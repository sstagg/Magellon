import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    Box,
    Paper,
    Stack,
    Typography,
    IconButton,
    Button,
    ButtonGroup,
    ToggleButton,
    ToggleButtonGroup,
    Chip,
    Divider,
    Slider,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent,
    Tooltip,
    Badge,
    CircularProgress,
    LinearProgress,
    Alert,
    Snackbar,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Switch,
    FormControlLabel,
    Drawer,
    Fab,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Menu,
    Collapse,
    useTheme,
    useMediaQuery,
    alpha,
    Grid,
    Card,
    CardContent,
    Accordion,
    AccordionSummary,
    AccordionDetails
} from '@mui/material';
import {
    Add as AddIcon,
    Remove as RemoveIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    Save as SaveIcon,
    Undo as UndoIcon,
    Redo as RedoIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    CenterFocusStrong as CenterFocusStrongIcon,
    GridOn as GridOnIcon,
    Visibility as VisibilityIcon,
    VisibilityOff as VisibilityOffIcon,
    AutoFixHigh as AutoFixHighIcon,
    Settings as SettingsIcon,
    Download as DownloadIcon,
    Upload as UploadIcon,
    Help as HelpIcon,
    Refresh as RefreshIcon,
    Close as CloseIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    PlayArrow as PlayArrowIcon,
    Pause as PauseIcon,
    ContentCopy as CopyIcon,
    ContentPaste as PasteIcon,
    SelectAll as SelectAllIcon,
    Layers as LayersIcon,
    FilterList as FilterListIcon,
    Assessment as AssessmentIcon,

    Brush as BrushIcon,

    Fullscreen as FullscreenIcon,
    FullscreenExit as FullscreenExitIcon,

    CropFree as CropFreeIcon,
    PanTool as PanToolIcon,
    TouchApp as TouchAppIcon,

} from '@mui/icons-material';
import {

    Move,
    Circle,
    HelpCircle,
} from 'lucide-react';
import { ParticleSessionDialog } from './ParticleSessionDialog.tsx';
import ImageInfoDto from './ImageInfoDto.ts';
import { ParticlePickingDto } from '../../../domains/ParticlePickingDto.ts';
import { useImageViewerStore } from './store/imageViewerStore.ts';
import { settings } from '../../../core/settings.ts';
import { useAuthenticatedImage } from '../../../hooks/useAuthenticatedImage';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface Point {
    x: number;
    y: number;
    id?: string;
    confidence?: number;
    type?: 'manual' | 'auto' | 'suggested';
    class?: string;
    timestamp?: number;
}

interface ParticleClass {
    id: string;
    name: string;
    color: string;
    count: number;
    visible: boolean;
    icon?: React.ReactNode;
}

interface EnhancedParticlePickingTabProps {
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

type Tool = 'add' | 'remove' | 'select' | 'move' | 'box' | 'auto' | 'brush' | 'pan';
type ViewMode = 'normal' | 'overlay' | 'heatmap' | 'comparison';

// Enhanced Particle Editor Component
const EnhancedParticleEditor: React.FC<{
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

    // Use authenticated image hook
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

export const EnhancedParticlePickingTab: React.FC<EnhancedParticlePickingTabProps> = ({
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
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Store integration
    const {
        selectedParticlePicking,
        isParticlePickingDialogOpen,
        currentSession
    } = useImageViewerStore();

    const sessionName = currentSession?.name || '';

    // Enhanced state management
    const [tool, setTool] = useState<Tool>('add');
    const [viewMode, setViewMode] = useState<ViewMode>('normal');
    const [particleRadius, setParticleRadius] = useState(15);
    const [brushSize, setBrushSize] = useState(30);
    const [particleOpacity, setParticleOpacity] = useState(0.8);
    const [showGrid, setShowGrid] = useState(false);
    const [showCrosshair, setShowCrosshair] = useState(true);
    const [showStats, setShowStats] = useState(true);
    const [showMinimap, setShowMinimap] = useState(!isMobile);
    const [zoom, setZoom] = useState(1);
    const [autoPickingThreshold, setAutoPickingThreshold] = useState(0.7);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // UI state
    const [settingsExpanded, setSettingsExpanded] = useState(false);
    const [statsExpanded, setStatsExpanded] = useState(true);
    const [helpOpen, setHelpOpen] = useState(false);
    const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
        open: false,
        message: '',
        severity: 'info'
    });
    const [isAutoPickingRunning, setIsAutoPickingRunning] = useState(false);
    const [autoPickingProgress, setAutoPickingProgress] = useState(0);

    // Particle classes
    const [particleClasses, setParticleClasses] = useState<ParticleClass[]>([
        { id: '1', name: 'Good', color: '#4caf50', count: 0, visible: true, icon: <CheckCircleIcon fontSize="small" /> },
        { id: '2', name: 'Edge', color: '#ff9800', count: 0, visible: true, icon: <Circle size={16} /> },
        { id: '3', name: 'Contamination', color: '#f44336', count: 0, visible: true, icon: <CloseIcon fontSize="small" /> },
        { id: '4', name: 'Uncertain', color: '#9c27b0', count: 0, visible: true, icon: <HelpIcon fontSize="small" /> }
    ]);
    const [activeClass, setActiveClass] = useState('1');

    // Enhanced particle management
    const [particles, setParticles] = useState<Point[]>([]);
    const [selectedParticles, setSelectedParticles] = useState<Set<string>>(new Set());
    const [history, setHistory] = useState<Point[][]>([[]]);
    const [historyIndex, setHistoryIndex] = useState(0);
    const [copiedParticles, setCopiedParticles] = useState<Point[]>([]);

    // Statistics
    const [stats, setStats] = useState({
        total: 0,
        manual: 0,
        auto: 0,
        avgConfidence: 0,
        particlesPerClass: {} as Record<string, number>
    });

    // Load particles when IPP changes
    useEffect(() => {
        if (selectedParticlePicking?.data_json) {
            try {
                const parsedParticles = selectedParticlePicking.data_json as Point[];
                setParticles(parsedParticles);
                updateStats(parsedParticles);
            } catch (error) {
                console.error('Error parsing particles:', error);
                showSnackbar('Error loading particles', 'error');
            }
        } else {
            setParticles([]);
            setHistory([[]]);
            setHistoryIndex(0);
        }
    }, [selectedParticlePicking]);

    // Update IPP when particles change
    useEffect(() => {
        if (selectedParticlePicking) {
            const updatedIpp = {
                ...selectedParticlePicking,
                data_json: particles,
                temp: JSON.stringify(particles)
            };
            handleIppUpdate(updatedIpp);
        }
    }, [particles]);

    // Helper functions
    const showSnackbar = (message: string, severity: 'success' | 'error' | 'info' | 'warning' = 'info') => {
        setSnackbar({ open: true, message, severity });
    };

    const updateStats = (particleList: Point[]) => {
        const manual = particleList.filter(p => p.type === 'manual').length;
        const auto = particleList.filter(p => p.type === 'auto').length;
        const avgConfidence = particleList.length > 0
            ? particleList.reduce((sum, p) => sum + (p.confidence || 1), 0) / particleList.length
            : 0;

        const particlesPerClass: Record<string, number> = {};
        particleClasses.forEach(cls => {
            particlesPerClass[cls.id] = particleList.filter(p => (p.class || '1') === cls.id).length;
        });

        setStats({
            total: particleList.length,
            manual,
            auto,
            avgConfidence,
            particlesPerClass
        });

        // Update class counts
        setParticleClasses(prev => prev.map(cls => ({
            ...cls,
            count: particlesPerClass[cls.id] || 0
        })));
    };

    const addToHistory = (newParticles: Point[]) => {
        const newHistory = history.slice(0, historyIndex + 1);
        newHistory.push([...newParticles]);
        setHistory(newHistory);
        setHistoryIndex(newHistory.length - 1);
    };

    const undo = () => {
        if (historyIndex > 0) {
            const newIndex = historyIndex - 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            updateStats(history[newIndex]);
            showSnackbar('Undo', 'info');
        }
    };

    const redo = () => {
        if (historyIndex < history.length - 1) {
            const newIndex = historyIndex + 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            updateStats(history[newIndex]);
            showSnackbar('Redo', 'info');
        }
    };

    const selectAll = () => {
        const allIds = new Set(particles.map(p => p.id || ''));
        setSelectedParticles(allIds);
        showSnackbar(`Selected ${particles.length} particles`, 'info');
    };

    const deselectAll = () => {
        setSelectedParticles(new Set());
    };

    const deleteSelected = () => {
        const newParticles = particles.filter(p => !selectedParticles.has(p.id || ''));
        setParticles(newParticles);
        addToHistory(newParticles);
        setSelectedParticles(new Set());
        updateStats(newParticles);
        showSnackbar(`Deleted ${selectedParticles.size} particles`, 'success');
    };

    const copySelected = () => {
        const selected = particles.filter(p => selectedParticles.has(p.id || ''));
        setCopiedParticles(selected);
        showSnackbar(`Copied ${selected.length} particles`, 'success');
    };

    const pasteParticles = () => {
        if (copiedParticles.length === 0) return;

        const offset = 20;
        const newParticles = copiedParticles.map(p => ({
            ...p,
            id: `particle-${Date.now()}-${Math.random()}`,
            x: p.x + offset,
            y: p.y + offset
        }));

        const updatedParticles = [...particles, ...newParticles];
        setParticles(updatedParticles);
        addToHistory(updatedParticles);
        updateStats(updatedParticles);
        showSnackbar(`Pasted ${newParticles.length} particles`, 'success');
    };

    const runAutoPicking = async () => {
        setIsAutoPickingRunning(true);
        setAutoPickingProgress(0);

        // Simulate auto-picking
        for (let i = 0; i <= 100; i += 10) {
            await new Promise(resolve => setTimeout(resolve, 200));
            setAutoPickingProgress(i);

            if (i === 50) {
                // Add simulated auto-detected particles
                const autoParticles: Point[] = [];
                for (let j = 0; j < 15; j++) {
                    autoParticles.push({
                        x: Math.random() * 800 + 100,
                        y: Math.random() * 800 + 100,
                        id: `auto-${Date.now()}-${j}`,
                        type: 'auto',
                        confidence: Math.random() * 0.3 + 0.7,
                        class: Math.random() > autoPickingThreshold ? '1' : '4'
                    });
                }

                const updatedParticles = [...particles, ...autoParticles];
                setParticles(updatedParticles);
                addToHistory(updatedParticles);
                updateStats(updatedParticles);
            }
        }

        setIsAutoPickingRunning(false);
        setAutoPickingProgress(0);
        showSnackbar('Auto-picking completed - 15 particles detected', 'success');
    };

    const exportParticles = () => {
        const dataStr = JSON.stringify(particles, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
        const exportFileDefaultName = `particles-${selectedImage?.name || 'export'}.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        showSnackbar('Particles exported successfully', 'success');
    };

    const importParticles = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const imported = JSON.parse(e.target?.result as string);
                setParticles(imported);
                addToHistory(imported);
                updateStats(imported);
                showSnackbar('Particles imported successfully', 'success');
            } catch (error) {
                showSnackbar('Failed to import particles', 'error');
            }
        };
        reader.readAsText(file);
    };

    const handleParticlesUpdate = (newParticles: Point[]) => {
        setParticles(newParticles);
        addToHistory(newParticles);
        updateStats(newParticles);
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
            <Paper elevation={1} sx={{ p: 2 }}>
                <Stack spacing={2}>
                    {/* Session and Save Controls */}
                    <Stack direction={isMobile ? "column" : "row"} spacing={2} alignItems="flex-start">
                        <FormControl size="small" sx={{ minWidth: 200, flex: 1 }}>
                            <InputLabel>Particle Picking Session</InputLabel>
                            <Select
                                value={selectedParticlePicking?.oid || ""}
                                label="Particle Picking Session"
                                onChange={OnIppSelected}
                                startAdornment={
                                    isIPPLoading ? (
                                        <CircularProgress size={20} sx={{ mr: 1 }} />
                                    ) : null
                                }
                            >
                                <MenuItem value="">
                                    <em>None</em>
                                </MenuItem>
                                {Array.isArray(ImageParticlePickings) && ImageParticlePickings?.map((ipp) => (
                                    <MenuItem key={ipp.oid} value={ipp.oid}>
                                        {ipp.name}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <ButtonGroup size="small" variant="outlined">
                            <Tooltip title="Refresh Sessions">
                                <IconButton onClick={onParticlePickingLoad}>
                                    <RefreshIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Create New Session">
                                <IconButton onClick={handleOpen}>
                                    <AddIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Save Current Session">
                                <IconButton onClick={handleSave} disabled={!selectedParticlePicking}>
                                    <SaveIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete Session">
                                <IconButton disabled={!selectedParticlePicking}>
                                    <DeleteIcon />
                                </IconButton>
                            </Tooltip>
                        </ButtonGroup>

                        {!isMobile && (
                            <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
                                <IconButton onClick={toggleFullscreen}>
                                    {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
                                </IconButton>
                            </Tooltip>
                        )}
                    </Stack>

                    {/* Tool Selection */}
                    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                        <ToggleButtonGroup
                            value={tool}
                            exclusive
                            onChange={(e, value) => value && setTool(value)}
                            size="small"
                        >
                            <ToggleButton value="add" aria-label="add particles">
                                <Tooltip title="Add Particles (1)">
                                    <AddIcon />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="remove" aria-label="remove particles">
                                <Tooltip title="Remove Particles (2)">
                                    <RemoveIcon />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="select" aria-label="select particles">
                                <Tooltip title="Select Particles (3)">
                                    <TouchAppIcon />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="move" aria-label="move particles">
                                <Tooltip title="Move Particles (4)">
                                    <Move size={16} />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="box" aria-label="box selection">
                                <Tooltip title="Box Selection (5)">
                                    <CropFreeIcon />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="brush" aria-label="brush tool">
                                <Tooltip title="Brush Tool (6)">
                                    <BrushIcon />
                                </Tooltip>
                            </ToggleButton>
                            <ToggleButton value="pan" aria-label="pan view">
                                <Tooltip title="Pan View">
                                    <PanToolIcon />
                                </Tooltip>
                            </ToggleButton>
                        </ToggleButtonGroup>

                        <Divider orientation="vertical" flexItem />

                        {/* Action Buttons */}
                        <ButtonGroup size="small">
                            <Tooltip title="Undo (Ctrl+Z)">
                                <span>
                                    <IconButton
                                        onClick={undo}
                                        disabled={historyIndex === 0}
                                        size="small"
                                    >
                                        <UndoIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title="Redo (Ctrl+Shift+Z)">
                                <span>
                                    <IconButton
                                        onClick={redo}
                                        disabled={historyIndex === history.length - 1}
                                        size="small"
                                    >
                                        <RedoIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </ButtonGroup>

                        <ButtonGroup size="small">
                            <Tooltip title="Select All (Ctrl+A)">
                                <IconButton onClick={selectAll} size="small">
                                    <SelectAllIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Copy Selected (Ctrl+C)">
                                <span>
                                    <IconButton
                                        onClick={copySelected}
                                        disabled={selectedParticles.size === 0}
                                        size="small"
                                    >
                                        <CopyIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title="Paste (Ctrl+V)">
                                <span>
                                    <IconButton
                                        onClick={pasteParticles}
                                        disabled={copiedParticles.length === 0}
                                        size="small"
                                    >
                                        <PasteIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title="Delete Selected (Delete)">
                                <span>
                                    <IconButton
                                        onClick={deleteSelected}
                                        disabled={selectedParticles.size === 0}
                                        size="small"
                                    >
                                        <DeleteIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </ButtonGroup>

                        <Divider orientation="vertical" flexItem />

                        {/* View Controls */}
                        <ButtonGroup size="small">
                            <Tooltip title="Zoom In (+)">
                                <IconButton
                                    onClick={() => setZoom(prev => Math.min(prev * 1.2, 5))}
                                    size="small"
                                >
                                    <ZoomInIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Zoom Out (-)">
                                <IconButton
                                    onClick={() => setZoom(prev => Math.max(prev / 1.2, 0.2))}
                                    size="small"
                                >
                                    <ZoomOutIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Reset View">
                                <IconButton
                                    onClick={() => setZoom(1)}
                                    size="small"
                                >
                                    <CenterFocusStrongIcon />
                                </IconButton>
                            </Tooltip>
                        </ButtonGroup>

                        <Chip
                            label={`Zoom: ${(zoom * 100).toFixed(0)}%`}
                            size="small"
                            variant="outlined"
                        />

                        <Box sx={{ flex: 1 }} />

                        {/* Right side controls */}
                        <Tooltip title="Toggle Grid (G)">
                            <IconButton
                                onClick={() => setShowGrid(!showGrid)}
                                color={showGrid ? "primary" : "default"}
                                size="small"
                            >
                                <GridOnIcon />
                            </IconButton>
                        </Tooltip>

                        <Tooltip title="Run Auto-picking">
                            <IconButton
                                onClick={runAutoPicking}
                                disabled={isAutoPickingRunning}
                                color="primary"
                                size="small"
                            >
                                <AutoFixHighIcon />
                            </IconButton>
                        </Tooltip>

                        <Tooltip title="Settings">
                            <IconButton
                                onClick={() => setSettingsDrawerOpen(true)}
                                size="small"
                            >
                                <SettingsIcon />
                            </IconButton>
                        </Tooltip>

                        <Tooltip title="Help (H)">
                            <IconButton
                                onClick={() => setHelpOpen(true)}
                                size="small"
                            >
                                <HelpIcon />
                            </IconButton>
                        </Tooltip>
                    </Stack>
                </Stack>
            </Paper>

            {/* Statistics Bar */}
            {showStats && (
                <Paper
                    elevation={0}
                    sx={{
                        p: 1,
                        backgroundColor: alpha(theme.palette.primary.main, 0.05),
                        border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
                    }}
                >
                    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                        <Chip
                            icon={<LayersIcon />}
                            label={`Total: ${stats.total}`}
                            size="small"
                            variant="outlined"
                        />
                        <Chip
                            icon={<TouchAppIcon />}
                            label={`Manual: ${stats.manual}`}
                            size="small"
                            color="primary"
                            variant="outlined"
                        />
                        <Chip
                            icon={<AutoFixHighIcon />}
                            label={`Auto: ${stats.auto}`}
                            size="small"
                            color="secondary"
                            variant="outlined"
                        />
                        <Chip
                            icon={<AssessmentIcon />}
                            label={`Confidence: ${(stats.avgConfidence * 100).toFixed(0)}%`}
                            size="small"
                            variant="outlined"
                        />

                        <Divider orientation="vertical" flexItem />

                        {particleClasses.map(cls => (
                            <Chip
                                key={cls.id}
                                icon={cls.icon}
                                label={`${cls.name}: ${cls.count}`}
                                size="small"
                                sx={{
                                    backgroundColor: activeClass === cls.id
                                        ? alpha(cls.color, 0.3)
                                        : alpha(cls.color, 0.1),
                                    color: cls.color,
                                    fontWeight: activeClass === cls.id ? 'bold' : 'normal',
                                    border: `1px solid ${cls.color}`,
                                    cursor: 'pointer'
                                }}
                                onClick={() => setActiveClass(cls.id)}
                                variant={activeClass === cls.id ? "filled" : "outlined"}
                            />
                        ))}

                        {selectedParticles.size > 0 && (
                            <>
                                <Divider orientation="vertical" flexItem />
                                <Chip
                                    label={`Selected: ${selectedParticles.size}`}
                                    size="small"
                                    color="info"
                                    onDelete={deselectAll}
                                />
                            </>
                        )}
                    </Stack>
                </Paper>
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
                    <EnhancedParticleEditor
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
            <Drawer
                anchor="right"
                open={settingsDrawerOpen}
                onClose={() => setSettingsDrawerOpen(false)}
            >
                <Box sx={{ width: 320, p: 3 }}>
                    <Typography variant="h6" gutterBottom>
                        Particle Picking Settings
                    </Typography>

                    <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography>Display Settings</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Box>
                                    <Typography gutterBottom>Particle Size</Typography>
                                    <Slider
                                        value={particleRadius}
                                        onChange={(e, v) => setParticleRadius(v as number)}
                                        min={5}
                                        max={50}
                                        valueLabelDisplay="auto"
                                        marks={[
                                            { value: 5, label: '5' },
                                            { value: 25, label: '25' },
                                            { value: 50, label: '50' }
                                        ]}
                                    />
                                </Box>

                                <Box>
                                    <Typography gutterBottom>Particle Opacity</Typography>
                                    <Slider
                                        value={particleOpacity}
                                        onChange={(e, v) => setParticleOpacity(v as number)}
                                        min={0.1}
                                        max={1}
                                        step={0.1}
                                        valueLabelDisplay="auto"
                                        marks={[
                                            { value: 0.1, label: '10%' },
                                            { value: 0.5, label: '50%' },
                                            { value: 1, label: '100%' }
                                        ]}
                                    />
                                </Box>

                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={showCrosshair}
                                            onChange={(e) => setShowCrosshair(e.target.checked)}
                                        />
                                    }
                                    label="Show Crosshairs"
                                />

                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={showGrid}
                                            onChange={(e) => setShowGrid(e.target.checked)}
                                        />
                                    }
                                    label="Show Grid"
                                />

                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={showStats}
                                            onChange={(e) => setShowStats(e.target.checked)}
                                        />
                                    }
                                    label="Show Statistics Bar"
                                />
                            </Stack>
                        </AccordionDetails>
                    </Accordion>

                    <Accordion>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography>Particle Classes</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <List>
                                {particleClasses.map(cls => (
                                    <ListItem key={cls.id}>
                                        <ListItemIcon>
                                            {cls.icon}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={cls.name}
                                            secondary={`${cls.count} particles`}
                                        />
                                        <ListItemSecondaryAction>
                                            <Switch
                                                checked={cls.visible}
                                                onChange={(e) => {
                                                    setParticleClasses(prev =>
                                                        prev.map(c =>
                                                            c.id === cls.id
                                                                ? { ...c, visible: e.target.checked }
                                                                : c
                                                        )
                                                    );
                                                }}
                                            />
                                        </ListItemSecondaryAction>
                                    </ListItem>
                                ))}
                            </List>
                        </AccordionDetails>
                    </Accordion>

                    <Accordion>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography>Auto-picking Settings</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Box>
                                    <Typography gutterBottom>Detection Threshold</Typography>
                                    <Slider
                                        value={autoPickingThreshold}
                                        onChange={(e, v) => setAutoPickingThreshold(v as number)}
                                        min={0.1}
                                        max={1}
                                        step={0.1}
                                        valueLabelDisplay="auto"
                                        marks={[
                                            { value: 0.3, label: 'Low' },
                                            { value: 0.7, label: 'Medium' },
                                            { value: 0.9, label: 'High' }
                                        ]}
                                    />
                                </Box>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>
                </Box>
            </Drawer>

            {/* Help Dialog */}
            <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <HelpCircle />
                        <Typography variant="h6">Particle Picking Help</Typography>
                    </Stack>
                </DialogTitle>
                <DialogContent>
                    <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                        Keyboard Shortcuts
                    </Typography>
                    <List dense>
                        <ListItem>
                            <ListItemText primary="1-6" secondary="Select tools (Add, Remove, Select, Move, Box, Brush)" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+Z / Cmd+Z" secondary="Undo last action" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+Shift+Z / Cmd+Shift+Z" secondary="Redo last action" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+A / Cmd+A" secondary="Select all particles" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+C / Cmd+C" secondary="Copy selected particles" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+V / Cmd+V" secondary="Paste particles" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Delete" secondary="Delete selected particles" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="G" secondary="Toggle grid" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="H" secondary="Show this help" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="+/-"  secondary="Zoom in/out" />
                        </ListItem>
                    </List>

                    <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                        Mouse Controls
                    </Typography>
                    <List dense>
                        <ListItem>
                            <ListItemText primary="Left Click" secondary="Apply current tool action" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Right Click" secondary="Quick remove particle" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Middle Mouse / Alt+Drag" secondary="Pan view" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Scroll Wheel" secondary="Zoom in/out" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Shift+Click" secondary="Add to selection" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+Click" secondary="Toggle selection" />
                        </ListItem>
                    </List>

                    <Typography variant="subtitle1"  sx={{ mt: 2 }}>
                        Tips
                    </Typography>
                    <List dense>
                        <ListItem>
                            <ListItemText
                                primary="Use particle classes"
                                secondary="Categorize particles as Good, Edge, Contamination, or Uncertain"
                            />
                        </ListItem>
                        <ListItem>
                            <ListItemText
                                primary="Auto-picking"
                                secondary="Use the auto-pick feature for initial particle detection, then refine manually"
                            />
                        </ListItem>
                        <ListItem>
                            <ListItemText
                                primary="Save frequently"
                                secondary="Press Ctrl+S to save your work regularly"
                            />
                        </ListItem>
                    </List>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setHelpOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>

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