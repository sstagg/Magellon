import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Stack,
    SelectChangeEvent,
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
import ImageInfoDto from '../../../entities/image/types.ts';
import { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import { settings } from '../../../shared/config/settings.ts';
import { Point, ParticleClass, Tool } from '../lib/useParticleOperations.ts';
import { useParticleOperations } from '../lib/useParticleOperations.ts';
import { ParticleCanvas } from './ParticleCanvas.tsx';
import { ParticleToolbar } from './ParticleToolbar.tsx';
import { ParticleStatsBar } from './ParticleStatsBar.tsx';
import { ParticleSettingsPanel } from './ParticleSettingsDrawer.tsx';
import { ParticleHelpDialog } from './ParticleHelpDialog.tsx';
import { useSidePanelStore } from '../../../app/layouts/PanelLayout/useBottomPanelStore.ts';
import { useSettingsPanelSlot } from '../../../app/layouts/PanelLayout/useSettingsPanelSlot.ts';

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
    isIPPError,
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
    const [particleRadius, setParticleRadius] = useState(15);
    const [particleOpacity, setParticleOpacity] = useState(0.8);
    const [showGrid, setShowGrid] = useState(false);
    const [showCrosshair, setShowCrosshair] = useState(true);
    const [showStats, setShowStats] = useState(true);
    const [zoom, setZoom] = useState(1);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [helpOpen, setHelpOpen] = useState(false);
    const [activeClass, setActiveClass] = useState('1');

    // Settings panel — opens in the app-level SidePanelArea (same as Jobs/Logs)
    const { activePanel, togglePanel } = useSidePanelStore();
    const settingsOpen = activePanel === 'settings';
    const { setContent, clearContent } = useSettingsPanelSlot();

    // Algorithm parameters — single dict driven by schema
    const [pickerParams, setPickerParams] = useState<Record<string, any>>({
        template_paths: [],
        image_pixel_size: 1.0,
        template_pixel_size: 1.0,
        diameter_angstrom: 200.0,
        threshold: 0.4,
        max_peaks: 500,
        bin_factor: 1,
        invert_templates: false,
    });

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
    } = useParticleOperations({
        selectedParticlePicking,
        handleIppUpdate,
        selectedImage,
        particleClasses,
        setParticleClasses,
        pickerParams,
        showSnackbar,
    });

    // Register settings panel content into the app-level side panel slot
    useEffect(() => {
        setContent(
            <ParticleSettingsPanel
                open={settingsOpen}
                pickerParams={pickerParams}
                onPickerParamsChange={setPickerParams}
                onRun={runAutoPicking}
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
                autoPickingProgress={autoPickingProgress}
                resultCount={lastResultCount}
            />
        );
        return () => clearContent();
    }, [settingsOpen, pickerParams, isAutoPickingRunning, autoPickingProgress, lastResultCount,
        particles, selectedImage, previewParticles]);

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
                onSettingsOpen={() => togglePanel('settings')}
                onHelpOpen={() => setHelpOpen(true)}
                isMobile={isMobile}
                isFullscreen={isFullscreen}
                onToggleFullscreen={toggleFullscreen}
            />

            {/* Auto-picking Progress */}
            {isAutoPickingRunning && (
                <LinearProgress
                    variant="determinate"
                    value={autoPickingProgress}
                    sx={{ mb: 1 }}
                />
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
                {showStats && !isMobile && (
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
                        imageUrl={`${BASE_URL}/image_thumbnail?name=${encodeURIComponent(selectedImage?.name)}&sessionName=${sessionName}`}
                        width={isMobile ? 300 : 1024}
                        height={isMobile ? 300 : 1024}
                        particles={particles}
                        selectedParticles={selectedParticles}
                        tool={tool}
                        particleRadius={particleRadius}
                        particleOpacity={particleOpacity}
                        showGrid={showGrid}
                        showCrosshair={showCrosshair}
                        zoom={zoom}
                        activeClass={activeClass}
                        particleClasses={particleClasses}
                        onParticlesUpdate={handleParticlesUpdate}
                        onSelectedParticlesUpdate={setSelectedParticles}
                        onShowSnackbar={showSnackbar}
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
                        tooltipTitle="Save (Ctrl+S)"
                        onClick={() => {
                            handleSave();
                            showSnackbar('Particles saved', 'success');
                        }}
                    />
                    <SpeedDialAction
                        icon={<DownloadIcon />}
                        tooltipTitle="Export Particles"
                        onClick={exportParticles}
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
                        tooltipTitle="Import Particles"
                        onClick={() => document.getElementById('import-particles')?.click()}
                    />
                    <SpeedDialAction
                        icon={<AutoFixHighIcon />}
                        tooltipTitle="Run Auto-picking"
                        onClick={runAutoPicking}
                    />
                </SpeedDial>
            </Paper>

            {/* Settings panel content — registered into SidePanelArea slot */}

            {/* Help Dialog */}
            <ParticleHelpDialog
                open={helpOpen}
                onClose={() => setHelpOpen(false)}
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
