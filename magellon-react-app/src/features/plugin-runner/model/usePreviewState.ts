import { useEffect, useReducer, useRef } from 'react';
import { settings } from '../../../shared/config/settings.ts';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { apiErrorMessage } from '../../../shared/api/apiError.ts';
import type { PreviewResult } from './previewTypes.ts';
import { parseFieldErrors } from './formErrors.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

/**
 * Preview state for the plugin runner: the picked test image (streamed
 * as a blob from /web/files/preview) plus, for plugins advertising the
 * preview capability, the /preview run and the debounced live /retune
 * loop.
 */
export interface PreviewState {
    /** Object URL of the picked test image, if loaded. */
    previewUrl: string | null;
    /** Error loading the picked test image. */
    previewError: string | null;
    /** A /preview call is in flight. */
    previewRunning: boolean;
    /** Result of the last successful /preview call. */
    previewResult: PreviewResult | null;
    /** Error from the last /preview or /retune call. */
    previewRunError: string | null;
    /** A debounced /retune call is in flight. */
    retuning: boolean;
    /** A non-tunable field changed since the last preview run. */
    previewStale: boolean;
}

type PreviewAction =
    | { type: 'image-cleared' }
    | { type: 'image-loading' }
    | { type: 'image-loaded'; url: string }
    | { type: 'image-failed'; message: string }
    | { type: 'preview-started' }
    | { type: 'preview-succeeded'; result: PreviewResult }
    | { type: 'preview-failed'; message: string }
    | { type: 'preview-settled' }
    | { type: 'marked-stale' }
    | { type: 'retune-started' }
    | { type: 'retune-succeeded'; particles: PreviewResult['particles']; numParticles: PreviewResult['num_particles'] }
    | { type: 'retune-failed'; message: string }
    | { type: 'retune-settled' };

const initialState: PreviewState = {
    previewUrl: null,
    previewError: null,
    previewRunning: false,
    previewResult: null,
    previewRunError: null,
    retuning: false,
    previewStale: false,
};

function reducer(state: PreviewState, action: PreviewAction): PreviewState {
    switch (action.type) {
        case 'image-cleared':
            return { ...state, previewUrl: null, previewError: null };
        case 'image-loading':
            return { ...state, previewError: null };
        case 'image-loaded':
            return { ...state, previewUrl: action.url };
        case 'image-failed':
            return { ...state, previewError: action.message };
        case 'preview-started':
            return { ...state, previewRunError: null, previewRunning: true, previewStale: false };
        case 'preview-succeeded':
            return { ...state, previewResult: action.result };
        case 'preview-failed':
            return { ...state, previewRunError: action.message };
        case 'preview-settled':
            return { ...state, previewRunning: false };
        case 'marked-stale':
            return { ...state, previewStale: true };
        case 'retune-started':
            return { ...state, retuning: true };
        case 'retune-succeeded':
            // Retune only replaces the particle set — keep the existing
            // preview (image shape, preview_id, …) untouched.
            return state.previewResult
                ? {
                    ...state,
                    previewResult: {
                        ...state.previewResult,
                        particles: action.particles,
                        num_particles: action.numParticles,
                    },
                }
                : state;
        case 'retune-failed':
            return { ...state, previewRunError: action.message };
        case 'retune-settled':
            return { ...state, retuning: false };
    }
}

interface UsePreviewStateArgs {
    /** Plugin advertises Capability.PREVIEW — enables the retune loop. */
    usePreviewMode: boolean;
    /** Filesystem path of the picked test image, if any. */
    pickedPath: string | null;
    /** Current form values. */
    values: Record<string, unknown>;
    /** Fields whose changes can be re-applied via /retune. */
    tunableKeys: Set<string>;
    /** Surfaces FastAPI per-field validation errors on the form. */
    setFieldErrors: (errors: Record<string, string>) => void;
}

export const usePreviewState = ({
    usePreviewMode,
    pickedPath,
    values,
    tunableKeys,
    setFieldErrors,
}: UsePreviewStateArgs): PreviewState & { handlePreview: () => Promise<void> } => {
    const [state, dispatch] = useReducer(reducer, initialState);

    useEffect(() => {
        if (!pickedPath) {
            dispatch({ type: 'image-cleared' });
            return;
        }
        let revoked = false;
        let objectUrl: string | null = null;
        dispatch({ type: 'image-loading' });
        api
            .get('/web/files/preview', { params: { path: pickedPath }, responseType: 'blob' })
            .then((res) => {
                if (revoked) return;
                objectUrl = URL.createObjectURL(res.data);
                dispatch({ type: 'image-loaded', url: objectUrl });
            })
            .catch((err) => {
                if (revoked) return;
                dispatch({
                    type: 'image-failed',
                    message: err.response?.data?.detail || err.message || 'Preview failed',
                });
            });
        return () => {
            revoked = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [pickedPath]);

    const handlePreview = async () => {
        dispatch({ type: 'preview-started' });
        setFieldErrors({});
        try {
            const payload = { ...values };
            Object.keys(payload).forEach((k) => {
                if (payload[k] === null || payload[k] === undefined) delete payload[k];
            });
            const res = await api.post('/particle-picking/preview', payload);
            dispatch({ type: 'preview-succeeded', result: res.data });
            lastRetunedValuesRef.current = pickTunable(values, tunableKeys);
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
            const parsed = parseFieldErrors(detail);
            if (Object.keys(parsed).length > 0) {
                setFieldErrors(parsed);
                dispatch({ type: 'preview-failed', message: 'Fix the highlighted field(s) and retry.' });
            } else {
                dispatch({
                    type: 'preview-failed',
                    message: typeof detail === 'string' ? detail : apiErrorMessage(err, 'Preview failed'),
                });
            }
        } finally {
            dispatch({ type: 'preview-settled' });
        }
    };

    // Live retune: when a preview exists and only tunable fields change, re-apply
    // them via /retune without recomputing correlation maps. Any non-tunable
    // change marks the preview as stale so the user knows to re-run Preview.
    const lastRetunedValuesRef = useRef<Record<string, unknown>>({});
    const retuneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!usePreviewMode) return;
        const previewId = state.previewResult?.preview_id;
        if (!previewId) return;

        const changedKeys = diffChangedKeys(values, lastRetunedValuesRef.current);
        if (changedKeys.length === 0) return;

        const nonTunableChanged = changedKeys.some((k) => !tunableKeys.has(k));
        if (nonTunableChanged) {
            dispatch({ type: 'marked-stale' });
            return;
        }
        // All changes are tunable — fire a debounced retune.
        if (retuneTimerRef.current) clearTimeout(retuneTimerRef.current);
        retuneTimerRef.current = setTimeout(async () => {
            dispatch({ type: 'retune-started' });
            try {
                const retunePayload: Record<string, unknown> = {};
                for (const k of tunableKeys) {
                    if (values[k] !== undefined && values[k] !== null) retunePayload[k] = values[k];
                }
                const res = await api.post(
                    `/particle-picking/preview/${previewId}/retune`,
                    retunePayload,
                );
                dispatch({
                    type: 'retune-succeeded',
                    particles: res.data.particles,
                    numParticles: res.data.num_particles,
                });
                lastRetunedValuesRef.current = pickTunable(values, tunableKeys);
            } catch (err) {
                // Retune failed — surface as an error but keep the existing preview.
                const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
                dispatch({
                    type: 'retune-failed',
                    message: typeof detail === 'string' ? detail : apiErrorMessage(err, 'Retune failed'),
                });
            } finally {
                dispatch({ type: 'retune-settled' });
            }
        }, 300);

        return () => {
            if (retuneTimerRef.current) clearTimeout(retuneTimerRef.current);
        };
    }, [values, state.previewResult?.preview_id, tunableKeys, usePreviewMode]);

    return { ...state, handlePreview };
};

function pickTunable(values: Record<string, unknown>, tunableKeys: Set<string>): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const k of tunableKeys) out[k] = values[k];
    return out;
}

function diffChangedKeys(next: Record<string, unknown>, prev: Record<string, unknown>): string[] {
    const keys = new Set<string>([...Object.keys(next), ...Object.keys(prev)]);
    const changed: string[] = [];
    for (const k of keys) {
        if (!shallowEqual(next[k], prev[k])) changed.push(k);
    }
    return changed;
}

function shallowEqual(a: unknown, b: unknown): boolean {
    if (a === b) return true;
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
        return true;
    }
    return false;
}
