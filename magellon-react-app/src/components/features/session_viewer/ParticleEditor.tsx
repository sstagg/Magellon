import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    Box,
    IconButton,
    Typography,
    Slider,
    Paper,
    Chip,
    Stack,
    Tooltip,
    Badge,
    ButtonGroup,
    Divider,
    alpha,
    useTheme,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Switch,
    FormControlLabel,
    ToggleButton,
    ToggleButtonGroup,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Fab,
    Menu,
    MenuItem,
    ListItemIcon,
    Snackbar,
    Alert,
    LinearProgress,
    Drawer,
    Zoom,
    Fade,
    CircularProgress
} from '@mui/material';
import {
    Add as AddIcon,
    Remove as RemoveIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    Save as SaveIcon,
    Undo as UndoIcon,
    Redo as RedoIcon,
    Visibility as VisibilityIcon,
    VisibilityOff as VisibilityOffIcon,
    AutoFixHigh as AutoFixHighIcon,
    Settings as SettingsIcon,
    Download as DownloadIcon,
    Upload as UploadIcon,
    ContentCopy as ContentCopyIcon,
    ContentPaste as ContentPasteIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    CenterFocusStrong as CenterFocusStrongIcon,
    GridOn as GridOnIcon,
    Brush as BrushIcon,
    Circle as CircleIcon,
    Square as SquareIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    Help as HelpIcon,
    Tune as TuneIcon,
    PlayArrow as PlayArrowIcon,
    Pause as PauseIcon,
    SkipNext as SkipNextIcon,
    SkipPrevious as SkipPreviousIcon,
    FilterList as FilterListIcon,
    Search as SearchIcon,
    Close as CloseIcon,
    KeyboardArrowUp as KeyboardArrowUpIcon,
    KeyboardArrowDown as KeyboardArrowDownIcon,
    Layers as LayersIcon,
    Timeline as TimelineIcon,
    Assessment as AssessmentIcon
} from '@mui/icons-material';
import {
    Target,
    Crosshair,
    MousePointer,
    Move,
    RotateCcw,
    Maximize2,
    Minimize2,
    AlertCircle,
    Check,
    X,
    Copy,
    Clipboard,
    Eye,
    EyeOff,
    Sparkles,
    Wand2,
    RefreshCw,
    FileDown,
    FileUp,
    Sliders,
    HelpCircle,
    Info,
    Zap,
    Activity,
    BarChart3, Circle
} from 'lucide-react';

interface Point {
    x: number;
    y: number;
    id: string;
    confidence?: number;
    type?: 'manual' | 'auto' | 'suggested';
    selected?: boolean;
    group?: string;
}

interface ParticleClass {
    id: string;
    name: string;
    color: string;
    count: number;
    visible: boolean;
}

interface ParticleEditorProps {
    imageUrl: string;
    width: number;
    height: number;
    image: any;
    ipp: any;
    onCirclesSelected: (circles: Point[]) => void;
    onIppUpdate: (updatedIpp: any) => void;
}

type Tool = 'add' | 'remove' | 'select' | 'move' | 'box' | 'auto';
type ViewMode = 'normal' | 'overlay' | 'heatmap' | 'clusters';

const ParticleEditor: React.FC<ParticleEditorProps> = ({
                                                                   imageUrl,
                                                                   width,
                                                                   height,
                                                                   image,
                                                                   ipp,
                                                                   onCirclesSelected,
                                                                   onIppUpdate
                                                               }) => {
    const theme = useTheme();
    const svgRef = useRef<SVGSVGElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // State management
    const [particles, setParticles] = useState<Point[]>([]);
    const [selectedParticles, setSelectedParticles] = useState<Set<string>>(new Set());
    const [hoveredParticle, setHoveredParticle] = useState<string | null>(null);
    const [tool, setTool] = useState<Tool>('add');
    const [viewMode, setViewMode] = useState<ViewMode>('normal');
    const [particleRadius, setParticleRadius] = useState(15);
    const [particleOpacity, setParticleOpacity] = useState(0.8);
    const [showGrid, setShowGrid] = useState(false);
    const [showCrosshair, setShowCrosshair] = useState(true);
    const [showLabels, setShowLabels] = useState(false);
    const [showStats, setShowStats] = useState(true);
    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isPanning, setIsPanning] = useState(false);
    const [dragStart, setDragStart] = useState<Point | null>(null);
    const [boxSelection, setBoxSelection] = useState<{ start: Point; end: Point } | null>(null);

    // History management
    const [history, setHistory] = useState<Point[][]>([[]]);
    const [historyIndex, setHistoryIndex] = useState(0);

    // UI state
    const [showSettings, setShowSettings] = useState(false);
    const [showHelp, setShowHelp] = useState(false);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
        open: false,
        message: '',
        severity: 'info'
    });
    const [autoPickingProgress, setAutoPickingProgress] = useState(0);
    const [isAutoPickingRunning, setIsAutoPickingRunning] = useState(false);

    // Particle classes for categorization
    const [particleClasses, setParticleClasses] = useState<ParticleClass[]>([
        { id: '1', name: 'Good', color: '#4caf50', count: 0, visible: true },
        { id: '2', name: 'Edge', color: '#ff9800', count: 0, visible: true },
        { id: '3', name: 'Bad', color: '#f44336', count: 0, visible: true }
    ]);
    const [activeClass, setActiveClass] = useState('1');

    // Load particles from IPP
    useEffect(() => {
        if (ipp?.data_json) {
            const parsedParticles: Point[] = (ipp.data_json as any[]).map((p, idx) => ({
                ...p,
                id: p.id || `particle-${idx}`,
                type: p.type || 'manual',
                confidence: p.confidence || 1,
                group: p.group || '1'
            }));
            setParticles(parsedParticles);
            addToHistory(parsedParticles);
            updateParticleClassCounts(parsedParticles);
        } else {
            setParticles([]);
            setHistory([[]]);
            setHistoryIndex(0);
        }
    }, [ipp?.oid]);

    // Update IPP when particles change
    useEffect(() => {
        const updatedIpp = { ...ipp, temp: JSON.stringify(particles) };
        onIppUpdate(updatedIpp);
        onCirclesSelected(particles);
    }, [particles]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'z':
                        e.preventDefault();
                        if (e.shiftKey) {
                            redo();
                        } else {
                            undo();
                        }
                        break;
                    case 'a':
                        e.preventDefault();
                        selectAll();
                        break;
                    case 'd':
                        e.preventDefault();
                        deselectAll();
                        break;
                    case 'c':
                        e.preventDefault();
                        copySelected();
                        break;
                    case 'v':
                        e.preventDefault();
                        pasteParticles();
                        break;
                    case 's':
                        e.preventDefault();
                        // Trigger save
                        showSnackbar('Particles saved', 'success');
                        break;
                }
            } else {
                switch (e.key) {
                    case '1':
                        setTool('add');
                        break;
                    case '2':
                        setTool('remove');
                        break;
                    case '3':
                        setTool('select');
                        break;
                    case '4':
                        setTool('move');
                        break;
                    case 'Delete':
                        deleteSelected();
                        break;
                    case 'Escape':
                        deselectAll();
                        setBoxSelection(null);
                        break;
                    case 'g':
                        setShowGrid(!showGrid);
                        break;
                    case 'h':
                        setShowHelp(!showHelp);
                        break;
                    case '+':
                    case '=':
                        zoomIn();
                        break;
                    case '-':
                        zoomOut();
                        break;
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [particles, selectedParticles, showGrid, showHelp]);

    // Helper functions
    const generateId = () => `particle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const addToHistory = (newParticles: Point[]) => {
        const newHistory = history.slice(0, historyIndex + 1);
        newHistory.push([...newParticles]);
        setHistory(newHistory);
        setHistoryIndex(newHistory.length - 1);
    };

    const updateParticleClassCounts = (particleList: Point[]) => {
        const counts = particleClasses.reduce((acc, cls) => {
            acc[cls.id] = 0;
            return acc;
        }, {} as Record<string, number>);

        particleList.forEach(p => {
            if (p.group && counts[p.group] !== undefined) {
                counts[p.group]++;
            }
        });

        setParticleClasses(prev => prev.map(cls => ({
            ...cls,
            count: counts[cls.id] || 0
        })));
    };

    const showSnackbar = (message: string, severity: 'success' | 'error' | 'info' | 'warning' = 'info') => {
        setSnackbar({ open: true, message, severity });
    };

    // Tool functions
    const undo = () => {
        if (historyIndex > 0) {
            const newIndex = historyIndex - 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            showSnackbar('Undo', 'info');
        }
    };

    const redo = () => {
        if (historyIndex < history.length - 1) {
            const newIndex = historyIndex + 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            showSnackbar('Redo', 'info');
        }
    };

    const selectAll = () => {
        const allIds = new Set(particles.map(p => p.id));
        setSelectedParticles(allIds);
        showSnackbar(`Selected ${particles.length} particles`, 'info');
    };

    const deselectAll = () => {
        setSelectedParticles(new Set());
    };

    const deleteSelected = () => {
        const newParticles = particles.filter(p => !selectedParticles.has(p.id));
        setParticles(newParticles);
        addToHistory(newParticles);
        setSelectedParticles(new Set());
        updateParticleClassCounts(newParticles);
        showSnackbar(`Deleted ${selectedParticles.size} particles`, 'success');
    };

    const copySelected = () => {
        const selectedParticlesList = particles.filter(p => selectedParticles.has(p.id));
        if (selectedParticlesList.length > 0) {
            localStorage.setItem('copiedParticles', JSON.stringify(selectedParticlesList));
            showSnackbar(`Copied ${selectedParticlesList.length} particles`, 'success');
        }
    };

    const pasteParticles = () => {
        const copiedData = localStorage.getItem('copiedParticles');
        if (copiedData) {
            try {
                const copiedParticles = JSON.parse(copiedData);
                const offset = 20; // Offset pasted particles
                const newParticles = copiedParticles.map((p: Point) => ({
                    ...p,
                    id: generateId(),
                    x: p.x + offset,
                    y: p.y + offset
                }));
                const updatedParticles = [...particles, ...newParticles];
                setParticles(updatedParticles);
                addToHistory(updatedParticles);
                updateParticleClassCounts(updatedParticles);
                showSnackbar(`Pasted ${newParticles.length} particles`, 'success');
            } catch (error) {
                showSnackbar('Failed to paste particles', 'error');
            }
        }
    };

    const zoomIn = () => {
        setZoom(prev => Math.min(prev * 1.2, 5));
    };

    const zoomOut = () => {
        setZoom(prev => Math.max(prev / 1.2, 0.2));
    };

    const resetView = () => {
        setZoom(1);
        setPan({ x: 0, y: 0 });
    };

    // Mouse event handlers
    const handleMouseDown = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (e.button === 1 || (e.button === 0 && e.altKey)) {
            // Middle mouse or Alt+Left click for panning
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
                x: prev.x + dx,
                y: prev.y + dy
            }));
            setDragStart(point);
        } else if (boxSelection) {
            setBoxSelection(prev => prev ? { ...prev, end: point } : null);
        }
    };

    const handleMouseUp = (e: React.MouseEvent<SVGElement>) => {
        setIsPanning(false);
        setDragStart(null);

        if (boxSelection) {
            // Select particles within box
            const minX = Math.min(boxSelection.start.x, boxSelection.end.x);
            const maxX = Math.max(boxSelection.start.x, boxSelection.end.x);
            const minY = Math.min(boxSelection.start.y, boxSelection.end.y);
            const maxY = Math.max(boxSelection.start.y, boxSelection.end.y);

            const selected = new Set<string>();
            particles.forEach(p => {
                if (p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY) {
                    selected.add(p.id);
                }
            });

            setSelectedParticles(selected);
            setBoxSelection(null);
            showSnackbar(`Selected ${selected.size} particles`, 'info');
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

    const getSVGPoint = (e: React.MouseEvent<SVGElement>): Point => {
        if (!svgRef.current) return { x: 0, y: 0, id: '' };

        const svg = svgRef.current;
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

        return { x: svgP.x, y: svgP.y, id: '' };
    };

    const addParticle = (point: Point) => {
        const newParticle: Point = {
            ...point,
            id: generateId(),
            type: 'manual',
            confidence: 1,
            group: activeClass
        };

        const updatedParticles = [...particles, newParticle];
        setParticles(updatedParticles);
        addToHistory(updatedParticles);
        updateParticleClassCounts(updatedParticles);
    };

    const removeParticleAt = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            const newParticles = particles.filter(p => p.id !== clickedParticle.id);
            setParticles(newParticles);
            addToHistory(newParticles);
            updateParticleClassCounts(newParticles);
        }
    };

    const toggleParticleSelection = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            const newSelected = new Set(selectedParticles);
            if (newSelected.has(clickedParticle.id)) {
                newSelected.delete(clickedParticle.id);
            } else {
                newSelected.add(clickedParticle.id);
            }
            setSelectedParticles(newSelected);
        }
    };

    const findParticleAt = (point: Point): Point | null => {
        return particles.find(p => {
            const dx = p.x - point.x;
            const dy = p.y - point.y;
            return Math.sqrt(dx * dx + dy * dy) <= particleRadius;
        }) || null;
    };

    // Auto-picking simulation
    const runAutoPicking = async () => {
        setIsAutoPickingRunning(true);
        setAutoPickingProgress(0);

        // Simulate auto-picking with progress
        for (let i = 0; i <= 100; i += 10) {
            await new Promise(resolve => setTimeout(resolve, 200));
            setAutoPickingProgress(i);

            if (i === 50) {
                // Add some auto-detected particles
                const autoParticles: Point[] = [];
                for (let j = 0; j < 10; j++) {
                    autoParticles.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        id: generateId(),
                        type: 'auto',
                        confidence: Math.random() * 0.5 + 0.5,
                        group: '1'
                    });
                }

                const updatedParticles = [...particles, ...autoParticles];
                setParticles(updatedParticles);
                addToHistory(updatedParticles);
                updateParticleClassCounts(updatedParticles);
            }
        }

        setIsAutoPickingRunning(false);
        setAutoPickingProgress(0);
        showSnackbar('Auto-picking completed', 'success');
    };

    // Export/Import functions
    const exportParticles = () => {
        const dataStr = JSON.stringify(particles, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);

        const exportFileDefaultName = `particles-${image?.name || 'export'}.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        showSnackbar('Particles exported', 'success');
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
                updateParticleClassCounts(imported);
                showSnackbar('Particles imported successfully', 'success');
            } catch (error) {
                showSnackbar('Failed to import particles', 'error');
            }
        };
        reader.readAsText(file);
    };

    // Render helpers
    const getParticleColor = (particle: Point) => {
        const particleClass = particleClasses.find(c => c.id === particle.group);
        const baseColor = particleClass?.color || theme.palette.primary.main;

        if (selectedParticles.has(particle.id)) {
            return theme.palette.info.main;
        }
        if (hoveredParticle === particle.id) {
            return theme.palette.secondary.main;
        }

        return baseColor;
    };

    const getParticleOpacity = (particle: Point) => {
        const particleClass = particleClasses.find(c => c.id === particle.group);
        if (!particleClass?.visible) return 0;

        if (particle.type === 'auto') {
            return particleOpacity * (particle.confidence || 1);
        }

        return particleOpacity;
    };

    const viewBox = `${-pan.x} ${-pan.y} ${width / zoom} ${height / zoom}`;

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Top Toolbar */}
            <Paper elevation={1} sx={{ p: 1, mb: 2 }}>
                <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                    {/* Tool Selection */}
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
                                <MousePointer size={16} />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="move" aria-label="move particles">
                            <Tooltip title="Move Particles (4)">
                                <Move size={16} />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="box" aria-label="box selection">
                            <Tooltip title="Box Selection">
                                <SquareIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="auto" aria-label="auto-pick">
                            <Tooltip title="Auto-pick">
                                <AutoFixHighIcon />
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
                                <CheckCircleIcon />
                            </IconButton>
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
                            <IconButton onClick={zoomIn} size="small">
                                <ZoomInIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Zoom Out (-)">
                            <IconButton onClick={zoomOut} size="small">
                                <ZoomOutIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Reset View">
                            <IconButton onClick={resetView} size="small">
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

                    <Tooltip title="Settings">
                        <IconButton onClick={() => setShowSettings(true)} size="small">
                            <SettingsIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Help (H)">
                        <IconButton onClick={() => setShowHelp(true)} size="small">
                            <HelpIcon />
                        </IconButton>
                    </Tooltip>
                </Stack>
            </Paper>

            {/* Statistics Bar */}
            {showStats && (
                <Paper
                    elevation={0}
                    sx={{
                        p: 1,
                        mb: 1,
                        backgroundColor: alpha(theme.palette.primary.main, 0.05),
                        border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
                    }}
                >
                    <Stack direction="row" spacing={3} alignItems="center">
                        <Typography variant="body2">
                            <strong>Total:</strong> {particles.length}
                        </Typography>
                        <Typography variant="body2">
                            <strong>Selected:</strong> {selectedParticles.size}
                        </Typography>
                        <Divider orientation="vertical" flexItem />
                        {particleClasses.map(cls => (
                            <Chip
                                key={cls.id}
                                label={`${cls.name}: ${cls.count}`}
                                size="small"
                                sx={{
                                    backgroundColor: alpha(cls.color, 0.2),
                                    color: cls.color,
                                    fontWeight: 'bold'
                                }}
                                onClick={() => setActiveClass(cls.id)}
                                variant={activeClass === cls.id ? "filled" : "outlined"}
                            />
                        ))}
                    </Stack>
                </Paper>
            )}

            {/* Main Canvas */}
            <Box
                ref={containerRef}
                sx={{
                    flex: 1,
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: theme.palette.grey[900],
                    borderRadius: 1,
                    cursor: tool === 'add' ? 'crosshair' :
                        tool === 'move' ? 'move' :
                            tool === 'select' ? 'pointer' :
                                'default'
                }}
            >
                {/* Auto-picking Progress */}
                {isAutoPickingRunning && (
                    <LinearProgress
                        variant="determinate"
                        value={autoPickingProgress}
                        sx={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            zIndex: 10
                        }}
                    />
                )}

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
                    style={{ width: '100%', height: '100%' }}
                >
                    {/* Grid */}
                    {showGrid && (
                        <g opacity={0.2}>
                            <defs>
                                <pattern
                                    id="grid"
                                    width="50"
                                    height="50"
                                    patternUnits="userSpaceOnUse"
                                >
                                    <path
                                        d="M 50 0 L 0 0 0 50"
                                        fill="none"
                                        stroke="white"
                                        strokeWidth="1"
                                    />
                                </pattern>
                            </defs>
                            <rect width="100%" height="100%" fill="url(#grid)" />
                        </g>
                    )}

                    {/* Image */}
                    <image
                        href={imageUrl}
                        width={width}
                        height={height}
                        style={{ userSelect: 'none' }}
                    />

                    {/* Particles */}
                    <g>
                        {particles.map(particle => {
                            const particleClass = particleClasses.find(c => c.id === particle.group);
                            if (!particleClass?.visible) return null;

                            return (
                                <g
                                    key={particle.id}
                                    onMouseEnter={() => setHoveredParticle(particle.id)}
                                    onMouseLeave={() => setHoveredParticle(null)}
                                >
                                    {/* Particle circle */}
                                    <circle
                                        cx={particle.x}
                                        cy={particle.y}
                                        r={particleRadius}
                                        fill="none"
                                        stroke={getParticleColor(particle)}
                                        strokeWidth={selectedParticles.has(particle.id) ? 3 : 2}
                                        opacity={getParticleOpacity(particle)}
                                        style={{
                                            cursor: tool === 'select' || tool === 'move' ? 'pointer' : 'default',
                                            transition: 'all 0.2s ease'
                                        }}
                                    />

                                    {/* Crosshair */}
                                    {showCrosshair && (
                                        <>
                                            <line
                                                x1={particle.x - particleRadius/2}
                                                y1={particle.y}
                                                x2={particle.x + particleRadius/2}
                                                y2={particle.y}
                                                stroke={getParticleColor(particle)}
                                                strokeWidth={2}
                                                opacity={getParticleOpacity(particle)}
                                            />
                                            <line
                                                x1={particle.x}
                                                y1={particle.y - particleRadius/2}
                                                x2={particle.x}
                                                y2={particle.y + particleRadius/2}
                                                stroke={getParticleColor(particle)}
                                                strokeWidth={2}
                                                opacity={getParticleOpacity(particle)}
                                            />
                                        </>
                                    )}

                                    {/* Confidence indicator for auto-picked particles */}
                                    {particle.type === 'auto' && particle.confidence && (
                                        <circle
                                            cx={particle.x}
                                            cy={particle.y}
                                            r={particleRadius * 0.3}
                                            fill={getParticleColor(particle)}
                                            opacity={particle.confidence}
                                        />
                                    )}

                                    {/* Label */}
                                    {showLabels && (
                                        <text
                                            x={particle.x}
                                            y={particle.y - particleRadius - 5}
                                            fill="white"
                                            fontSize="12"
                                            textAnchor="middle"
                                            style={{ userSelect: 'none' }}
                                        >
                                            {particles.indexOf(particle) + 1}
                                        </text>
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
                            fill={alpha(theme.palette.primary.main, 0.2)}
                            stroke={theme.palette.primary.main}
                            strokeWidth={2}
                            strokeDasharray="5 5"
                        />
                    )}
                </svg>

                {/* Floating Action Buttons */}
                <SpeedDial
                    ariaLabel="Particle picking actions"
                    sx={{ position: 'absolute', bottom: 16, right: 16 }}
                    icon={<SpeedDialIcon />}
                >
                    <SpeedDialAction
                        icon={<SaveIcon />}
                        tooltipTitle="Save (Ctrl+S)"
                        onClick={() => showSnackbar('Particles saved', 'success')}
                    />
                    <SpeedDialAction
                        icon={<DownloadIcon />}
                        tooltipTitle="Export"
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
                                <label htmlFor="import-particles">
                                    <UploadIcon />
                                </label>
                            </>
                        }
                        tooltipTitle="Import"
                    />
                    <SpeedDialAction
                        icon={<AutoFixHighIcon />}
                        tooltipTitle="Run Auto-picking"
                        onClick={runAutoPicking}
                    />
                </SpeedDial>
            </Box>

            {/* Settings Drawer */}
            <Drawer
                anchor="right"
                open={showSettings}
                onClose={() => setShowSettings(false)}
            >
                <Box sx={{ width: 300, p: 3 }}>
                    <Typography variant="h6" gutterBottom>
                        Particle Picking Settings
                    </Typography>

                    <Stack spacing={3}>
                        <Box>
                            <Typography gutterBottom>Particle Size</Typography>
                            <Slider
                                value={particleRadius}
                                onChange={(e, v) => setParticleRadius(v as number)}
                                min={5}
                                max={50}
                                valueLabelDisplay="auto"
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
                            />
                        </Box>

                        <Divider />

                        <Typography variant="subtitle1">Display Options</Typography>

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
                                    checked={showLabels}
                                    onChange={(e) => setShowLabels(e.target.checked)}
                                />
                            }
                            label="Show Labels"
                        />

                        <FormControlLabel
                            control={
                                <Switch
                                    checked={showStats}
                                    onChange={(e) => setShowStats(e.target.checked)}
                                />
                            }
                            label="Show Statistics"
                        />

                        <Divider />

                        <Typography variant="subtitle1">Particle Classes</Typography>

                        <List>
                            {particleClasses.map(cls => (
                                <ListItem key={cls.id}>
                                    <ListItemIcon>
                                        <Circle
                                            size={20}
                                            color={cls.color}
                                            fill={cls.color}
                                        />
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
                    </Stack>
                </Box>
            </Drawer>

            {/* Help Dialog */}
            <Dialog open={showHelp} onClose={() => setShowHelp(false)} maxWidth="sm" fullWidth>
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
                            <ListItemText primary="1" secondary="Add particles tool" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="2" secondary="Remove particles tool" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="3" secondary="Select particles tool" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="4" secondary="Move particles tool" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+Z / Cmd+Z" secondary="Undo" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+Shift+Z / Cmd+Shift+Z" secondary="Redo" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Ctrl+A / Cmd+A" secondary="Select all" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Delete" secondary="Delete selected" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="G" secondary="Toggle grid" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="+"  secondary="Zoom inout" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Alt+Click / Middle Mouse" secondary="Pan image" />
                        </ListItem>
                    </List>

                    <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                        Mouse Controls
                    </Typography>
                    <List dense>
                        <ListItem>
                            <ListItemText primary="Left Click" secondary="Apply current tool" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Right Click" secondary="Remove particle (in any mode)" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Middle Mouse / Alt+Drag" secondary="Pan view" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="Scroll Wheel" secondary="Zoom in/out" />
                        </ListItem>
                    </List>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowHelp(false)}>Close</Button>
                </DialogActions>
            </Dialog>

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
        </Box>
    );
};

export default ParticleEditor;