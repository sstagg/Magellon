import React, { useState, useEffect, useCallback } from 'react';
import type {
    SelectChangeEvent} from '@mui/material';
import {
    Box,
    Paper,
    Stack,
    Alert,
    Snackbar,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    LinearProgress,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import {
    Save as SaveIcon,
    Download as DownloadIcon,
    Upload as UploadIcon,
    AutoFixHigh as AutoFixHighIcon,
    Close as CloseIcon,
    CheckCircle as CheckCircleIcon,
    Help as HelpIcon,
} from '@mui/icons-material';
import { Circle } from 'lucide-react';
import { ParticleSessionDialog } from './ParticleSessionDialog.tsx';
import type ImageInfoDto from '../../../entities/image/types.ts';
import type { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import { settings } from '../../../shared/config/settings.ts';
import type { Point, ParticleClass, Tool } from '../lib/useParticleOperations.ts';
import { useParticleOperations } from '../lib/useParticleOperations.ts';
import { ParticleCanvas } from './ParticleCanvas.tsx';
import { ParticleToolbar } from './ParticleToolbar.tsx';
import { ParticleStatsBar } from './ParticleStatsBar.tsx';
import { ParticleSettingsPanel } from './ParticleSettingsDrawer.tsx';
import { ParticleHelpDialog } from './ParticleHelpDialog.tsx';
import { BatchRunDialog } from './BatchRunDialog.tsx';
import { useSidePanelStore } from '../../../shared/lib/stores/useBottomPanelStore.ts';
import { useSettingsPanelSlot } from '../../../shared/lib/stores/useSettingsPanelSlot.ts';
import { apiErrorMessage } from '../../../shared/api/apiError.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface ParticlePickingTabProps {
    selectedImage: ImageInfoDto | null;
    ImageParticlePickings: ParticlePickingDto[] | null;
    isIPPLoading: boolean;
    isIPPError: boolean;
    onParticlePickingLoad: () => void;
    OnIppSelected: (event: SelectChangeEvent) => void;
    handleSave: () => void;
    handleOpen: () => void;
    handleClose: () => void;
    handleIppUpdate: (ipp: ParticlePickingDto) => void;
}

export const ParticlePickingTab: React.FC<ParticlePickingTabProps> = ({
    selectedImage,
    ImageParticlePickings,
    isIPPLoading,
    isIPPError: _isIPPError,
    onParticlePickingLoad,
    OnIppSelected,
    handleSave,
    handleOpen,
    handleClose,
    handleIppUpdate
}) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const {
        selectedParticlePicking,
        isParticlePickingDialogOpen,
        currentSession
    } = useImageViewerStore();

    const sessionName = currentSession?.name || '';

    // UI-only state (display controls, not sent to backend)
    const [tool, setTool] = useState<Tool>('add');
    const [showGrid, setShowGrid] = useState(false);
    const [zoom, setZoom] = useState(1);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [helpOpen, setHelpOpen] = useState(false);
    const [batchDialogOpen, setBatchDialogOpen] = useState(false);
    const [activeClass, setActiveClass] = useState('1');
    const [customParticleRadius, setCustomParticleRadius] = useState<number | null>(null);

    const PARTICLE_OPACITY = 0.8;
    const SHOW_CROSSHAIR = true;
    const SHOW_STATS = true;

    // Settings panel — opens in the app-level SidePanelArea (same as Jobs/Logs)
    const { activePanel, togglePanel } = useSidePanelStore();
    const settingsOpen = activePanel === 'settings';
    // Subscribe to ONLY the (stable) store setters — never the `content`
    // value. Selecting the whole store made this tab re-render every time
    // it pushed content, a self-feedback edge that can amplify into a
    // render loop when combined with churning effect deps.
    const setContent = useSettingsPanelSlot((s) => s.setContent);
    const clearContent = useSettingsPanelSlot((s) => s.clearContent);

    // Algorithm parameters — single dict driven by schema. Defaults tuned so a
    // default "Run" completes in seconds, not minutes, on a typical micrograph.
    const [pickerParams, setPickerParams] = useState<Record<string, unknown>>({
        template_paths: [],
        image_pixel_size: 1.0,
        template_pixel_size: 2.646,
        diameter_angstrom: 220.0,
        threshold: 0.35,
        max_peaks: 500,
        bin_factor: 4,
        invert_templates: true,
        lowpass_resolution: 12.0,
    });

    // Auto-fill image_pixel_size from the selected image's metadata when known.
    useEffect(() => {
        const apix = (selectedImage as { pixelSize?: number })?.pixelSize;
        if (typeof apix === 'number' && apix > 0) {
            setPickerParams((prev) =>
                prev.image_pixel_size && prev.image_pixel_size !== 1.0
                    ? prev
                    : { ...prev, image_pixel_size: apix },
            );
        }
    }, [selectedImage?.oid]); // eslint-disable-line react-hooks/exhaustive-deps

    // Preview state — particles shown on canvas before committing
    const [previewParticles, setPreviewParticles] = useState<Point[] | null>(null);
    const [lastResultCount, setLastResultCount] = useState<number | null>(null);

    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
        open: false,
        message: '',
        severity: 'info'
    });

    const showSnackbar = (message: string, severity: 'success' | 'error' | 'info' | 'warning' = 'info') => {
        setSnackbar({ open: true, message, severity });
    };

    // Particle classes
    const [particleClasses, setParticleClasses] = useState<ParticleClass[]>([
        { id: '1', name: 'Good', color: '#4caf50', count: 0, visible: true, icon: <CheckCircleIcon fontSize="small" /> },
        { id: '2', name: 'Edge', color: '#ff9800', count: 0, visible: true, icon: <Circle size={16} /> },
        { id: '3', name: 'Contamination', color: '#f44336', count: 0, visible: true, icon: <CloseIcon fontSize="small" /> },
        { id: '4', name: 'Uncertain', color: '#9c27b0', count: 0, visible: true, icon: <HelpIcon fontSize="small" /> }
    ]);

    // Particle operations hook
    const {
        particles,
        selectedParticles,
        setSelectedParticles,
        history,
        historyIndex,
        copiedParticles,
        stats,
        isAutoPickingRunning,
        autoPickingProgress,
        imageShape,
        setImageShape,
        undo,
        redo,
        selectAll,
        deselectAll,
        deleteSelected,
        copySelected,
        pasteParticles,
        handleParticlesUpdate,
        exportParticles,
        importParticles,
        runAutoPicking,
        dispatchPick,
        sam2Click,
        isSam2Loading,
        sam2MaskPolygon,
    } = useParticleOperations({
        selectedParticlePicking,
        handleIppUpdate,
        selectedImage,
        sessionName,
        particleClasses,
        setParticleClasses,
        pickerParams,
        showSnackbar,
        onIppSaved: () => {
            // Refresh IPP list so the newly-saved record appears in the dropdown.
            onParticlePickingLoad();
        },
        onRefreshIppList: onParticlePickingLoad,
    });

    // Scale the default display radius to the coordinate space (reference: 15px at 1024 wide).
    const DEFAULT_PARTICLE_RADIUS = imageShape ? Math.round(imageShape[1] / 1024 * 15) : 15;
    const PARTICLE_RADIUS = customParticleRadius ?? DEFAULT_PARTICLE_RADIUS;
    const PARTICLE_RADIUS_MAX = imageShape ? Math.max(64, Math.round(imageShape[1] / 8)) : 256;

    useEffect(() => {
        setCustomParticleRadius(null);
    }, [selectedImage?.oid]);

    const handleParticleRadiusChange = useCallback((radius: number) => {
        const nextRadius = Math.max(4, Math.min(Math.round(radius), PARTICLE_RADIUS_MAX));
        setCustomParticleRadius(nextRadius);
        if (selectedParticles.size === 0) return;
        const updated = particles.map((p) =>
            selectedParticles.has(p.id || '') ? { ...p, radius: nextRadius } : p
        );
        handleParticlesUpdate(updated);
    }, [PARTICLE_RADIUS_MAX, selectedParticles, particles, handleParticlesUpdate]);

    // Global keyboard shortcuts — declared here so undo/redo/etc. are in scope
    const handleKeyDown = useCallback((e: KeyboardEvent) => {
        const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

        const ctrl = e.ctrlKey || e.metaKey;

        if (!ctrl && !e.shiftKey) {
            switch (e.key) {
                case '1': setTool('add'); break;
                case '2': setTool('remove'); break;
                case '3': setTool('select'); break;
                case '4': setTool('move'); break;
                case '5': setTool('box'); break;
                case '6': setTool('brush'); break;
                case 'l': case 'L': setTool('lasso'); break;
                case 's': case 'S': setTool('sam2'); break;
                case 'g': case 'G': setShowGrid((v) => !v); break;
                case 'h': case 'H': setHelpOpen(true); break;
                case '+': case '=': setZoom((z) => Math.min(z * 1.2, 5)); break;
                case '-': setZoom((z) => Math.max(z / 1.2, 0.2)); break;
                case '0': setZoom(1); break;
            }
        } else if (ctrl && !e.shiftKey) {
            switch (e.key.toLowerCase()) {
                case 'z': undo(); e.preventDefault(); break;
                case 'a': selectAll(); e.preventDefault(); break;
                case 'c': copySelected(); e.preventDefault(); break;
                case 'v': pasteParticles(); e.preventDefault(); break;
                case 's': handleSave(); e.preventDefault(); break;
            }
        } else if (ctrl && e.shiftKey) {
            if (e.key.toLowerCase() === 'z') { redo(); e.preventDefault(); }
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
            deleteSelected();
        }
    }, [undo, redo, selectAll, copySelected, pasteParticles, deleteSelected, handleSave]);

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    // Clear the side-panel slot only when the tab actually unmounts.
    // The previous pattern (cleanup → setContent on every dep change)
    // forced the panel to unmount and remount, blowing away its
    // internal state — including the `dispatchedIppName` that drives
    // the post-dispatch transition to the 'results' card.
    useEffect(() => clearContent, [clearContent]);

    // Push the latest panel JSX into the slot. setContent replaces the
    // stored node atomically, so React reconciles into the same panel
    // instance (state preserved) instead of remounting.
    useEffect(() => {
        setContent(
            <ParticleSettingsPanel
                open={settingsOpen}
                pickerParams={pickerParams}
                onPickerParamsChange={setPickerParams}
                onRun={runAutoPicking}
                onDispatch={(targetBackend, ippName) => dispatchPick({ targetBackend, ippName })}
                onRunBatch={sessionName ? () => setBatchDialogOpen(true) : undefined}
                isRunning={isAutoPickingRunning}
                onPreviewParticles={(pts) => {
                    setPreviewParticles(pts);
                    handleParticlesUpdate(pts);
                }}
                onAcceptParticles={() => {
                    setPreviewParticles(null);
                    setLastResultCount(null);
                    showSnackbar('Particles accepted', 'success');
                }}
                onDiscardParticles={() => {
                    const kept = particles.filter(p =>
                        !p.id?.startsWith('preview-') && !p.id?.startsWith('retune-')
                    );
                    handleParticlesUpdate(kept);
                    setPreviewParticles(null);
                    setLastResultCount(null);
                }}
                imageName={selectedImage?.name || null}
                sessionName={sessionName}
                autoPickingProgress={autoPickingProgress}
                resultCount={lastResultCount}
                ippName={selectedParticlePicking?.name}
                currentParticleCount={particles.length}
                currentParticles={particles}
            />
        );
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settingsOpen, pickerParams, isAutoPickingRunning, autoPickingProgress, lastResultCount,
        particles, selectedImage, previewParticles, sessionName, selectedParticlePicking?.name]);

    const handleExportCoco = async () => {
        if (!selectedParticlePicking?.oid) {
            showSnackbar('No picking record selected', 'warning');
            return;
        }
        try {
            const token = localStorage.getItem('access_token');
            const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
            const url = `${settings.ConfigData.SERVER_API_URL}/particle-picking/records/${selectedParticlePicking.oid}/coco?radius=${PARTICLE_RADIUS}`;
            const res = await fetch(url, { headers });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `Server error ${res.status}`);
            }
            const coco = await res.json();
            const dataUri = `data:application/json;charset=utf-8,${  encodeURIComponent(JSON.stringify(coco, null, 2))}`;
            const link = document.createElement('a');
            link.setAttribute('href', dataUri);
            const safeName = (selectedParticlePicking.name || 'picking').replace(/[^a-z0-9._-]+/gi, '_');
            link.setAttribute('download', `${safeName}.coco.json`);
            link.click();
            showSnackbar(`Exported ${coco.annotations?.length ?? 0} particles as COCO`, 'success');
        } catch (err) {
            showSnackbar(`COCO export failed: ${apiErrorMessage(err, 'unknown error')}`, 'error');
        }
    };

    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    };

    return (
        <Stack spacing={3} sx={{ height: '100%' }}>
            {/* Top Controls Bar */}
            <ParticleToolbar
                selectedParticlePicking={selectedParticlePicking}
                ImageParticlePickings={ImageParticlePickings}
                isIPPLoading={isIPPLoading}
                OnIppSelected={OnIppSelected}
                onRefresh={onParticlePickingLoad}
                onCreateNew={handleOpen}
                onSave={handleSave}
                onExportCoco={handleExportCoco}
                tool={tool}
                onToolChange={setTool}
                onUndo={undo}
                onRedo={redo}
                canUndo={historyIndex > 0}
                canRedo={historyIndex < history.length - 1}
                onSelectAll={selectAll}
                onCopy={copySelected}
                onPaste={pasteParticles}
                onDelete={deleteSelected}
                hasSelection={selectedParticles.size > 0}
                hasCopied={copiedParticles.length > 0}
                zoom={zoom}
                onZoomIn={() => setZoom(prev => Math.min(prev * 1.2, 5))}
                onZoomOut={() => setZoom(prev => Math.max(prev / 1.2, 0.2))}
                onZoomReset={() => setZoom(1)}
                showGrid={showGrid}
                onToggleGrid={() => setShowGrid(!showGrid)}
                onAutoPickRun={runAutoPicking}
                isAutoPickingRunning={isAutoPickingRunning}
                particleRadius={PARTICLE_RADIUS}
                particleRadiusMax={PARTICLE_RADIUS_MAX}
                onParticleRadiusChange={handleParticleRadiusChange}
                onSettingsOpen={() => togglePanel('settings')}
                onHelpOpen={() => setHelpOpen(true)}
                isMobile={isMobile}
                isFullscreen={isFullscreen}
                onToggleFullscreen={toggleFullscreen}
            />

            {/* Auto-picking Progress — indeterminate: the sync endpoint
                doesn't stream progress, and showing 0→100 was fake. */}
            {isAutoPickingRunning && (
                <LinearProgress sx={{ mb: 1 }} />
            )}

            {/* Main Canvas + Stats Sidebar */}
            <Paper
                elevation={2}
                sx={{
                    flex: 1,
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: theme.palette.grey[900],
                    borderRadius: 2,
                    display: 'flex',
                }}
            >
                {/* Stats Sidebar */}
                {SHOW_STATS && !isMobile && (
                    <ParticleStatsBar
                        stats={stats}
                        particleClasses={particleClasses}
                        activeClass={activeClass}
                        onActiveClassChange={setActiveClass}
                        selectedCount={selectedParticles.size}
                        onDeselectAll={deselectAll}
                    />
                )}

                <Box sx={{ flex: 1, minWidth: 0, height: '100%' }}>
                    <ParticleCanvas
                        imageUrl={
                            selectedImage?.name
                                ? `${BASE_URL}/image_thumbnail?name=${encodeURIComponent(selectedImage.name)}&sessionName=${encodeURIComponent(sessionName)}`
                                : ''
                        }
                        width={imageShape ? imageShape[1] : (isMobile ? 300 : 1024)}
                        height={imageShape ? imageShape[0] : (isMobile ? 300 : 1024)}
                        particles={particles}
                        selectedParticles={selectedParticles}
                        tool={tool}
                        particleRadius={PARTICLE_RADIUS}
                        particleOpacity={PARTICLE_OPACITY}
                        showGrid={showGrid}
                        showCrosshair={SHOW_CROSSHAIR}
                        zoom={zoom}
                        activeClass={activeClass}
                        particleClasses={particleClasses}
                        onParticlesUpdate={handleParticlesUpdate}
                        onSelectedParticlesUpdate={setSelectedParticles}
                        onShowSnackbar={showSnackbar}
                        onImageNaturalSize={(shape) => {
                            // Only fall back to the thumbnail's natural size
                            // when backend hasn't supplied image_shape yet.
                            if (!imageShape) setImageShape(shape);
                        }}
                        onSam2Click={sam2Click}
                        sam2MaskPolygon={sam2MaskPolygon}
                        isSam2Loading={isSam2Loading}
                    />
                </Box>

                {/* Floating Action Buttons */}
                <SpeedDial
                    ariaLabel="Particle picking actions"
                    sx={{ position: 'absolute', bottom: 16, right: 16 }}
                    icon={<SpeedDialIcon />}
                    direction={isMobile ? "up" : "left"}
                >
                    <SpeedDialAction
                        icon={<SaveIcon />}
                        title="Save (Ctrl+S)"
                        slotProps={{
                            fab: {
                                onClick: () => {
                                    handleSave();
                                    showSnackbar('Particles saved', 'success');
                                },
                            },
                        }}
                    />
                    <SpeedDialAction
                        icon={<DownloadIcon />}
                        title="Export Particles"
                        slotProps={{ fab: { onClick: exportParticles } }}
                    />
                    <SpeedDialAction
                        icon={
                            <>
                                <input
                                    type="file"
                                    accept=".json"
                                    onChange={importParticles}
                                    style={{ display: 'none' }}
                                    id="import-particles"
                                />
                                <label htmlFor="import-particles" style={{ cursor: 'pointer' }}>
                                    <UploadIcon />
                                </label>
                            </>
                        }
                        title="Import Particles"
                        slotProps={{
                            fab: {
                                onClick: () => document.getElementById('import-particles')?.click(),
                            },
                        }}
                    />
                    <SpeedDialAction
                        icon={<AutoFixHighIcon />}
                        title="Run Auto-picking"
                        slotProps={{ fab: { onClick: runAutoPicking } }}
                    />
                </SpeedDial>
            </Paper>

            {/* Settings panel content — registered into SidePanelArea slot */}

            {/* Help Dialog */}
            <ParticleHelpDialog
                open={helpOpen}
                onClose={() => setHelpOpen(false)}
            />

            {/* Batch Run Dialog */}
            <BatchRunDialog
                open={batchDialogOpen}
                onClose={() => setBatchDialogOpen(false)}
                sessionName={sessionName}
                currentImage={selectedImage}
                pickerParams={pickerParams}
                onComplete={(res) => {
                    showSnackbar(
                        `Batch complete — ${res.succeeded}/${res.total} succeeded`,
                        res.failed > 0 ? 'warning' : 'success',
                    );
                    onParticlePickingLoad();
                }}
            />

            {/* Particle Session Dialog */}
            <ParticleSessionDialog
                open={isParticlePickingDialogOpen}
                onClose={handleClose}
                ImageDto={selectedImage!}
            />

            {/* Snackbar for notifications */}
            <Snackbar
                open={snackbar.open}
                autoHideDuration={3000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            >
                <Alert
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                    severity={snackbar.severity}
                    sx={{ width: '100%' }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Stack>
    );
};
