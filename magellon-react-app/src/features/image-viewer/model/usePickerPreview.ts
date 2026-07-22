import { useCallback, useRef, useState } from 'react';
import { apiErrorMessage } from '../../../shared/api/apiError.ts';
import type { Point } from '../lib/useParticleOperations.ts';
import { TEMPLATE_PICKER_PATH } from '../lib/useParticleOperations.ts';
import { API_URL, pointFromBackendPick } from './particleSettingsCore.ts';
import type { BackendPick, DrawerState, TrainedModel } from './particleSettingsTypes.ts';

interface UsePickerPreviewArgs {
    isValid: boolean;
    pickerParams: Record<string, unknown>;
    imageName: string | null;
    sessionName?: string;
    selectedBackend: string;
    isTopazBackend: boolean;
    manualTrainingParticles: Point[];
    onPreviewParticles: (particles: Point[]) => void;
    onPickerParamsChange: (params: Record<string, unknown>) => void;
    setTrainedModel: (model: TrainedModel | null) => void;
    setDrawerState: (state: DrawerState) => void;
    setShowErrors: (show: boolean) => void;
    setRuntimeError: (error: string | null) => void;
}

/** Preview / session-train / retune lifecycle for the settings panel. */
export function usePickerPreview({
    isValid,
    pickerParams,
    imageName,
    sessionName,
    selectedBackend,
    isTopazBackend,
    manualTrainingParticles,
    onPreviewParticles,
    onPickerParamsChange,
    setTrainedModel,
    setDrawerState,
    setShowErrors,
    setRuntimeError,
}: UsePickerPreviewArgs) {
    const [previewId, setPreviewId] = useState<string | null>(null);
    const [previewCount, setPreviewCount] = useState(0);
    const [scoreMapPng, setScoreMapPng] = useState<string | null>(null);
    const [retuning, setRetuning] = useState(false);
    const [training, setTraining] = useState(false);
    const retuneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // --- Preview ---
    const handlePreview = useCallback(async () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        setRuntimeError(null);
        setDrawerState('previewing');

        try {
            const payload: Record<string, unknown> = {
                ...pickerParams,
                image_path: imageName,
                backend: selectedBackend,
                session_name: sessionName,
            };
            Object.keys(payload).forEach(k => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; });

            const token = localStorage.getItem('access_token');
            const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview`, {
                method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `${res.status}`);
            }
            const data = await res.json();
            setPreviewId(data.preview_id);
            setPreviewCount(data.num_particles);
            setScoreMapPng(data.score_map_png_base64 || null);

            const threshold = Number(pickerParams.threshold ?? (isTopazBackend ? -3.0 : 0.4));
            const pts: Point[] = (data.particles || []).map((p: BackendPick, i: number) =>
                pointFromBackendPick(p, 'preview', i, threshold, isTopazBackend)
            );
            onPreviewParticles(pts);
            setDrawerState('preview');
        } catch (err) {
            setDrawerState('configure');
            setRuntimeError(`Preview failed: ${apiErrorMessage(err, 'unknown error')}`);
        }
    }, [isValid, pickerParams, imageName, selectedBackend, sessionName, onPreviewParticles]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleTrainSession = useCallback(async () => {
        if (!isTopazBackend || !imageName || !sessionName) return;
        if (!isValid) { setShowErrors(true); return; }
        if (manualTrainingParticles.length === 0) {
            setRuntimeError('Topaz training needs at least one manual annotation.');
            return;
        }
        setShowErrors(false);
        setRuntimeError(null);
        setTraining(true);
        setDrawerState('previewing');
        try {
            const token = localStorage.getItem('access_token');
            const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
            const payload = {
                backend: selectedBackend,
                image_path: imageName,
                session_name: sessionName,
                annotations: manualTrainingParticles.map((p) => ({
                    x: p.x,
                    y: p.y,
                    radius: p.radius,
                    class: p.class ?? '1',
                    type: p.type,
                })),
                picker_params: pickerParams,
            };
            const res = await fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/topaz/session-models`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeader },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `${res.status}`);
            }
            const data = await res.json();
            const nextParams = { ...pickerParams, ...data.engine_opts };
            onPickerParamsChange(nextParams);
            setTrainedModel(data);
            setPreviewId(data.preview_id || null);
            setPreviewCount(data.num_particles || 0);
            setScoreMapPng(null);
            const threshold = data.engine_opts?.threshold ?? -3.0;
            const pts: Point[] = (data.particles || []).map((p: BackendPick, i: number) =>
                pointFromBackendPick(p, 'trained', i, threshold, true)
            );
            onPreviewParticles(pts);
            setDrawerState('preview');
        } catch (err) {
            setDrawerState('configure');
            setRuntimeError(`Training failed: ${apiErrorMessage(err, 'unknown error')}`);
        } finally {
            setTraining(false);
        }
    }, [
        imageName,
        isTopazBackend,
        isValid,
        manualTrainingParticles,
        onPickerParamsChange,
        onPreviewParticles,
        pickerParams,
        selectedBackend,
        sessionName,
        setDrawerState,
        setRuntimeError,
        setShowErrors,
        setTrainedModel,
    ]);

    // --- Retune (debounced) ---
    const handleRetune = useCallback((newParams: Record<string, unknown>) => {
        onPickerParamsChange(newParams);
        if (!previewId) return;

        if (retuneTimer.current) clearTimeout(retuneTimer.current);
        retuneTimer.current = setTimeout(async () => {
            setRetuning(true);
            try {
                const retuneToken = localStorage.getItem('access_token');
                const retuneAuthHeader: Record<string, string> = retuneToken ? { Authorization: `Bearer ${retuneToken}` } : {};
                const retuneUrl = `${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}/retune`
                    + `?backend=${encodeURIComponent(selectedBackend)}`;
                const res = await fetch(retuneUrl, {
                    method: 'POST', headers: { 'Content-Type': 'application/json', ...retuneAuthHeader },
                    body: JSON.stringify({
                        threshold: newParams.threshold ?? 0.4,
                        radius: newParams.radius ?? newParams.min_distance ?? null,
                        max_threshold: newParams.max_threshold ?? null,
                        max_peaks: newParams.max_peaks ?? 500,
                        overlap_multiplier: newParams.overlap_multiplier ?? 1.0,
                        max_blob_size_multiplier: newParams.max_blob_size_multiplier ?? 1.0,
                        min_blob_roundness: newParams.min_blob_roundness ?? 0.0,
                        peak_position: newParams.peak_position ?? 'maximum',
                    }),
                });
                if (res.ok) {
                    const data = await res.json();
                    setPreviewCount(data.num_particles);
                    const threshold = Number(newParams.threshold ?? (isTopazBackend ? -3.0 : 0.4));
                    const pts: Point[] = (data.particles || []).map((p: BackendPick, i: number) =>
                        pointFromBackendPick(p, 'retune', i, threshold, isTopazBackend)
                    );
                    onPreviewParticles(pts);
                }
            } catch { /* ignore */ }
            setRetuning(false);
        }, 300);
    }, [previewId, selectedBackend, isTopazBackend, onPreviewParticles, onPickerParamsChange]);

    /** Delete the server-side preview session, if any (run/accept/discard). */
    const clearPreview = () => {
        if (previewId) {
            const clearToken = localStorage.getItem('access_token');
            const clearAuthHeader: Record<string, string> = clearToken ? { Authorization: `Bearer ${clearToken}` } : {};
            fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}?backend=${encodeURIComponent(selectedBackend)}`, {
                method: 'DELETE',
                headers: clearAuthHeader,
            }).catch(() => {});
            setPreviewId(null);
        }
    };

    const clearScoreMap = () => setScoreMapPng(null);

    return {
        previewCount,
        scoreMapPng,
        retuning,
        training,
        handlePreview,
        handleTrainSession,
        handleRetune,
        clearPreview,
        clearScoreMap,
    };
}
