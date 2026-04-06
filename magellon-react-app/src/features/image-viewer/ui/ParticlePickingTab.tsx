import React, { useState, useRef } from 'react';
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
    alpha,
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
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import { Point, ParticleClass, Tool } from '../lib/useParticleOperations.ts';
import { useParticleOperations } from '../lib/useParticleOperations.ts';
import { ParticleToolbar } from './ParticleToolbar.tsx';
import { ParticleStatsBar } from './ParticleStatsBar.tsx';
import { ParticleSettingsDrawer } from './ParticleSettingsDrawer.tsx';
import { ParticleHelpDialog } from './ParticleHelpDialog.tsx';

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

// Enhanced Particle Editor Component (SVG canvas)
const ParticleEditor: React.FC<{
    imageUrl: string;
    width: number;
    height: number;
    image: ImageInfoDto | null;
    ipp: ParticlePickingDto | null;
    particles: Point[];
    selectedParticles: Set<string>;
    tool: Tool;
    particleRadius: number;
    particleOpacity: number;
    showGrid: boolean;
    showCrosshair: boolean;
    zoom: number;
    activeClass: string;
    particleClasses: ParticleClass[];
    onParticlesUpdate: (particles: Point[]) => void;
    onSelectedParticlesUpdate: (selected: Set<string>) => void;
    onShowSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}> = ({
          imageUrl,
          width,
          height,
          image,
          ipp,
          particles,
          selectedParticles,
          tool,
          particleRadius,
          particleOpacity,
          showGrid,
          showCrosshair,
          zoom,
          activeClass,
          particleClasses,
          onParticlesUpdate,
          onSelectedParticlesUpdate,
          onShowSnackbar
      }) => {
    const svgRef = useRef<SVGSVGElement>(null);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isPanning, setIsPanning] = useState(false);
    const [dragStart, setDragStart] = useState<Point | null>(null);
    const [boxSelection, setBoxSelection] = useState<{ start: Point; end: Point } | null>(null);
    const [hoveredParticle, setHoveredParticle] = useState<string | null>(null);

    const { imageUrl: authenticatedImageUrl, isLoading: isImageLoading } = useAuthenticatedImage(imageUrl);

    const generateId = () => `particle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const getSVGPoint = (e: React.MouseEvent<SVGElement>): Point => {
        if (!svgRef.current) return { x: 0, y: 0 };

        const svg = svgRef.current;
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

        return { x: svgP.x, y: svgP.y };
    };

    const handleMouseDown = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (tool === 'pan' || (e.button === 1) || (e.button === 0 && e.altKey)) {
            setIsPanning(true);
            setDragStart(point);
        } else if (tool === 'box') {
            setBoxSelection({ start: point, end: point });
        }
    };

    const handleMouseMove = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (isPanning && dragStart) {
            const dx = point.x - dragStart.x;
            const dy = point.y - dragStart.y;
            setPan(prev => ({
                x: prev.x + dx * zoom,
                y: prev.y + dy * zoom
            }));
            setDragStart(point);
        } else if (boxSelection) {
            setBoxSelection(prev => prev ? { ...prev, end: point } : null);
        }
    };

    const handleMouseUp = () => {
        setIsPanning(false);
        setDragStart(null);

        if (boxSelection) {
            const minX = Math.min(boxSelection.start.x, boxSelection.end.x);
            const maxX = Math.max(boxSelection.start.x, boxSelection.end.x);
            const minY = Math.min(boxSelection.start.y, boxSelection.end.y);
            const maxY = Math.max(boxSelection.start.y, boxSelection.end.y);

            const selected = new Set<string>();
            particles.forEach(p => {
                if (p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY) {
                    selected.add(p.id || '');
                }
            });

            onSelectedParticlesUpdate(selected);
            setBoxSelection(null);
            if (selected.size > 0) {
                onShowSnackbar(`Selected ${selected.size} particles`, 'info');
            }
        }
    };

    const handleClick = (e: React.MouseEvent<SVGElement>) => {
        if (isPanning || boxSelection) return;

        const point = getSVGPoint(e);

        switch (tool) {
            case 'add':
                addParticle(point);
                break;
            case 'remove':
                removeParticleAt(point);
                break;
            case 'select':
                toggleParticleSelection(point);
                break;
        }
    };

    const addParticle = (point: Point) => {
        const newParticle: Point = {
            ...point,
            id: generateId(),
            type: 'manual',
            confidence: 1,
            class: activeClass,
            timestamp: Date.now()
        };

        onParticlesUpdate([...particles, newParticle]);
    };

    const removeParticleAt = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            onParticlesUpdate(particles.filter(p => p.id !== clickedParticle.id));
        }
    };

    const toggleParticleSelection = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            const newSelected = new Set(selectedParticles);
            if (newSelected.has(clickedParticle.id || '')) {
                newSelected.delete(clickedParticle.id || '');
            } else {
                newSelected.add(clickedParticle.id || '');
            }
            onSelectedParticlesUpdate(newSelected);
        }
    };

    const findParticleAt = (point: Point): Point | null => {
        return particles.find(p => {
            const dx = p.x - point.x;
            const dy = p.y - point.y;
            return Math.sqrt(dx * dx + dy * dy) <= particleRadius;
        }) || null;
    };

    const getParticleColor = (particle: Point) => {
        const particleClass = particleClasses.find(c => c.id === particle.class);
        const baseColor = particleClass?.color || '#4caf50';

        if (selectedParticles.has(particle.id || '')) {
            return '#2196f3';
        }
        if (hoveredParticle === particle.id) {
            return '#ff9800';
        }

        return baseColor;
    };

    const viewBox = `${-pan.x / zoom} ${-pan.y / zoom} ${width / zoom} ${height / zoom}`;

    return (
        <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox={viewBox}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onClick={handleClick}
            onContextMenu={(e) => e.preventDefault()}
            style={{
                cursor: tool === 'add' ? 'crosshair' :
                    tool === 'move' || tool === 'pan' ? 'move' :
                        tool === 'select' ? 'pointer' :
                            'default',
                backgroundColor: '#000'
            }}
        >
            {/* Grid */}
            {showGrid && (
                <g opacity={0.2}>
                    <defs>
                        <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
                            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="white" strokeWidth="1"/>
                        </pattern>
                    </defs>
                    <rect width="100%" height="100%" fill="url(#grid)" />
                </g>
            )}

            {/* Image */}
            {isImageLoading ? (
                <rect width={width} height={height} fill="#333" />
            ) : authenticatedImageUrl ? (
                <image href={authenticatedImageUrl} width={width} height={height} />
            ) : null}

            {/* Particles */}
            <g>
                {particles.map(particle => {
                    const particleClass = particleClasses.find(c => c.id === particle.class);
                    if (!particleClass?.visible) return null;

                    return (
                        <g
                            key={particle.id}
                            onMouseEnter={() => setHoveredParticle(particle.id || null)}
                            onMouseLeave={() => setHoveredParticle(null)}
                        >
                            <circle
                                cx={particle.x}
                                cy={particle.y}
                                r={particleRadius}
                                fill="none"
                                stroke={getParticleColor(particle)}
                                strokeWidth={selectedParticles.has(particle.id || '') ? 3 : 2}
                                opacity={particleOpacity}
                            />

                            {showCrosshair && (
                                <>
                                    <line
                                        x1={particle.x - particleRadius/2}
                                        y1={particle.y}
                                        x2={particle.x + particleRadius/2}
                                        y2={particle.y}
                                        stroke={getParticleColor(particle)}
                                        strokeWidth={2}
                                        opacity={particleOpacity}
                                    />
                                    <line
                                        x1={particle.x}
                                        y1={particle.y - particleRadius/2}
                                        x2={particle.x}
                                        y2={particle.y + particleRadius/2}
                                        stroke={getParticleColor(particle)}
                                        strokeWidth={2}
                                        opacity={particleOpacity}
                                    />
                                </>
                            )}

                            {particle.type === 'auto' && particle.confidence && (
                                <circle
                                    cx={particle.x}
                                    cy={particle.y}
                                    r={particleRadius * 0.3}
                                    fill={getParticleColor(particle)}
                                    opacity={particle.confidence}
                                />
                            )}
                        </g>
                    );
                })}
            </g>

            {/* Box Selection */}
            {boxSelection && (
                <rect
                    x={Math.min(boxSelection.start.x, boxSelection.end.x)}
                    y={Math.min(boxSelection.start.y, boxSelection.end.y)}
                    width={Math.abs(boxSelection.end.x - boxSelection.start.x)}
                    height={Math.abs(boxSelection.end.y - boxSelection.start.y)}
                    fill={alpha('#2196f3', 0.2)}
                    stroke="#2196f3"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                />
            )}
        </svg>
    );
};

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

    // UI state
    const [tool, setTool] = useState<Tool>('add');
    const [particleRadius, setParticleRadius] = useState(15);
    const [particleOpacity, setParticleOpacity] = useState(0.8);
    const [showGrid, setShowGrid] = useState(false);
    const [showCrosshair, setShowCrosshair] = useState(true);
    const [showStats, setShowStats] = useState(true);
    const [zoom, setZoom] = useState(1);
    const [autoPickingThreshold, setAutoPickingThreshold] = useState(0.7);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [helpOpen, setHelpOpen] = useState(false);
    const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
    const [activeClass, setActiveClass] = useState('1');

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
        autoPickingThreshold,
        showSnackbar,
    });

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
                onSettingsOpen={() => setSettingsDrawerOpen(true)}
                onHelpOpen={() => setHelpOpen(true)}
                isMobile={isMobile}
                isFullscreen={isFullscreen}
                onToggleFullscreen={toggleFullscreen}
            />

            {/* Statistics Bar */}
            {showStats && (
                <ParticleStatsBar
                    stats={stats}
                    particleClasses={particleClasses}
                    activeClass={activeClass}
                    onActiveClassChange={setActiveClass}
                    selectedCount={selectedParticles.size}
                    onDeselectAll={deselectAll}
                />
            )}

            {/* Auto-picking Progress */}
            {isAutoPickingRunning && (
                <LinearProgress
                    variant="determinate"
                    value={autoPickingProgress}
                    sx={{ mb: 1 }}
                />
            )}

            {/* Main Canvas */}
            <Paper
                elevation={2}
                sx={{
                    flex: 1,
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: theme.palette.grey[900],
                    borderRadius: 2
                }}
            >
                <Box sx={{ width: '100%', height: '100%' }}>
                    <ParticleEditor
                        imageUrl={`${BASE_URL}/image_thumbnail?name=${encodeURIComponent(selectedImage?.name)}&sessionName=${sessionName}`}
                        width={isMobile ? 300 : 1024}
                        height={isMobile ? 300 : 1024}
                        image={selectedImage}
                        ipp={selectedParticlePicking}
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

            {/* Settings Drawer */}
            <ParticleSettingsDrawer
                open={settingsDrawerOpen}
                onClose={() => setSettingsDrawerOpen(false)}
                particleRadius={particleRadius}
                onRadiusChange={setParticleRadius}
                particleOpacity={particleOpacity}
                onOpacityChange={setParticleOpacity}
                showCrosshair={showCrosshair}
                onCrosshairToggle={setShowCrosshair}
                showGrid={showGrid}
                onGridToggle={setShowGrid}
                showStats={showStats}
                onStatsToggle={setShowStats}
                particleClasses={particleClasses}
                onClassVisibilityChange={(classId, visible) => {
                    setParticleClasses(prev =>
                        prev.map(c =>
                            c.id === classId
                                ? { ...c, visible }
                                : c
                        )
                    );
                }}
                autoPickingThreshold={autoPickingThreshold}
                onThresholdChange={setAutoPickingThreshold}
            />

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
