import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Collapse,
    Divider,
    Grid,
    LinearProgress,
    Stack,
    Typography,
    Alert,
    Chip,
    IconButton,
    Tooltip,
} from '@mui/material';
import { ChevronDown, ChevronRight, Image as ImageIcon, Layers, Play, ZoomIn, ZoomOut, Maximize2, Move, X as XIcon } from 'lucide-react';
import { useQueryClient } from 'react-query';
import {
    JobSubmitRequest,
    useCancelJob,
    usePluginInputSchema,
    useSubmitPluginJob,
    PluginSummary,
} from '../api/PluginApi.ts';
import { SchemaForm } from './SchemaForm.tsx';
import { ResultRenderer } from './results/ResultRenderers.tsx';
import { ImagePickerDialog } from './ImagePickerDialog.tsx';
import { ProgressTracker } from './ProgressTracker.tsx';
import { useJobStore } from '../../../app/layouts/PanelLayout/useJobStore.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import { settings } from '../../../shared/config/settings.ts';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { useAuth } from '../../auth/model/AuthContext.tsx';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

interface PluginRunnerProps {
    plugin: PluginSummary;
}

/** Schema-driven single-job runner. Progress comes from Socket.IO. */
export const PluginRunner: React.FC<PluginRunnerProps> = ({ plugin }) => {
    const { sid } = useSocket();
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const { data: schema, isLoading: schemaLoading, error: schemaError } =
        usePluginInputSchema(plugin.plugin_id);
    const submit = useSubmitPluginJob(plugin.plugin_id);
    const cancel = useCancelJob();

    // pp/template-picker uses the preview endpoint on this page — test images
    // typically don't exist in the DB, so saving to image-metadata or creating
    // job rows isn't useful. Other plugins keep the job-submit flow.
    const usePreviewMode = plugin.plugin_id === 'pp/template-picker';

    const defaults = useMemo(() => buildDefaults(schema), [schema]);
    const [values, setValues] = useState<Record<string, any>>({});
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [showRequest, setShowRequest] = useState(false);
    const [imagePickerOpen, setImagePickerOpen] = useState(false);
    const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
    const [pickedPath, setPickedPath] = useState<string | null>(null);
    const [lastImageDir, setLastImageDir] = useState<string | null>(null);
    const [lastTemplateDir, setLastTemplateDir] = useState<string | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);

    // Local preview state (pp/template-picker only)
    const [previewRunning, setPreviewRunning] = useState(false);
    const [previewResult, setPreviewResult] = useState<any | null>(null);
    const [previewRunError, setPreviewRunError] = useState<string | null>(null);
    const [retuning, setRetuning] = useState(false);
    const [previewStale, setPreviewStale] = useState(false);
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // Tunable keys — fields whose changes can be re-applied via /retune without
    // redoing the expensive FFT. Derived from the plugin's own schema metadata.
    const tunableKeys = useMemo<Set<string>>(() => {
        const out = new Set<string>();
        const props = (schema as any)?.properties;
        if (props) {
            for (const [key, raw] of Object.entries<any>(props)) {
                if (raw?.ui_tunable === true) out.add(key);
            }
        }
        return out;
    }, [schema]);

    const imagePathField = useMemo(() => findImagePathField(schema), [schema]);
    const templatePathsField = useMemo(() => findTemplatePathsField(schema), [schema]);

    React.useEffect(() => {
        if (!pickedPath) {
            setPreviewUrl(null);
            setPreviewError(null);
            return;
        }
        let revoked = false;
        let objectUrl: string | null = null;
        setPreviewError(null);
        api
            .get('/web/files/preview', { params: { path: pickedPath }, responseType: 'blob' })
            .then((res) => {
                if (revoked) return;
                objectUrl = URL.createObjectURL(res.data);
                setPreviewUrl(objectUrl);
            })
            .catch((err) => {
                if (revoked) return;
                setPreviewError(err.response?.data?.detail || err.message || 'Preview failed');
            });
        return () => {
            revoked = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [pickedPath]);

    const handlePickImage = (path: string) => {
        setPickedPath(path);
        setValues((prev) => {
            const next = { ...prev };
            if (imagePathField) next[imagePathField] = path;
            const apix = imagePixelSizeFor(plugin.plugin_id, path);
            if (apix != null) next['image_pixel_size'] = apix;
            return next;
        });
    };

    const handlePickTemplates = (paths: string[]) => {
        if (!templatePathsField) return;
        setValues((prev) => {
            const replaced = Array.from(new Set(paths));
            const next: Record<string, any> = { ...prev, [templatePathsField]: replaced };
            const apix = templatePixelSizeFor(plugin.plugin_id, paths);
            if (apix != null) next['template_pixel_size'] = apix;
            return next;
        });
    };

    const requestPreview = useMemo(() => {
        const base = settings.ConfigData.SERVER_API_URL.replace(/\/$/, '');
        if (usePreviewMode) {
            return {
                url: `${base}/plugins/pp/template-pick/preview`,
                body: values,
            };
        }
        const body: JobSubmitRequest = { input: values, name: `${plugin.name} run` };
        const url = `${base}/plugins/${plugin.plugin_id}/jobs${sid ? `?sid=${sid}` : ''}`;
        return { url, body };
    }, [plugin.plugin_id, plugin.name, values, sid, usePreviewMode]);

    React.useEffect(() => {
        if (schema && Object.keys(values).length === 0) {
            setValues({ ...defaults, ...pluginTestDefaultsFor(plugin.plugin_id) });
        }
    }, [schema]); // eslint-disable-line react-hooks/exhaustive-deps

    const currentJob = useJobStore((s) =>
        currentJobId ? s.jobs.find((j) => j.job_id === currentJobId) : undefined,
    );

    const handleSubmit = async () => {
        setFieldErrors({});
        try {
            const job = await submit.mutateAsync({
                input: values,
                name: `${plugin.name} run`,
                user_id: user?.id,
                sid,
            });
            setCurrentJobId(job.job_id);
            useJobStore.getState().upsertJob(job);
            queryClient.invalidateQueries(['plugin-jobs']);
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            const parsed = parseFieldErrors(detail);
            if (Object.keys(parsed).length > 0) setFieldErrors(parsed);
        }
    };

    const handlePreview = async () => {
        setPreviewRunError(null);
        setFieldErrors({});
        setPreviewRunning(true);
        setPreviewStale(false);
        try {
            const payload = { ...values };
            Object.keys(payload).forEach((k) => {
                if (payload[k] === null || payload[k] === undefined) delete payload[k];
            });
            const res = await api.post('/plugins/pp/template-pick/preview', payload);
            setPreviewResult(res.data);
            lastRetunedValuesRef.current = pickTunable(values, tunableKeys);
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            const parsed = parseFieldErrors(detail);
            if (Object.keys(parsed).length > 0) {
                setFieldErrors(parsed);
                setPreviewRunError('Fix the highlighted field(s) and retry.');
            } else {
                setPreviewRunError(
                    typeof detail === 'string' ? detail : (err?.message || 'Preview failed'),
                );
            }
        } finally {
            setPreviewRunning(false);
        }
    };

    // Live retune: when a preview exists and only tunable fields change, re-apply
    // them via /retune without recomputing correlation maps. Any non-tunable
    // change marks the preview as stale so the user knows to re-run Preview.
    const lastRetunedValuesRef = useRef<Record<string, any>>({});
    const retuneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!usePreviewMode) return;
        const previewId = previewResult?.preview_id;
        if (!previewId) return;

        const changedKeys = diffChangedKeys(values, lastRetunedValuesRef.current);
        if (changedKeys.length === 0) return;

        const nonTunableChanged = changedKeys.some((k) => !tunableKeys.has(k));
        if (nonTunableChanged) {
            setPreviewStale(true);
            return;
        }
        // All changes are tunable — fire a debounced retune.
        if (retuneTimerRef.current) clearTimeout(retuneTimerRef.current);
        retuneTimerRef.current = setTimeout(async () => {
            setRetuning(true);
            try {
                const retunePayload: Record<string, any> = {};
                for (const k of tunableKeys) {
                    if (values[k] !== undefined && values[k] !== null) retunePayload[k] = values[k];
                }
                const res = await api.post(
                    `/plugins/pp/template-pick/preview/${previewId}/retune`,
                    retunePayload,
                );
                setPreviewResult((prev: any) => prev ? {
                    ...prev,
                    particles: res.data.particles,
                    num_particles: res.data.num_particles,
                } : prev);
                lastRetunedValuesRef.current = pickTunable(values, tunableKeys);
            } catch (err: any) {
                // Retune failed — surface as an error but keep the existing preview.
                const detail = err?.response?.data?.detail;
                setPreviewRunError(
                    typeof detail === 'string' ? detail : (err?.message || 'Retune failed'),
                );
            } finally {
                setRetuning(false);
            }
        }, 300);

        return () => {
            if (retuneTimerRef.current) clearTimeout(retuneTimerRef.current);
        };
    }, [values, previewResult?.preview_id, tunableKeys, usePreviewMode]);

    if (schemaLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (schemaError) {
        return <Alert severity="error">Failed to load input schema for {plugin.plugin_id}</Alert>;
    }

    const templateCount = Array.isArray(values[templatePathsField ?? ''])
        ? values[templatePathsField as string].length
        : 0;

    const pickedName = pickedPath ? (pickedPath.split(/[\\/]/).pop() || pickedPath) : null;
    const isRunning = usePreviewMode
        ? previewRunning
        : (submit.isLoading || currentJob?.status === 'running' || currentJob?.status === 'queued');
    const displayedResult = usePreviewMode ? previewResult : currentJob?.result;
    const showsResult = usePreviewMode ? !!previewResult : currentJob?.status === 'completed';

    return (
        <Card variant="outlined" sx={{ overflow: 'visible' }}>
            <CardContent sx={{ pb: 2 }}>
                <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={2}
                    alignItems={{ xs: 'flex-start', sm: 'center' }}
                    justifyContent="space-between"
                    sx={{ mb: 1 }}
                >
                    <Box sx={{ minWidth: 0 }}>
                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ rowGap: 0.5 }}>
                            <Typography variant="h6" sx={{ lineHeight: 1.2 }}>{plugin.name}</Typography>
                            <Chip size="small" label={`v${plugin.version}`} />
                            <Chip size="small" variant="outlined" label={plugin.category} />
                        </Stack>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {plugin.description}
                        </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} alignItems="center" flexShrink={0}>
                        <Button
                            size="small"
                            variant="text"
                            onClick={() => setShowRequest((v) => !v)}
                            startIcon={showRequest ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            sx={{ color: 'text.secondary' }}
                        >
                            Request
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={isRunning ? <CircularProgress size={14} color="inherit" /> : <Play size={16} />}
                            onClick={usePreviewMode ? handlePreview : handleSubmit}
                            disabled={isRunning}
                        >
                            {usePreviewMode
                                ? (previewRunning ? 'Previewing…' : 'Preview')
                                : (currentJob?.status === 'running' ? 'Running…'
                                    : currentJob?.status === 'queued' ? 'Queued…' : 'Run')}
                        </Button>
                        {!usePreviewMode
                            && currentJobId
                            && (currentJob?.status === 'running' || currentJob?.status === 'queued') && (
                            <Button
                                variant="outlined"
                                color="warning"
                                startIcon={<XIcon size={14} />}
                                onClick={() => cancel.mutate(currentJobId)}
                                disabled={cancel.isLoading}
                            >
                                {cancel.isLoading ? 'Cancelling…' : 'Cancel'}
                            </Button>
                        )}
                    </Stack>
                </Stack>

                <Divider sx={{ mt: 2, mb: 2 }} />

                <Grid container spacing={3}>
                    <Grid size={{ xs: 12, md: 7 }}>
                        <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 0.5 }}>
                            Inputs
                        </Typography>
                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mt: 0.5, mb: 1.5, rowGap: 1 }}>
                            {pickedName ? (
                                <Chip
                                    size="small"
                                    icon={<ImageIcon size={14} />}
                                    label={pickedName}
                                    title={pickedPath ?? undefined}
                                    onDelete={() => {
                                        setPickedPath(null);
                                        if (imagePathField) {
                                            setValues((prev) => ({ ...prev, [imagePathField]: undefined }));
                                        }
                                    }}
                                    deleteIcon={<XIcon size={14} />}
                                    onClick={() => setImagePickerOpen(true)}
                                />
                            ) : (
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<ImageIcon size={14} />}
                                    onClick={() => setImagePickerOpen(true)}
                                >
                                    Pick test image…
                                </Button>
                            )}
                            {templatePathsField && (
                                templateCount > 0 ? (
                                    <Chip
                                        size="small"
                                        icon={<Layers size={14} />}
                                        label={`${templateCount} template${templateCount === 1 ? '' : 's'}`}
                                        onDelete={() => setValues((prev) => ({ ...prev, [templatePathsField]: [] }))}
                                        deleteIcon={<XIcon size={14} />}
                                        onClick={() => setTemplatePickerOpen(true)}
                                    />
                                ) : (
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<Layers size={14} />}
                                        onClick={() => setTemplatePickerOpen(true)}
                                    >
                                        Pick templates…
                                    </Button>
                                )
                            )}
                        </Stack>

                        <SchemaForm
                            schema={schema}
                            value={values}
                            onChange={(next) => {
                                setValues(next);
                                if (Object.keys(fieldErrors).length > 0) {
                                    const remaining: Record<string, string> = {};
                                    for (const [k, msg] of Object.entries(fieldErrors)) {
                                        if (next[k] === values[k]) remaining[k] = msg;
                                    }
                                    setFieldErrors(remaining);
                                }
                            }}
                            disabled={isRunning}
                            errors={fieldErrors}
                        />

                        <Collapse in={showRequest}>
                            <Box
                                sx={{
                                    mt: 2,
                                    p: 1.5,
                                    borderRadius: 1,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    bgcolor: (t) => t.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    overflowX: 'auto',
                                }}
                            >
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                    POST {requestPreview.url}
                                </Typography>
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                    {JSON.stringify(requestPreview.body, null, 2)}
                                </pre>
                            </Box>
                        </Collapse>
                    </Grid>

                    <Grid size={{ xs: 12, md: 5 }}>
                        <Box sx={{ position: { md: 'sticky' }, top: { md: 16 } }}>
                            {!usePreviewMode && submit.isError && (
                                <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                                    {formatSubmitError(submit.error)}
                                </Alert>
                            )}
                            {usePreviewMode && previewRunError && (
                                <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                                    {previewRunError}
                                </Alert>
                            )}
                            {usePreviewMode && previewResult && (
                                <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                    <Chip size="small" color="success"
                                        label={`${previewResult.num_particles} particle${previewResult.num_particles === 1 ? '' : 's'}`} />
                                    {retuning && (
                                        <Chip size="small" color="info" icon={<CircularProgress size={10} color="inherit" />} label="Retuning…" />
                                    )}
                                    {previewStale && !retuning && (
                                        <Chip size="small" color="warning" label="Preview stale — re-run Preview" />
                                    )}
                                    {!retuning && !previewStale && tunableKeys.size > 0 && (
                                        <Typography variant="caption" color="text.secondary">
                                            Live tune: {tunableKeys.size} field{tunableKeys.size === 1 ? '' : 's'}
                                        </Typography>
                                    )}
                                </Box>
                            )}
                            {!usePreviewMode && currentJob && (
                                <RunStatusBanner job={currentJob} />
                            )}
                            {!usePreviewMode && currentJobId && (
                                <ProgressTracker jobId={currentJobId} />
                            )}
                            <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 0.5, display: 'block', mb: 0.5 }}>
                                Preview
                            </Typography>
                            {previewError ? (
                                <Alert severity="warning">{previewError}</Alert>
                            ) : previewUrl ? (
                                <Box
                                    sx={{
                                        borderRadius: 1,
                                        overflow: 'hidden',
                                        bgcolor: 'grey.900',
                                        boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.06)',
                                        display: 'flex',
                                        justifyContent: 'center',
                                    }}
                                >
                                    <ZoomablePreview
                                        src={previewUrl}
                                        overlay={
                                            <ParticleOverlay
                                                result={showsResult ? displayedResult : undefined}
                                                diameterAngstrom={Number(values['diameter_angstrom']) || undefined}
                                                imagePixelSize={Number(values['image_pixel_size']) || undefined}
                                            />
                                        }
                                    />
                                </Box>
                            ) : (
                                <Box
                                    sx={{
                                        border: '1px dashed',
                                        borderColor: 'divider',
                                        borderRadius: 1,
                                        py: 5,
                                        px: 3,
                                        textAlign: 'center',
                                        color: 'text.secondary',
                                        bgcolor: 'action.hover',
                                    }}
                                >
                                    <ImageIcon size={28} style={{ opacity: 0.5 }} />
                                    <Typography variant="body2" sx={{ mt: 1 }}>
                                        No test image selected
                                    </Typography>
                                    <Typography variant="caption">
                                        Pick one above to preview it here.
                                    </Typography>
                                </Box>
                            )}

                            {showsResult && displayedResult && (
                                <Box sx={{ mt: 2 }}>
                                    <ResultRenderer pluginId={plugin.plugin_id} result={displayedResult} />
                                </Box>
                            )}
                        </Box>
                    </Grid>
                </Grid>
            </CardContent>

            <ImagePickerDialog
                open={imagePickerOpen}
                onClose={() => setImagePickerOpen(false)}
                onPick={handlePickImage}
                onPathChange={setLastImageDir}
                initialPath={lastImageDir ?? parentDir(pickedPath) ?? undefined}
                storageKey="imagePicker:lastPath:shared"
            />
            <ImagePickerDialog
                open={templatePickerOpen}
                onClose={() => setTemplatePickerOpen(false)}
                multiple
                onPick={handlePickTemplates}
                onPathChange={setLastTemplateDir}
                title="Pick templates"
                initialPath={lastTemplateDir ?? parentDir(pickedPath) ?? undefined}
                storageKey="imagePicker:lastPath:shared"
            />
        </Card>
    );
};

function parseFieldErrors(detail: unknown): Record<string, string> {
    if (!Array.isArray(detail)) return {};
    const out: Record<string, string> = {};
    for (const item of detail as any[]) {
        if (!item?.loc || !item?.msg) continue;
        // FastAPI loc looks like ["body", "input", "threshold"] for wrapped
        // JobSubmitRequest bodies, or ["body", "threshold"] for direct
        // /preview bodies. Strip the request-envelope segments and take the
        // first remaining segment as the field key.
        const loc = Array.isArray(item.loc) ? item.loc : [];
        const segments = loc.filter((s: unknown) => s !== 'body' && s !== 'input');
        const key = segments.length > 0 ? String(segments[0]) : '';
        if (key && !out[key]) out[key] = String(item.msg);
    }
    return out;
}

function pickTunable(values: Record<string, any>, tunableKeys: Set<string>): Record<string, any> {
    const out: Record<string, any> = {};
    for (const k of tunableKeys) out[k] = values[k];
    return out;
}

function diffChangedKeys(next: Record<string, any>, prev: Record<string, any>): string[] {
    const keys = new Set<string>([...Object.keys(next), ...Object.keys(prev)]);
    const changed: string[] = [];
    for (const k of keys) {
        if (!shallowEqual(next[k], prev[k])) changed.push(k);
    }
    return changed;
}

function shallowEqual(a: any, b: any): boolean {
    if (a === b) return true;
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
        return true;
    }
    return false;
}

function parentDir(path: string | null | undefined): string | null {
    if (!path) return null;
    const norm = path.replace(/\\/g, '/');
    const idx = norm.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = norm.slice(0, idx);
    if (/^[A-Za-z]:$/.test(parent)) return parent + '/';
    return parent || '/';
}

// ---------------------------------------------------------------------------

interface ZoomablePreviewProps {
    src: string;
    overlay?: React.ReactNode;
}

const MIN_SCALE = 1;
const MAX_SCALE = 12;

const ZoomablePreview: React.FC<ZoomablePreviewProps> = ({ src, overlay }) => {
    const [scale, setScale] = React.useState(1);
    const [offset, setOffset] = React.useState({ x: 0, y: 0 });
    const dragRef = React.useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
    const wrapRef = React.useRef<HTMLDivElement | null>(null);

    const reset = () => { setScale(1); setOffset({ x: 0, y: 0 }); };

    const zoomAroundCenter = (factor: number) => {
        const rect = wrapRef.current?.getBoundingClientRect();
        if (!rect) return;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        if (nextScale === scale) return;
        const k = nextScale / scale;
        setOffset({
            x: cx - k * (cx - offset.x),
            y: cy - k * (cy - offset.y),
        });
        setScale(nextScale);
    };

    const onWheel = (e: React.WheelEvent) => {
        e.preventDefault();
        const rect = wrapRef.current?.getBoundingClientRect();
        if (!rect) return;
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        if (nextScale === scale) return;
        const k = nextScale / scale;
        setOffset({
            x: cx - k * (cx - offset.x),
            y: cy - k * (cy - offset.y),
        });
        setScale(nextScale);
    };

    const onMouseDown = (e: React.MouseEvent) => {
        if (scale === 1) return;
        dragRef.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
    };
    const onMouseMove = (e: React.MouseEvent) => {
        if (!dragRef.current) return;
        setOffset({
            x: dragRef.current.ox + (e.clientX - dragRef.current.x),
            y: dragRef.current.oy + (e.clientY - dragRef.current.y),
        });
    };
    const endDrag = () => { dragRef.current = null; };

    return (
        <Box
            ref={wrapRef}
            onWheel={onWheel}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={endDrag}
            onMouseLeave={endDrag}
            onDoubleClick={reset}
            sx={{
                position: 'relative',
                overflow: 'hidden',
                maxWidth: '100%',
                maxHeight: 420,
                cursor: scale > 1 ? (dragRef.current ? 'grabbing' : 'grab') : 'zoom-in',
                userSelect: 'none',
            }}
        >
            <Box
                sx={{
                    transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                    transformOrigin: '0 0',
                    position: 'relative',
                    display: 'inline-block',
                }}
            >
                <img
                    src={src}
                    alt="Test image preview"
                    draggable={false}
                    style={{ display: 'block', maxWidth: '100%', maxHeight: 420, objectFit: 'contain' }}
                />
                {overlay}
            </Box>
            <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                onMouseDown={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
                sx={{
                    position: 'absolute', top: 6, right: 6,
                    bgcolor: 'rgba(0,0,0,0.55)', color: '#fff',
                    px: 0.5, py: 0.25, borderRadius: 1,
                    backdropFilter: 'blur(2px)',
                }}
            >
                <Tooltip title="Zoom in">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => zoomAroundCenter(1.25)}
                            disabled={scale >= MAX_SCALE}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <ZoomIn size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title="Zoom out">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => zoomAroundCenter(1 / 1.25)}
                            disabled={scale <= MIN_SCALE}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <ZoomOut size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title="Reset (double-click image)">
                    <span>
                        <IconButton
                            size="small"
                            onClick={reset}
                            disabled={scale === 1 && offset.x === 0 && offset.y === 0}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <Maximize2 size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title={scale > 1 ? 'Drag the image to pan' : 'Zoom in to pan'}>
                    <Box sx={{ display: 'flex', alignItems: 'center', px: 0.25, opacity: scale > 1 ? 1 : 0.45 }}>
                        <Move size={14} />
                    </Box>
                </Tooltip>
                <Typography variant="caption" sx={{ minWidth: 38, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {Math.round(scale * 100)}%
                </Typography>
            </Stack>
        </Box>
    );
};

interface ParticleOverlayProps {
    result: any;
    diameterAngstrom?: number;
    imagePixelSize?: number;
}

const ParticleOverlay: React.FC<ParticleOverlayProps> = ({ result, diameterAngstrom, imagePixelSize }) => {
    if (!result) return null;
    const particles = Array.isArray(result.particles) ? result.particles : [];
    const shape = result.image_shape as [number, number] | undefined;
    if (!particles.length || !shape || shape.length !== 2) return null;
    const [h, w] = shape;

    // Particle radius in binned-image pixels; fall back to 1.2% of image width.
    const bin = Number(result.image_binning) || 1;
    const targetApix = Number(result.target_pixel_size) || (imagePixelSize ? imagePixelSize * bin : undefined);
    const radiusBinned =
        diameterAngstrom && targetApix ? diameterAngstrom / targetApix / 2 : w * 0.012;

    return (
        <svg
            viewBox={`0 0 ${w} ${h}`}
            preserveAspectRatio="xMidYMid meet"
            style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
            }}
        >
            {particles.map((p: any, i: number) => (
                <circle
                    key={i}
                    cx={p.x}
                    cy={p.y}
                    r={radiusBinned}
                    fill="none"
                    stroke="#00e676"
                    strokeWidth={Math.max(w, h) * 0.002}
                    opacity={0.9}
                />
            ))}
        </svg>
    );
};

// ---------------------------------------------------------------------------

interface RunStatusBannerProps {
    job: any;
}

const RunStatusBanner: React.FC<RunStatusBannerProps> = ({ job }) => {
    const statusColor =
        job.status === 'completed' ? 'success' :
        job.status === 'failed' ? 'error' :
        job.status === 'cancelled' ? 'warning' :
        job.status === 'running' ? 'info' :
        job.status === 'queued' ? 'warning' : 'default';

    const startedAt = job.started_at ? new Date(job.started_at).getTime() : null;
    const finishedAt = job.finished_at ? new Date(job.finished_at).getTime() : null;
    const [now, setNow] = React.useState(() => Date.now());
    const active = job.status === 'running' || job.status === 'queued';

    React.useEffect(() => {
        if (!active) return;
        const id = setInterval(() => setNow(Date.now()), 500);
        return () => clearInterval(id);
    }, [active]);

    const elapsedMs = startedAt
        ? (finishedAt ?? now) - startedAt
        : null;

    const particles = job.result?.num_particles;

    return (
        <Box
            sx={{
                mb: 2,
                p: 1.25,
                borderRadius: 1,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: (t) => t.palette.mode === 'dark' ? 'background.paper' : 'grey.50',
            }}
        >
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: active ? 1 : 0, flexWrap: 'wrap', rowGap: 0.5 }}>
                <Chip size="small" color={statusColor as any} label={job.status} sx={{ textTransform: 'capitalize' }} />
                {elapsedMs != null && (
                    <Typography variant="caption" color="text.secondary" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                        {formatDuration(elapsedMs)}
                    </Typography>
                )}
                {job.status === 'completed' && typeof particles === 'number' && (
                    <Chip size="small" variant="outlined" color="success" label={`${particles} particle${particles === 1 ? '' : 's'}`} />
                )}
                <Box sx={{ flex: 1 }} />
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                    {String(job.job_id).slice(0, 8)}
                </Typography>
            </Stack>
            {active && (
                <LinearProgress
                    variant={typeof job.progress === 'number' ? 'determinate' : 'indeterminate'}
                    value={job.progress ?? 0}
                    sx={{ height: 4, borderRadius: 1 }}
                />
            )}
            {job.status === 'failed' && job.error && (
                <Alert severity="error" sx={{ mt: 1 }}>{job.error}</Alert>
            )}
        </Box>
    );
};

function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms} ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = Math.round(s - m * 60);
    return `${m}m ${rem}s`;
}

// ---------------------------------------------------------------------------

function formatSubmitError(err: any): string {
    const status = err?.response?.status;
    const data = err?.response?.data;
    const detail = typeof data?.detail === 'string'
        ? data.detail
        : data?.detail
            ? JSON.stringify(data.detail, null, 2)
            : null;
    if (status && detail) return `HTTP ${status}: ${detail}`;
    if (status) return `HTTP ${status}: ${err?.message ?? 'Request failed'}`;
    if (err?.message === 'Network Error') {
        return 'Network error — the server may have returned a response without CORS headers. Check the backend log for the real error.';
    }
    return err?.message || 'Submission failed';
}

function buildDefaults(schema: any): Record<string, any> {
    if (!schema?.properties) return {};
    const out: Record<string, any> = {};
    for (const [key, prop] of Object.entries<any>(schema.properties)) {
        if (prop?.default !== undefined) out[key] = prop.default;
    }
    return out;
}

/** Pick the schema property most likely to hold a single image path. */
function findImagePathField(schema: any): string | null {
    if (!schema?.properties) return null;
    const stringKeys = Object.entries<any>(schema.properties)
        .filter(([, prop]) => prop?.type === 'string')
        .map(([key]) => key);
    const imagePath = stringKeys.find((k) => /image.*path|micrograph.*path/i.test(k));
    if (imagePath) return imagePath;
    const anyPath = stringKeys.find((k) => /path$/i.test(k) || /_path/i.test(k));
    if (anyPath) return anyPath;
    const imageKey = stringKeys.find((k) => /image|micrograph/i.test(k));
    return imageKey ?? null;
}

// ---------------------------------------------------------------------------
// Plugin-specific test-bench presets. Values come from the plugin's own
// Sandbox README so "pick test image + pick templates + run" just works.

interface PluginPreset {
    defaults?: Record<string, any>;
    imagePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
    templatePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
}

const PLUGIN_PRESETS: Record<string, PluginPreset> = {
    'pp/template-picker': {
        defaults: {
            diameter_angstrom: 220,
            invert_templates: true,
            bin_factor: 4,
            lowpass_resolution: 12.0,
            threshold: 0.35,
        },
        imagePixelSizesByFilename: [
            { match: /24may23b/i, apix: 1.230 },
            { match: /25may06y/i, apix: 0.830 },
        ],
        templatePixelSizesByFilename: [
            { match: /origTemplate/i, apix: 2.646 },
        ],
    },
};

function pluginTestDefaultsFor(pluginId: string): Record<string, any> {
    return PLUGIN_PRESETS[pluginId]?.defaults ?? {};
}

function imagePixelSizeFor(pluginId: string, path: string): number | null {
    const preset = PLUGIN_PRESETS[pluginId];
    if (!preset?.imagePixelSizesByFilename) return null;
    const name = path.split(/[\\/]/).pop() ?? path;
    return preset.imagePixelSizesByFilename.find((r) => r.match.test(name))?.apix ?? null;
}

function templatePixelSizeFor(pluginId: string, paths: string[]): number | null {
    const preset = PLUGIN_PRESETS[pluginId];
    if (!preset?.templatePixelSizesByFilename || paths.length === 0) return null;
    // All templates must match the same rule, otherwise don't auto-fill.
    for (const rule of preset.templatePixelSizesByFilename) {
        if (paths.every((p) => rule.match.test(p.split(/[\\/]/).pop() ?? p))) {
            return rule.apix;
        }
    }
    return null;
}

/** Pick the schema property most likely to hold a list of template paths. */
function findTemplatePathsField(schema: any): string | null {
    if (!schema?.properties) return null;
    const arrayOfStringKeys = Object.entries<any>(schema.properties)
        .filter(([, prop]) => prop?.type === 'array' && prop?.items?.type === 'string')
        .map(([key]) => key);
    const templateKey = arrayOfStringKeys.find((k) => /template/i.test(k));
    if (templateKey) return templateKey;
    return arrayOfStringKeys.find((k) => /path/i.test(k)) ?? null;
}
