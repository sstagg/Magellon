import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import {
    Box,
    Typography,
    CircularProgress,
    Chip,
    Button,
    Alert,
    AlertTitle,
    Collapse,
    LinearProgress,
    IconButton,
    MenuItem,
    Select,
    FormControl,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Visibility as PreviewIcon,
    PlayArrow as RunIcon,
    ErrorOutlined as ErrorIcon,
    CheckCircle as ValidIcon,
    ArrowBack as BackIcon,
    Check as AcceptIcon,
    Close as DiscardIcon,
    Tune as TuneIcon,
    Layers as BatchIcon,
    Send as DispatchIcon,
} from '@mui/icons-material';
import { SchemaForm, type BrowseFileRequest } from '../../../shared/ui/SchemaForm.tsx';
import { ImagePickerDialog } from '../../plugin-runner/ui/ImagePickerDialog.tsx';
import { settings as appSettings } from '../../../shared/config/settings.ts';
import { PickDispatchResponse, Point, TEMPLATE_PICKER_PATH } from '../lib/useParticleOperations.ts';
import { useJobStepEvents } from '../../../shared/lib/useJobStepEvents.ts';

interface BackendInfo {
    backend_id: string;
    plugin_id: string;
    label: string;
    capabilities: string[];
    has_preview: boolean;
    has_sync: boolean;
    http_endpoint: string | null;
    status: string;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DrawerState = 'configure' | 'previewing' | 'preview' | 'running' | 'dispatched' | 'results';

export interface ParticleSettingsDrawerProps {
    open: boolean;
    pickerParams: Record<string, any>;
    onPickerParamsChange: (params: Record<string, any>) => void;
    onRun: () => void;
    /** Dispatch a picking task via RMQ for the given backend and IPP name. */
    onDispatch: (targetBackend: string, ippName: string) => Promise<PickDispatchResponse | null>;
    /** Opens the batch-run modal so the user can pick the cohort of images. */
    onRunBatch?: () => void;
    isRunning: boolean;
    onPreviewParticles: (particles: Point[]) => void;
    onAcceptParticles: () => void;
    onDiscardParticles: () => void;
    imageName: string | null;
    /** Session of the selected image — lets the backend resolve the MRC path. */
    sessionName?: string;
    autoPickingProgress: number;
    resultCount: number | null;
    /** Optional IPP name for the run — used as the RMQ task label. */
    ippName?: string;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validateParams(schema: any, params: Record<string, any>, imageName: string | null): string[] {
    if (!schema?.properties) return [];
    const errors: string[] = [];
    const required = new Set<string>(schema.required || []);

    if (!imageName) {
        errors.push('No image selected — select a micrograph first.');
    }

    for (const [key, field] of Object.entries<any>(schema.properties)) {
        if (field.ui_hidden) continue;
        const value = params[key];
        const label = field.title || key;

        if (required.has(key)) {
            if (value === undefined || value === null || value === '') {
                errors.push(field.ui_required_message || `${label} is required.`);
                continue;
            }
            if (Array.isArray(value) && field.minItems && value.length < field.minItems) {
                errors.push(field.ui_required_message || `${label} needs at least ${field.minItems} item(s).`);
                continue;
            }
        }

        if (value !== null && value !== undefined && typeof value === 'number') {
            if (field.minimum !== undefined && value < field.minimum)
                errors.push(`${label} must be at least ${field.minimum}.`);
            if (field.maximum !== undefined && value > field.maximum)
                errors.push(`${label} must be at most ${field.maximum}.`);
            if (field.exclusiveMinimum !== undefined && value <= field.exclusiveMinimum)
                errors.push(`${label} must be greater than ${field.exclusiveMinimum}.`);
        }
    }
    return errors;
}

// ---------------------------------------------------------------------------
// Component — renders as a plain Box (no Drawer), meant to be placed
// inside the SidePanelArea alongside JobsPanel / LogsPanel.
// ---------------------------------------------------------------------------

const API_URL = appSettings.ConfigData.SERVER_API_URL;

export const ParticleSettingsPanel: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    pickerParams,
    onPickerParamsChange,
    onRun: _onRun,
    onDispatch,
    onRunBatch,
    isRunning,
    onPreviewParticles,
    onAcceptParticles,
    onDiscardParticles,
    imageName,
    sessionName,
    autoPickingProgress: _autoPickingProgress,
    resultCount,
    ippName,
}) => {
    const theme = useTheme();
    const [schema, setSchema] = useState<any>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);
    const [runtimeError, setRuntimeError] = useState<string | null>(null);
    const [showErrors, setShowErrors] = useState(false);
    const [drawerState, setDrawerState] = useState<DrawerState>('configure');
    const [previewId, setPreviewId] = useState<string | null>(null);
    const [previewCount, setPreviewCount] = useState(0);
    const [scoreMapPng, setScoreMapPng] = useState<string | null>(null);
    const [retuning, setRetuning] = useState(false);
    const [dispatchJobId, setDispatchJobId] = useState<string | null>(null);

    // Backend selection
    const [backends, setBackends] = useState<BackendInfo[]>([]);
    const [selectedBackend, setSelectedBackend] = useState<string>('topaz-particle-picking');
    const [backendsLoading, setBackendsLoading] = useState(false);

    const activeBackend = backends.find(b => b.backend_id === selectedBackend);
    const canPreview = activeBackend?.has_preview ?? (selectedBackend === 'template-picker');
    const isTopazBackend = selectedBackend.replace('_', '-').toLowerCase().includes('topaz');
    const { events: dispatchEvents, connected: socketConnected } = useJobStepEvents(dispatchJobId);
    const latestDispatchEvent = dispatchEvents[dispatchEvents.length - 1];
    const latestProgressEvent = [...dispatchEvents].reverse().find((e) => e.type === 'magellon.step.progress');
    const dispatchPercent = (latestProgressEvent?.data as any)?.percent;
    const dispatchMessage =
        (latestDispatchEvent?.data as any)?.message ||
        (latestProgressEvent?.data as any)?.message ||
        (latestDispatchEvent?.data as any)?.error ||
        'Task queued';
    const dispatchCompleted = dispatchEvents.some((e) => e.type === 'magellon.step.completed');
    const dispatchFailed = dispatchEvents.some((e) => e.type === 'magellon.step.failed');

    // GPFS picker state — driven by the SchemaForm's onBrowseFile
    // callback. Same pattern the plugin test panel uses; templates
    // path field gets the picker for free since template_paths is in
    // the schema's file_path heuristic whitelist.
    const [pickerRequest, setPickerRequest] = useState<BrowseFileRequest | null>(null);
    const handleBrowseFile = useCallback(
        (req: BrowseFileRequest) => setPickerRequest(req),
        [],
    );
    const retuneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Sync external running state
    useEffect(() => {
        if (isRunning && drawerState !== 'running' && drawerState !== 'dispatched') setDrawerState('running');
        if (!isRunning && drawerState === 'running') setDrawerState(resultCount !== null ? 'results' : 'configure');
        if (!isRunning && drawerState === 'dispatched') setDrawerState('configure');
    }, [isRunning, resultCount]);

    // Load live backends
    useEffect(() => {
        if (!open) return;
        setBackendsLoading(true);
        fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/backends`)
            .then((res) => res.ok ? res.json() : Promise.resolve([]))
            .then((data: BackendInfo[]) => {
                // Topaz always sorts to the top; otherwise preserve server order.
                const isTopaz = (id: string) => id === 'topaz-particle-picking' || id === 'topaz';
                const sorted = [...data].sort((a, b) => {
                    if (isTopaz(a.backend_id)) return -1;
                    if (isTopaz(b.backend_id)) return 1;
                    return 0;
                });
                setBackends(sorted);
                // Auto-select topaz if live; else first available; else keep current.
                const topazLive = sorted.find(b => isTopaz(b.backend_id));
                if (topazLive) {
                    setSelectedBackend(topazLive.backend_id);
                } else if (sorted.length > 0 && !sorted.find(b => b.backend_id === selectedBackend)) {
                    setSelectedBackend(sorted[0].backend_id);
                }
            })
            .catch(() => { /* backends endpoint optional — fall back to template-picker */ })
            .finally(() => setBackendsLoading(false));
    }, [open]);

    // Fetch schema (re-fetch when backend changes)
    useEffect(() => {
        if (!open) return;
        setSchema(null);
        setSchemaLoading(true);
        const url = `${API_URL}${TEMPLATE_PICKER_PATH}/schema/input?backend=${encodeURIComponent(selectedBackend)}`;
        fetch(url)
            .then((res) => { if (!res.ok) throw new Error(`${res.status}`); return res.json(); })
            .then((data) => {
                setSchema(data);
                setSchemaError(null);
                if (selectedBackend.replace('_', '-').toLowerCase().includes('topaz')) {
                    onPickerParamsChange({
                        model: 'resnet16',
                        threshold: -3.0,
                        radius: 14,
                        scale: 8,
                    });
                }
            })
            .catch((err) => setSchemaError(`Could not load: ${err.message}`))
            .finally(() => setSchemaLoading(false));
    }, [open, selectedBackend]);

    const validationErrors = useMemo(
        () => (schema ? validateParams(schema, pickerParams, imageName) : []),
        [schema, pickerParams, imageName],
    );
    const isValid = validationErrors.length === 0;

    // --- Preview ---
    const handlePreview = useCallback(async () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        setRuntimeError(null);
        setDrawerState('previewing');

        try {
            const payload: Record<string, any> = {
                ...pickerParams,
                image_path: imageName,
                backend: selectedBackend,
                session_name: sessionName,
            };
            Object.keys(payload).forEach(k => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; });

            const res = await fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
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

            const pts: Point[] = (data.particles || []).map((p: any, i: number) => ({
                x: p.x, y: p.y, id: `preview-${Date.now()}-${i}`,
                type: 'auto' as const,
                confidence: Math.min(p.score, 1.0),
                class: p.score >= (pickerParams.threshold ?? 0.4) ? '1' : '4',
                timestamp: Date.now(),
            }));
            onPreviewParticles(pts);
            setDrawerState('preview');
        } catch (err: any) {
            setDrawerState('configure');
            setRuntimeError(`Preview failed: ${err.message}`);
        }
    }, [isValid, pickerParams, imageName, onPreviewParticles]);

    // --- Retune (debounced) ---
    const handleRetune = useCallback((newParams: Record<string, any>) => {
        onPickerParamsChange(newParams);
        if (!previewId) return;

        if (retuneTimer.current) clearTimeout(retuneTimer.current);
        retuneTimer.current = setTimeout(async () => {
            setRetuning(true);
            try {
                const retuneUrl = `${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}/retune`
                    + `?backend=${encodeURIComponent(selectedBackend)}`;
                const res = await fetch(retuneUrl, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        threshold: newParams.threshold ?? 0.4,
                        radius: newParams.radius ?? null,
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
                    const pts: Point[] = (data.particles || []).map((p: any, i: number) => ({
                        x: p.x, y: p.y, id: `retune-${Date.now()}-${i}`,
                        type: 'auto' as const,
                        confidence: Math.min(p.score, 1.0),
                        class: p.score >= (newParams.threshold ?? 0.4) ? '1' : '4',
                        timestamp: Date.now(),
                    }));
                    onPreviewParticles(pts);
                }
            } catch { /* ignore */ }
            setRetuning(false);
        }, 300);
    }, [previewId, onPreviewParticles, onPickerParamsChange]);

    // --- Run (RMQ dispatch) ---
    const handleRun = async () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        if (previewId) {
            fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}?backend=${encodeURIComponent(selectedBackend)}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        const name = ippName || `Auto-pick ${new Date().toISOString().slice(0, 16)}`;
        setDrawerState('dispatched');
        const result = await onDispatch(selectedBackend, name);
        if (result?.job_id) {
            setDispatchJobId(result.job_id);
        } else {
            setDrawerState('configure');
        }
    };

    // --- Accept / Discard ---
    const handleAccept = () => {
        if (previewId) {
            fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}?backend=${encodeURIComponent(selectedBackend)}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        setScoreMapPng(null);
        onAcceptParticles();
        setDrawerState('configure');
    };

    const handleDiscard = () => {
        if (previewId) {
            fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/preview/${previewId}?backend=${encodeURIComponent(selectedBackend)}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        setScoreMapPng(null);
        onDiscardParticles();
        setDrawerState('configure');
    };

    if (!open) return null;

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* ============ TOOLBAR ============ */}
            <Box sx={{
                px: 1.5, py: 1,
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: alpha(theme.palette.primary.main, 0.03),
                flexShrink: 0,
            }}>
                {/* Title row */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    {(drawerState === 'preview' || drawerState === 'results') && (
                        <IconButton size="small" onClick={handleDiscard} sx={{ mr: 0.5 }}>
                            <BackIcon fontSize="small" />
                        </IconButton>
                    )}
                    <Typography
                        variant="caption"
                        sx={{
                            fontWeight: 600,
                            flex: 1
                        }}>
                        {{
                            configure: 'Algorithm Settings',
                            previewing: 'Computing Preview...',
                            preview: 'Preview & Tune',
                            running: 'Running...',
                            dispatched: 'Task Queued',
                            results: 'Results',
                        }[drawerState]}
                    </Typography>
                    {schema && drawerState === 'configure' && (
                        <Chip label={selectedBackend} size="small" variant="outlined" sx={{ fontSize: '0.6rem', height: 20 }} />
                    )}
                </Box>

                {/* Backend selector — shown in configure state */}
                {drawerState === 'configure' && (
                    <FormControl fullWidth size="small" sx={{ mb: 0.75 }}>
                        <Select
                            value={selectedBackend}
                            onChange={(e) => {
                                setSelectedBackend(e.target.value);
                                setSchema(null); // will re-fetch for new backend
                            }}
                            displayEmpty
                            sx={{ fontSize: '0.75rem', height: 28 }}
                        >
                            {backends.length === 0 && (
                                <MenuItem value="topaz-particle-picking" sx={{ fontSize: '0.75rem' }}>
                                    topaz-particle-picking
                                </MenuItem>
                            )}
                            {backends.map(b => (
                                <MenuItem key={b.backend_id} value={b.backend_id} sx={{ fontSize: '0.75rem' }}>
                                    {b.label}
                                    {b.has_preview && <Chip label="preview" size="small" sx={{ ml: 1, fontSize: '0.6rem', height: 16 }} />}
                                </MenuItem>
                            ))}
                            {backendsLoading && (
                                <MenuItem disabled sx={{ fontSize: '0.75rem' }}>
                                    <CircularProgress size={12} sx={{ mr: 1 }} /> Loading…
                                </MenuItem>
                            )}
                        </Select>
                    </FormControl>
                )}

                {/* CONFIGURE: Preview + Run + Run Batch */}
                {drawerState === 'configure' && (
                    <>
                        {!canPreview && (
                            <Alert severity="info" sx={{ mb: 0.75, py: 0.25, '& .MuiAlert-message': { fontSize: '0.7rem' } }}>
                                {isTopazBackend
                                    ? 'Topaz currently runs as a queued job and saves an IPP record when it finishes. No-save preview is not available for this backend yet.'
                                    : 'This backend does not advertise no-save preview; running will save an IPP record.'}
                            </Alert>
                        )}
                        {canPreview && (
                            <Button
                                variant="outlined" size="small" fullWidth
                                startIcon={<PreviewIcon sx={{ fontSize: 14 }} />} onClick={handlePreview}
                                sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, mb: 0.75 }}
                            >
                                Preview &amp; tune (no save)
                            </Button>
                        )}
                        <Box sx={{ display: 'flex', gap: 0.75 }}>
                            <Button
                                variant="contained" size="small" fullWidth
                                startIcon={<DispatchIcon sx={{ fontSize: 14 }} />} onClick={handleRun}
                                sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5 }}
                            >
                                {canPreview ? 'Save current image' : 'Run and save image'}
                            </Button>
                            {onRunBatch && (
                                <Button
                                    variant="outlined" size="small" fullWidth
                                    startIcon={<BatchIcon sx={{ fontSize: 14 }} />}
                                    onClick={() => {
                                        if (!isValid) { setShowErrors(true); return; }
                                        setShowErrors(false);
                                        onRunBatch();
                                    }}
                                    sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5 }}
                                >
                                    Run batch…
                                </Button>
                            )}
                        </Box>
                        <Box sx={{ mt: 0.75, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            {isValid ? (
                                <><ValidIcon sx={{ fontSize: 12, color: 'success.main' }} /><Typography
                                    variant="caption"
                                    sx={{
                                        color: "success.main",
                                        fontSize: '0.7rem'
                                    }}>Ready</Typography></>
                            ) : (
                                <><ErrorIcon sx={{ fontSize: 12, color: 'warning.main' }} />
                                <Typography
                                    variant="caption"
                                    onClick={() => setShowErrors(!showErrors)}
                                    sx={{
                                        color: "warning.main",
                                        cursor: 'pointer',
                                        textDecoration: 'underline',
                                        fontSize: '0.7rem'
                                    }}>
                                    {validationErrors.length} issue{validationErrors.length !== 1 ? 's' : ''}
                                </Typography></>
                            )}
                        </Box>
                    </>
                )}

                {/* PREVIEW: pick count + actions */}
                {drawerState === 'preview' && (
                    <>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <TuneIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                            <Typography variant="caption"><strong>{previewCount}</strong> particles</Typography>
                            {retuning && <CircularProgress size={12} />}
                        </Box>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                            <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon sx={{ fontSize: 12 }} />}
                                onClick={handleDiscard} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                                Discard
                            </Button>
                            <Button variant="outlined" size="small" startIcon={<RunIcon sx={{ fontSize: 12 }} />}
                                onClick={handleRun} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                                Run
                            </Button>
                            <Button variant="contained" size="small" startIcon={<AcceptIcon sx={{ fontSize: 12 }} />}
                                onClick={handleAccept} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                                Accept
                            </Button>
                        </Box>
                    </>
                )}

                {/* RUNNING — indeterminate: the sync endpoint doesn't stream
                    progress, and showing a fake 0→100 was misleading. */}
                {drawerState === 'running' && (
                    <Box sx={{ mt: 0.5 }}>
                        <LinearProgress sx={{ height: 4, borderRadius: 1 }} />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 0.5,
                                display: 'block',
                                fontSize: '0.7rem'
                            }}>
                            Running...
                        </Typography>
                    </Box>
                )}

                {/* DISPATCHED — task sent to RMQ, polling for result */}
                {drawerState === 'dispatched' && (
                    <Box sx={{ mt: 0.5 }}>
                        <LinearProgress
                            variant={typeof dispatchPercent === 'number' ? 'determinate' : 'indeterminate'}
                            value={typeof dispatchPercent === 'number' ? dispatchPercent : undefined}
                            color={dispatchFailed ? 'error' : dispatchCompleted ? 'success' : 'primary'}
                            sx={{ height: 4, borderRadius: 1 }}
                        />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 0.5,
                                display: 'block',
                                fontSize: '0.7rem'
                            }}>
                            {dispatchFailed
                                ? `Failed: ${dispatchMessage}`
                                : dispatchCompleted
                                    ? 'Plugin finished - loading saved picks...'
                                    : dispatchMessage}
                            {typeof dispatchPercent === 'number' ? ` (${Math.round(dispatchPercent)}%)` : ''}
                        </Typography>
                        <Chip
                            size="small"
                            variant="outlined"
                            label={socketConnected ? 'socket live' : 'socket connecting'}
                            sx={{ mt: 0.5, height: 18, fontSize: '0.62rem' }}
                        />
                    </Box>
                )}

                {/* RESULTS */}
                {drawerState === 'results' && (
                    <>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <ValidIcon sx={{ fontSize: 16, color: 'success.main' }} />
                            <Typography variant="caption"><strong>{resultCount ?? 0}</strong> particles picked</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                            <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon sx={{ fontSize: 12 }} />}
                                onClick={handleDiscard} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                                Discard
                            </Button>
                            <Button variant="contained" size="small" startIcon={<AcceptIcon sx={{ fontSize: 12 }} />}
                                onClick={handleAccept} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                                Accept
                            </Button>
                        </Box>
                    </>
                )}

                {/* PREVIEWING spinner */}
                {drawerState === 'previewing' && (
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <CircularProgress size={20} />
                    </Box>
                )}
            </Box>
            {/* ============ VALIDATION ERRORS ============ */}
            <Collapse in={showErrors && validationErrors.length > 0 && drawerState === 'configure'}>
                <Box sx={{ px: 1.5, pt: 1 }}>
                    <Alert severity="warning" sx={{ py: 0.25, '& .MuiAlert-message': { fontSize: '0.7rem' } }}>
                        <AlertTitle sx={{ fontSize: '0.75rem', mb: 0.25 }}>Fix before running</AlertTitle>
                        {validationErrors.map((err, i) => (
                            <Typography
                                key={i}
                                variant="caption"
                                sx={{
                                    display: "block",
                                    lineHeight: 1.5,
                                    fontSize: '0.7rem'
                                }}>• {err}</Typography>
                        ))}
                    </Alert>
                </Box>
            </Collapse>
            {/* ============ BODY (scrollable) ============ */}
            <Box sx={{ flex: 1, overflow: 'auto', px: 1.5, py: 1 }}>

                {schemaLoading && (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <CircularProgress size={24} />
                        <Typography
                            variant="caption"
                            sx={{
                                display: "block",
                                color: "text.secondary",
                                mt: 1
                            }}>Loading...</Typography>
                    </Box>
                )}

                {schemaError && (
                    <Box sx={{ p: 1.5, borderRadius: 1, mb: 1, backgroundColor: alpha(theme.palette.error.main, 0.08) }}>
                        <Typography variant="caption" color="error">{schemaError}</Typography>
                        <Typography
                            variant="caption"
                            sx={{
                                display: "block",
                                color: "text.secondary",
                                mt: 0.5
                            }}>
                            Backend: {API_URL}
                        </Typography>
                    </Box>
                )}

                {runtimeError && (
                    <Alert
                        severity="error"
                        onClose={() => setRuntimeError(null)}
                        sx={{ mb: 1, py: 0.5, '& .MuiAlert-message': { fontSize: '0.75rem' } }}
                    >
                        {runtimeError}
                    </Alert>
                )}

                {/* CONFIGURE: full form */}
                {drawerState === 'configure' && schema && (
                    <SchemaForm schema={schema} values={pickerParams} onChange={onPickerParamsChange}
                        defaultExpanded={['Templates', 'Auto-picking Settings', 'Topaz']} collapseAdvanced
                        onBrowseFile={handleBrowseFile} />
                )}

                {/* PREVIEW: score map + tunable sliders */}
                {drawerState === 'preview' && schema && (
                    <>
                        {scoreMapPng && (
                            <Box sx={{ mb: 1.5, borderRadius: 1, overflow: 'hidden', border: `1px solid ${theme.palette.divider}` }}>
                                <img src={`data:image/png;base64,${scoreMapPng}`} alt="Score map" style={{ width: '100%', display: 'block' }} />
                                <Typography
                                    variant="caption"
                                    sx={{
                                        color: "text.secondary",
                                        px: 1,
                                        py: 0.25,
                                        display: 'block',
                                        fontSize: '0.65rem'
                                    }}>
                                    Correlation map — brighter = higher match
                                </Typography>
                            </Box>
                        )}
                        <Typography
                            variant="caption"
                            sx={{
                                fontWeight: 600,
                                display: 'block',
                                mb: 0.5,
                                fontSize: '0.7rem'
                            }}>
                            Tune parameters:
                        </Typography>
                        <SchemaForm schema={schema} values={pickerParams} onChange={handleRetune}
                            tunableOnly={true} defaultExpanded={['Auto-picking Settings', 'Advanced', 'Topaz']}
                            onBrowseFile={handleBrowseFile} />
                    </>
                )}

                {/* RUNNING */}
                {drawerState === 'running' && (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                        <CircularProgress size={32} />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 1.5,
                                display: 'block'
                            }}>
                            Running template matching...
                        </Typography>
                    </Box>
                )}

                {/* DISPATCHED — task queued via RMQ */}
                {drawerState === 'dispatched' && (
                    <Box sx={{ py: 3 }}>
                        <LinearProgress
                            variant={typeof dispatchPercent === 'number' ? 'determinate' : 'indeterminate'}
                            value={typeof dispatchPercent === 'number' ? dispatchPercent : undefined}
                            color={dispatchFailed ? 'error' : dispatchCompleted ? 'success' : 'primary'}
                            sx={{ height: 6, borderRadius: 1 }}
                        />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 1,
                                display: 'block'
                            }}>
                            <strong>{selectedBackend}</strong><br />
                            {dispatchFailed
                                ? `Failed: ${dispatchMessage}`
                                : dispatchCompleted
                                    ? 'Plugin finished. Waiting for the saved IPP record to appear.'
                                    : dispatchMessage}
                            {typeof dispatchPercent === 'number' ? ` (${Math.round(dispatchPercent)}%)` : ''}
                        </Typography>
                        <Chip
                            size="small"
                            variant="outlined"
                            label={socketConnected ? 'socket live' : 'socket connecting'}
                            sx={{ mt: 1, height: 20, fontSize: '0.68rem' }}
                        />
                    </Box>
                )}

                {/* RESULTS */}
                {drawerState === 'results' && (
                    <Box sx={{ py: 1 }}>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            {resultCount} particles detected. Click <strong>Accept</strong> to keep or <strong>Discard</strong> to remove.
                        </Typography>
                    </Box>
                )}
            </Box>

            {/* GPFS browser dialog — opens when SchemaForm's file_path /
                file_path_list widgets request a browse. Templates path
                field qualifies via the heuristic in the shared SchemaForm
                (template_paths in FILE_PATH_FIELD_NAMES). */}
            {pickerRequest && (
                pickerRequest.multiple ? (
                    <ImagePickerDialog
                        open
                        multiple
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(paths) => {
                            pickerRequest.onPick(paths);
                            setPickerRequest(null);
                        }}
                    />
                ) : (
                    <ImagePickerDialog
                        open
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(path) => {
                            pickerRequest.onPick(path);
                            setPickerRequest(null);
                        }}
                    />
                )
            )}
        </Box>
    );
};

// Backward-compat export name
export const ParticleSettingsDrawer = ParticleSettingsPanel;
