import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import {
    Box,
    Typography,
    Drawer,
    CircularProgress,
    Chip,
    Button,
    Alert,
    AlertTitle,
    Collapse,
    Divider,
    Tooltip,
    LinearProgress,
    IconButton,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Visibility as PreviewIcon,
    PlayArrow as RunIcon,
    ErrorOutline as ErrorIcon,
    CheckCircle as ValidIcon,
    ArrowBack as BackIcon,
    Check as AcceptIcon,
    Close as DiscardIcon,
    Tune as TuneIcon,
} from '@mui/icons-material';
import { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import { settings as appSettings } from '../../../shared/config/settings.ts';
import { Point } from '../lib/useParticleOperations.ts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DrawerState = 'configure' | 'previewing' | 'preview' | 'running' | 'results';

export interface ParticleSettingsDrawerProps {
    open: boolean;
    onClose: () => void;
    pickerParams: Record<string, any>;
    onPickerParamsChange: (params: Record<string, any>) => void;
    /** Called when user clicks Run — should trigger the full pick */
    onRun: () => void;
    isRunning: boolean;
    /** Called when preview or retune produces particles to show on canvas */
    onPreviewParticles: (particles: Point[]) => void;
    /** Called when user accepts picks from preview or results */
    onAcceptParticles: () => void;
    /** Called when user discards preview picks */
    onDiscardParticles: () => void;
    imageName: string | null;
    /** Auto-picking progress (0-100) while running */
    autoPickingProgress: number;
    /** Result particle count (set after run completes) */
    resultCount: number | null;
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
// Component
// ---------------------------------------------------------------------------

const API_URL = appSettings.ConfigData.SERVER_API_URL;

export const ParticleSettingsDrawer: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    onClose,
    pickerParams,
    onPickerParamsChange,
    onRun,
    isRunning,
    onPreviewParticles,
    onAcceptParticles,
    onDiscardParticles,
    imageName,
    autoPickingProgress,
    resultCount,
}) => {
    const theme = useTheme();
    const [schema, setSchema] = useState<any>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);
    const [showErrors, setShowErrors] = useState(false);
    const [drawerState, setDrawerState] = useState<DrawerState>('configure');
    const [previewId, setPreviewId] = useState<string | null>(null);
    const [previewCount, setPreviewCount] = useState(0);
    const [scoreMapPng, setScoreMapPng] = useState<string | null>(null);
    const [retuning, setRetuning] = useState(false);
    const retuneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Sync external running state
    useEffect(() => {
        if (isRunning && drawerState !== 'running') setDrawerState('running');
        if (!isRunning && drawerState === 'running') setDrawerState(resultCount !== null ? 'results' : 'configure');
    }, [isRunning, resultCount]);

    // Fetch schema
    useEffect(() => {
        if (!open || schema) return;
        setSchemaLoading(true);
        fetch(`${API_URL}/plugins/pp/template-pick/schema/input`)
            .then((res) => { if (!res.ok) throw new Error(`${res.status}`); return res.json(); })
            .then((data) => { setSchema(data); setSchemaError(null); })
            .catch((err) => setSchemaError(`Could not load: ${err.message}`))
            .finally(() => setSchemaLoading(false));
    }, [open, schema]);

    const validationErrors = useMemo(
        () => (schema ? validateParams(schema, pickerParams, imageName) : []),
        [schema, pickerParams, imageName],
    );
    const isValid = validationErrors.length === 0;

    // --- Preview flow ---
    const handlePreview = useCallback(async () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        setDrawerState('previewing');

        try {
            const payload = { ...pickerParams, image_path: imageName };
            Object.keys(payload).forEach(k => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; });

            const res = await fetch(`${API_URL}/plugins/pp/template-pick/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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

            // Push particles to canvas
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
            setSchemaError(`Preview failed: ${err.message}`);
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
                const res = await fetch(`${API_URL}/plugins/pp/template-pick/preview/${previewId}/retune`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        threshold: newParams.threshold ?? 0.4,
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
            } catch { /* ignore retune errors */ }
            setRetuning(false);
        }, 300);
    }, [previewId, onPreviewParticles, onPickerParamsChange]);

    // --- Run ---
    const handleRun = () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        // Clean up preview if active
        if (previewId) {
            fetch(`${API_URL}/plugins/pp/template-pick/preview/${previewId}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        setDrawerState('running');
        onRun();
    };

    // --- Accept / Discard ---
    const handleAccept = () => {
        if (previewId) {
            fetch(`${API_URL}/plugins/pp/template-pick/preview/${previewId}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        setScoreMapPng(null);
        onAcceptParticles();
        setDrawerState('configure');
    };

    const handleDiscard = () => {
        if (previewId) {
            fetch(`${API_URL}/plugins/pp/template-pick/preview/${previewId}`, { method: 'DELETE' }).catch(() => {});
            setPreviewId(null);
        }
        setScoreMapPng(null);
        onDiscardParticles();
        setDrawerState('configure');
    };

    const handleBack = () => {
        handleDiscard();
    };

    // Use persistent variant in preview mode so user sees the micrograph
    const isPersistent = drawerState === 'preview' || drawerState === 'results';

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={drawerState === 'running' ? undefined : onClose}
            variant={isPersistent ? 'persistent' : 'temporary'}
            hideBackdrop={isPersistent}
            sx={{
                '& .MuiDrawer-paper': {
                    width: 360,
                    boxShadow: isPersistent ? '-4px 0 12px rgba(0,0,0,0.08)' : undefined,
                },
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

                {/* ============ TOOLBAR (always visible) ============ */}
                <Box sx={{
                    px: 2, py: 1.5,
                    borderBottom: `1px solid ${theme.palette.divider}`,
                    backgroundColor: alpha(theme.palette.primary.main, 0.03),
                    mt: '64px', // below AppBar
                }}>
                    {/* Title row */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        {(drawerState === 'preview' || drawerState === 'results') && (
                            <IconButton size="small" onClick={handleBack} sx={{ mr: 0.5 }}>
                                <BackIcon fontSize="small" />
                            </IconButton>
                        )}
                        <Typography variant="subtitle1" fontWeight={600} sx={{ flex: 1 }}>
                            {{
                                configure: 'Algorithm Settings',
                                previewing: 'Computing Preview...',
                                preview: 'Preview & Tune',
                                running: 'Running...',
                                results: 'Results',
                            }[drawerState]}
                        </Typography>
                        {schema && drawerState === 'configure' && (
                            <Chip label="template-picker" size="small" variant="outlined" sx={{ fontSize: '0.65rem', height: 22 }} />
                        )}
                    </Box>

                    {/* ---- CONFIGURE state: Preview + Run buttons ---- */}
                    {drawerState === 'configure' && (
                        <>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Tooltip title="Compute maps and preview picks without committing">
                                    <span style={{ flex: 1 }}>
                                        <Button variant="outlined" size="small" fullWidth
                                            startIcon={<PreviewIcon />} onClick={handlePreview}
                                            sx={{ textTransform: 'none' }}>
                                            Preview
                                        </Button>
                                    </span>
                                </Tooltip>
                                <Tooltip title="Run auto-picking and commit particles">
                                    <span style={{ flex: 1 }}>
                                        <Button variant="contained" size="small" fullWidth
                                            startIcon={<RunIcon />} onClick={handleRun}
                                            sx={{ textTransform: 'none' }}>
                                            Run
                                        </Button>
                                    </span>
                                </Tooltip>
                            </Box>
                            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                {isValid ? (
                                    <><ValidIcon sx={{ fontSize: 14, color: 'success.main' }} /><Typography variant="caption" color="success.main">Ready</Typography></>
                                ) : (
                                    <><ErrorIcon sx={{ fontSize: 14, color: 'warning.main' }} />
                                    <Typography variant="caption" color="warning.main" sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                                        onClick={() => setShowErrors(!showErrors)}>
                                        {validationErrors.length} issue{validationErrors.length !== 1 ? 's' : ''}
                                    </Typography></>
                                )}
                            </Box>
                        </>
                    )}

                    {/* ---- PREVIEW state: pick count + Accept/Run/Discard ---- */}
                    {drawerState === 'preview' && (
                        <>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <TuneIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                                <Typography variant="body2">
                                    <strong>{previewCount}</strong> particles detected
                                </Typography>
                                {retuning && <CircularProgress size={14} />}
                            </Box>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon />}
                                    onClick={handleDiscard} sx={{ textTransform: 'none', flex: 1 }}>
                                    Discard
                                </Button>
                                <Button variant="outlined" size="small" startIcon={<RunIcon />}
                                    onClick={handleRun} sx={{ textTransform: 'none', flex: 1 }}>
                                    Run Full
                                </Button>
                                <Button variant="contained" size="small" startIcon={<AcceptIcon />}
                                    onClick={handleAccept} sx={{ textTransform: 'none', flex: 1 }}>
                                    Accept
                                </Button>
                            </Box>
                        </>
                    )}

                    {/* ---- RUNNING state: progress ---- */}
                    {drawerState === 'running' && (
                        <Box sx={{ mt: 1 }}>
                            <LinearProgress variant="determinate" value={autoPickingProgress} sx={{ height: 6, borderRadius: 1 }} />
                            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                                {autoPickingProgress}% complete
                            </Typography>
                        </Box>
                    )}

                    {/* ---- RESULTS state: summary + accept/discard ---- */}
                    {drawerState === 'results' && (
                        <>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <ValidIcon sx={{ fontSize: 18, color: 'success.main' }} />
                                <Typography variant="body2">
                                    <strong>{resultCount ?? 0}</strong> particles picked
                                </Typography>
                            </Box>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon />}
                                    onClick={handleDiscard} sx={{ textTransform: 'none', flex: 1 }}>
                                    Discard
                                </Button>
                                <Button variant="contained" size="small" startIcon={<AcceptIcon />}
                                    onClick={handleAccept} sx={{ textTransform: 'none', flex: 1 }}>
                                    Accept
                                </Button>
                            </Box>
                        </>
                    )}

                    {/* ---- PREVIEWING state: spinner ---- */}
                    {drawerState === 'previewing' && (
                        <Box sx={{ textAlign: 'center', py: 1 }}>
                            <CircularProgress size={24} />
                        </Box>
                    )}
                </Box>

                {/* ============ VALIDATION ERRORS ============ */}
                <Collapse in={showErrors && validationErrors.length > 0 && drawerState === 'configure'}>
                    <Box sx={{ px: 2, pt: 1 }}>
                        <Alert severity="warning" sx={{ py: 0.5, '& .MuiAlert-message': { fontSize: '0.75rem' } }}>
                            <AlertTitle sx={{ fontSize: '0.8rem', mb: 0.5 }}>Fix before running</AlertTitle>
                            {validationErrors.map((err, i) => (
                                <Typography key={i} variant="caption" display="block" sx={{ lineHeight: 1.6 }}>• {err}</Typography>
                            ))}
                        </Alert>
                    </Box>
                </Collapse>

                {/* ============ BODY ============ */}
                <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5 }}>

                    {/* --- Loading schema --- */}
                    {schemaLoading && (
                        <Box sx={{ textAlign: 'center', py: 6 }}>
                            <CircularProgress size={28} />
                            <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1.5 }}>
                                Loading settings from backend...
                            </Typography>
                        </Box>
                    )}

                    {schemaError && (
                        <Box sx={{ p: 2, borderRadius: 1, mb: 2, backgroundColor: alpha(theme.palette.error.main, 0.08) }}>
                            <Typography variant="caption" color="error">{schemaError}</Typography>
                            <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                                Backend: {API_URL}
                            </Typography>
                        </Box>
                    )}

                    {/* --- CONFIGURE: full form --- */}
                    {drawerState === 'configure' && schema && (
                        <SchemaForm
                            schema={schema}
                            values={pickerParams}
                            onChange={onPickerParamsChange}
                            defaultExpanded={['Templates', 'Auto-picking Settings']}
                            collapseAdvanced
                        />
                    )}

                    {/* --- PREVIEW: score map + tunable sliders --- */}
                    {drawerState === 'preview' && schema && (
                        <>
                            {scoreMapPng && (
                                <Box sx={{ mb: 2, borderRadius: 1, overflow: 'hidden', border: `1px solid ${theme.palette.divider}` }}>
                                    <img
                                        src={`data:image/png;base64,${scoreMapPng}`}
                                        alt="Score map"
                                        style={{ width: '100%', display: 'block' }}
                                    />
                                    <Typography variant="caption" color="text.secondary" sx={{ px: 1, py: 0.5, display: 'block' }}>
                                        Correlation score map — brighter = higher match
                                    </Typography>
                                </Box>
                            )}
                            <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                                Adjust tunable parameters:
                            </Typography>
                            <SchemaForm
                                schema={schema}
                                values={pickerParams}
                                onChange={handleRetune}
                                tunableOnly={true}
                                defaultExpanded={['Auto-picking Settings', 'Advanced']}
                            />
                        </>
                    )}

                    {/* --- RUNNING: just the progress message --- */}
                    {drawerState === 'running' && (
                        <Box sx={{ textAlign: 'center', py: 4 }}>
                            <CircularProgress size={40} />
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                                Running template matching...
                            </Typography>
                        </Box>
                    )}

                    {/* --- RESULTS: summary --- */}
                    {drawerState === 'results' && (
                        <Box sx={{ py: 2 }}>
                            <Typography variant="body2" gutterBottom>
                                Auto-picking completed successfully.
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {resultCount} particles detected and placed on the canvas.
                                Click <strong>Accept</strong> to keep them, or <strong>Discard</strong> to remove.
                            </Typography>
                        </Box>
                    )}
                </Box>
            </Box>
        </Drawer>
    );
};
