import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
    Box,
    Paper,
    Card,
    CardContent,
    CardHeader,
    Typography,
    Button,
    IconButton,
    Tabs,
    Tab,
    Grid,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    FormControlLabel,
    Switch,
    Slider,
    Chip,
    Badge,
    LinearProgress,
    Divider,
    Avatar,
    Tooltip,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Drawer,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemButton,
    useTheme,
    useMediaQuery,
    alpha,
    Fab,
    Collapse,
    Alert,
    Snackbar,
    CircularProgress,
    ButtonGroup
} from '@mui/material';
import {
    Camera as CameraIcon,
    Settings as SettingsIcon,
    PlayArrow as PlayIcon,
    Stop as StopIcon,
    Save as SaveIcon,
    Download as DownloadIcon,
    Refresh as RefreshIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    Fullscreen as FullscreenIcon,
    GridOn as GridIcon,
    Navigation as NavigationIcon,
    Visibility as VisibilityIcon,
    VisibilityOff as VisibilityOffIcon,
    Tune as TuneIcon,
    Science as ScienceIcon,
    Memory as MemoryIcon,
    Speed as SpeedIcon,
    ThermostatOutlined as ThermostatIcon,
    BatteryChargingFull as BatteryIcon,
    CheckCircle as CheckCircleIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    Info as InfoIcon,
    Close as CloseIcon,
    Menu as MenuIcon,
    Add as AddIcon,
    Remove as RemoveIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
    Edit as EditIcon,
    Timeline as TimelineIcon,
    Assessment as AssessmentIcon,
    FiberManualRecord as RecordIcon,
    History as HistoryIcon,
    MoreVert as MoreVertIcon
} from '@mui/icons-material';
import {
    Zap,
    Monitor,
    Move,
    Focus,
    Activity,
    Layers,
    Crosshair,
    MapPin,
    ScanLine,
    ChevronRight,
    ChevronLeft,
    ChevronUp,
    ChevronDown,
    RotateCw,
    X,
    Eye,
    EyeOff,
    Maximize2,
    Minimize2, TargetIcon
} from 'lucide-react';

const DRAWER_WIDTH = 240;

// Mock API (simplified version combining both implementations)
class MicroscopeAPI {
    constructor() {
        this.connected = false;
        this.callbacks = {};
    }

    connect() {
        this.connected = true;
        setTimeout(() => {
            this.trigger('connected', { status: 'connected' });
        }, 500);
    }

    disconnect() {
        this.connected = false;
        this.trigger('disconnected', { status: 'disconnected' });
    }

    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    trigger(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(cb => cb(data));
        }
    }

    async getMicroscopeStatus() {
        return {
            connected: true,
            model: 'Titan Krios G4',
            highTension: 300000,
            columnValve: 'open',
            vacuumStatus: 'ready',
            temperature: -192.3,
            autoloader: 'ready',
            refrigerantLevel: 85
        };
    }

    async getAtlasData() {
        const gridSquares = [];
        for (let row = 0; row < 10; row++) {
            for (let col = 0; col < 10; col++) {
                gridSquares.push({
                    id: `${row}-${col}`,
                    x: col * 100,
                    y: row * 100,
                    quality: Math.random() > 0.3 ? (Math.random() > 0.5 ? 'good' : 'medium') : 'bad',
                    collected: Math.random() > 0.7,
                    iceThickness: Math.random() * 200 + 50
                });
            }
        }
        return { gridSquares, currentPosition: { x: 450, y: 450 } };
    }

    async acquireImage(settings) {
        this.trigger('acquisitionStarted', settings);
        return new Promise((resolve) => {
            setTimeout(() => {
                const imageData = this.generateFakeImage();
                const fftData = this.generateFFT();
                this.trigger('acquisitionCompleted', {
                    image: imageData,
                    fft: fftData,
                    timestamp: new Date().toISOString(),
                    settings,
                    metadata: {
                        pixelSize: 1.2,
                        dose: settings.exposure * 0.01,
                        defocus: -2.0,
                        astigmatism: 0.05
                    }
                });
                resolve({ success: true, image: imageData, fft: fftData });
            }, settings.exposure);
        });
    }

    generateFakeImage() {
        const size = 512;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');

        const gradient = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
        gradient.addColorStop(0, '#666');
        gradient.addColorStop(1, '#000');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, size, size);

        for (let i = 0; i < 80; i++) {
            const x = Math.random() * size;
            const y = Math.random() * size;
            const r = Math.random() * 15 + 5;
            const intensity = Math.random() * 0.6 + 0.4;

            const spotGradient = ctx.createRadialGradient(x, y, 0, x, y, r);
            spotGradient.addColorStop(0, `rgba(255, 255, 255, ${intensity})`);
            spotGradient.addColorStop(0.5, `rgba(200, 200, 200, ${intensity * 0.5})`);
            spotGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
            ctx.fillStyle = spotGradient;
            ctx.fillRect(x - r, y - r, r * 2, r * 2);
        }

        return canvas.toDataURL();
    }

    generateFFT() {
        const size = 256;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, size, size);

        const centerGradient = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, 20);
        centerGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
        centerGradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.5)');
        centerGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = centerGradient;
        ctx.fillRect(0, 0, size, size);

        return canvas.toDataURL();
    }
}

const microscopeAPI = new MicroscopeAPI();

// Status Card Component
const StatusCard = ({ title, value, subtitle, icon, color, progress }) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                height: '100%',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3
                }
            }}
        >
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        {title}
                    </Typography>
                    <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
                        {value}
                    </Typography>
                    {subtitle && (
                        <Typography variant="caption" color="text.secondary">
                            {subtitle}
                        </Typography>
                    )}
                </Box>
                <Avatar
                    sx={{
                        backgroundColor: alpha(color, 0.15),
                        color: color,
                        width: 40,
                        height: 40
                    }}
                >
                    {icon}
                </Avatar>
            </Box>
            {progress !== undefined && (
                <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                        mt: 1,
                        backgroundColor: alpha(color, 0.1),
                        '& .MuiLinearProgress-bar': {
                            backgroundColor: color
                        }
                    }}
                />
            )}
        </Paper>
    );
};

// Quick Action Card Component
const QuickActionCard = ({ title, icon, color, onClick, disabled = false }) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.6 : 1,
                borderRadius: 2,
                transition: 'all 0.2s ease',
                '&:hover': disabled ? {} : {
                    transform: 'translateY(-2px)',
                    boxShadow: 2,
                    backgroundColor: alpha(color, 0.05)
                }
            }}
            onClick={disabled ? undefined : onClick}
        >
            <Avatar
                sx={{
                    backgroundColor: alpha(color, 0.1),
                    color: color,
                    width: 32,
                    height: 32
                }}
            >
                {icon}
            </Avatar>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {title}
            </Typography>
        </Paper>
    );
};

// Atlas Canvas Component
const AtlasCanvas = ({ atlasData, selectedSquare, onSquareClick, zoom, setZoom }) => {
    const canvasRef = useRef(null);
    const theme = useTheme();

    useEffect(() => {
        if (!atlasData || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const scale = zoom;

        ctx.fillStyle = theme.palette.mode === 'dark' ? '#1a1a1a' : '#f5f5f5';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        atlasData.gridSquares.forEach(square => {
            const x = square.x * scale + canvas.width/2 - 500*scale;
            const y = square.y * scale + canvas.height/2 - 500*scale;
            const size = 90 * scale;

            if (square.quality === 'good') {
                ctx.fillStyle = square.collected ? '#10b98144' : '#10b98122';
                ctx.strokeStyle = '#10b981';
            } else if (square.quality === 'medium') {
                ctx.fillStyle = square.collected ? '#f59e0b44' : '#f59e0b22';
                ctx.strokeStyle = '#f59e0b';
            } else {
                ctx.fillStyle = square.collected ? '#ef444444' : '#ef444422';
                ctx.strokeStyle = '#ef4444';
            }

            ctx.fillRect(x, y, size, size);
            ctx.strokeRect(x, y, size, size);

            if (selectedSquare?.id === square.id) {
                ctx.strokeStyle = theme.palette.primary.main;
                ctx.lineWidth = 3;
                ctx.strokeRect(x-2, y-2, size+4, size+4);
                ctx.lineWidth = 1;
            }
        });

        if (atlasData.currentPosition) {
            const x = atlasData.currentPosition.x * scale + canvas.width/2 - 500*scale;
            const y = atlasData.currentPosition.y * scale + canvas.height/2 - 500*scale;

            ctx.strokeStyle = theme.palette.primary.main;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, 2 * Math.PI);
            ctx.stroke();
        }
    }, [atlasData, selectedSquare, zoom, theme]);

    return (
        <Box sx={{ position: 'relative' }}>
            <canvas
                ref={canvasRef}
                width={400}
                height={400}
                style={{
                    width: '100%',
                    backgroundColor: theme.palette.background.paper,
                    borderRadius: theme.shape.borderRadius,
                    cursor: 'crosshair',
                    border: `1px solid ${theme.palette.divider}`
                }}
                onClick={(e) => {
                    const rect = e.target.getBoundingClientRect();
                    const x = (e.clientX - rect.left) * (400 / rect.width);
                    const y = (e.clientY - rect.top) * (400 / rect.height);
                    // Handle square selection
                }}
            />

            <Box sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                display: 'flex',
                gap: 1
            }}>
                <IconButton
                    size="small"
                    onClick={() => setZoom(z => Math.min(z * 1.2, 3))}
                    sx={{ backgroundColor: alpha(theme.palette.background.paper, 0.8) }}
                >
                    <ZoomInIcon fontSize="small" />
                </IconButton>
                <IconButton
                    size="small"
                    onClick={() => setZoom(z => Math.max(z / 1.2, 0.5))}
                    sx={{ backgroundColor: alpha(theme.palette.background.paper, 0.8) }}
                >
                    <ZoomOutIcon fontSize="small" />
                </IconButton>
            </Box>

            {selectedSquare && (
                <Paper
                    elevation={3}
                    sx={{
                        position: 'absolute',
                        bottom: 8,
                        right: 8,
                        p: 1,
                        backgroundColor: alpha(theme.palette.background.paper, 0.9)
                    }}
                >
                    <Typography variant="caption" display="block">
                        Square: {selectedSquare.id}
                    </Typography>
                    <Typography variant="caption" display="block">
                        Ice: {selectedSquare.iceThickness?.toFixed(0)} nm
                    </Typography>
                </Paper>
            )}
        </Box>
    );
};

// Main Microscopy Page Component
export default function UnifiedMicroscopyPage() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Track drawer state
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    // Connection states
    const [isConnected, setIsConnected] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');

    // Microscope states
    const [microscopeStatus, setMicroscopeStatus] = useState(null);
    const [stagePosition, setStagePosition] = useState({ x: 12.345, y: -23.456, z: 0.234, alpha: 0.0, beta: 0.0 });
    const [opticalSettings, setOpticalSettings] = useState({
        magnification: 81000,
        defocus: -2.0,
        spotSize: 3,
        intensity: 0.00045,
        beamBlank: false
    });

    // Camera states
    const [acquisitionSettings, setAcquisitionSettings] = useState({
        exposure: 1000,
        binning: 1,
        saveFrames: false,
        electronCounting: true,
        mode: 'Counting'
    });

    // UI states
    const [isAcquiring, setIsAcquiring] = useState(false);
    const [activeTab, setActiveTab] = useState(0);
    const [lastImage, setLastImage] = useState(null);
    const [lastFFT, setLastFFT] = useState(null);
    const [showFFT, setShowFFT] = useState(false);
    const [acquisitionHistory, setAcquisitionHistory] = useState([]);
    const [showHistory, setShowHistory] = useState(false);
    const [showSettings, setShowSettings] = useState(false);

    // Atlas states
    const [atlasData, setAtlasData] = useState(null);
    const [selectedSquare, setSelectedSquare] = useState(null);
    const [atlasZoom, setAtlasZoom] = useState(1);

    // Advanced settings
    const [advancedSettings, setAdvancedSettings] = useState({
        driftCorrection: true,
        autoFocus: true,
        autoStigmation: false,
        doseProtection: true,
        targetDefocus: -2.0
    });

    // Presets
    const presets = [
        { id: 1, name: 'Atlas', mag: 200, defocus: -100, spot: 5 },
        { id: 2, name: 'Square', mag: 2000, defocus: -50, spot: 4 },
        { id: 3, name: 'Hole', mag: 10000, defocus: -10, spot: 3 },
        { id: 4, name: 'Focus', mag: 50000, defocus: -2, spot: 3 },
        { id: 5, name: 'Record', mag: 81000, defocus: -2, spot: 3 }
    ];

    // Calculate left margin
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    // Initialize connection
    useEffect(() => {
        microscopeAPI.on('connected', () => {
            setIsConnected(true);
            setConnectionStatus('connected');
            updateAllStatus();
        });

        microscopeAPI.on('disconnected', () => {
            setIsConnected(false);
            setConnectionStatus('disconnected');
        });

        microscopeAPI.on('acquisitionStarted', () => {
            setIsAcquiring(true);
        });

        microscopeAPI.on('acquisitionCompleted', (data) => {
            setIsAcquiring(false);
            setLastImage(data.image);
            setLastFFT(data.fft);
            setAcquisitionHistory(prev => [{
                id: Date.now(),
                timestamp: data.timestamp,
                settings: data.settings,
                thumbnail: data.image,
                fft: data.fft,
                metadata: data.metadata
            }, ...prev.slice(0, 19)]);
        });
    }, []);

    const updateAllStatus = async () => {
        try {
            const [microscope, atlas] = await Promise.all([
                microscopeAPI.getMicroscopeStatus(),
                microscopeAPI.getAtlasData()
            ]);
            setMicroscopeStatus(microscope);
            setAtlasData(atlas);
        } catch (error) {
            console.error('Failed to update status:', error);
        }
    };

    const handleConnect = () => {
        if (!isConnected) {
            setConnectionStatus('connecting');
            microscopeAPI.connect();
        } else {
            microscopeAPI.disconnect();
        }
    };

    const handleAcquireImage = async () => {
        try {
            await microscopeAPI.acquireImage(acquisitionSettings);
        } catch (error) {
            console.error('Failed to acquire image:', error);
        }
    };

    const handlePresetSelect = (preset) => {
        setOpticalSettings(prev => ({
            ...prev,
            magnification: preset.mag,
            defocus: preset.defocus,
            spotSize: preset.spot
        }));
    };

    // Quick Actions
    const quickActions = [
        { title: 'Eucentric Height', icon: <TargetIcon />, color: '#2196f3', action: () => {} },
        { title: 'Auto Focus', icon: <Focus size={20} />, color: '#4caf50', action: () => {} },
        { title: 'Auto Stigmate', icon: <ScanLine size={20} />, color: '#ff9800', action: () => {} },
        { title: 'Drift Measure', icon: <Activity size={20} />, color: '#9c27b0', action: () => {} },
        { title: 'Acquire Atlas', icon: <GridIcon />, color: '#f44336', action: () => {} },
        { title: 'Reset Stage', icon: <MapPin size={20} />, color: '#607d8b', action: () => {} }
    ];

    // Status indicators
    const statusCards = [
        {
            title: 'Microscope',
            value: microscopeStatus?.model || 'Disconnected',
            subtitle: isConnected ? 'Ready' : 'Not Connected',
            icon: <ScienceIcon />,
            color: isConnected ? '#4caf50' : '#f44336'
        },
        {
            title: 'High Tension',
            value: microscopeStatus ? `${microscopeStatus.highTension / 1000} kV` : '--',
            subtitle: 'Stable',
            icon: <Zap size={20} />,
            color: '#ff9800'
        },
        {
            title: 'Temperature',
            value: microscopeStatus ? `${microscopeStatus.temperature.toFixed(1)}°C` : '--',
            subtitle: 'Optimal',
            icon: <ThermostatIcon />,
            color: '#2196f3'
        },
        {
            title: 'Vacuum',
            value: '5.2e-8 Pa',
            subtitle: 'Excellent',
            icon: <SpeedIcon />,
            color: '#4caf50'
        }
    ];

    return (
        <Box sx={{
            position: 'fixed',
            top: 64,
            left: leftMargin,
            right: 0,
            bottom: 0,
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Scrollable Content */}
            <Box sx={{ flex: 1, overflow: 'auto', p: { xs: 1, sm: 2, md: 3 } }}>
                {/* Header */}
                <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Typography variant={isMobile ? "h5" : "h4"} component="h1" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Zap size={isMobile ? 24 : 32} color={theme.palette.primary.main} />
                            Microscope Control System
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Advanced control interface for Titan Krios & Direct Electron cameras
                        </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            variant={isConnected ? "outlined" : "contained"}
                            color={isConnected ? "error" : "primary"}
                            onClick={handleConnect}
                            disabled={connectionStatus === 'connecting'}
                            startIcon={connectionStatus === 'connecting' ? <CircularProgress size={16} /> : <Monitor size={16} />}
                        >
                            {connectionStatus === 'connecting' ? 'Connecting...' : isConnected ? 'Disconnect' : 'Connect'}
                        </Button>

                        <IconButton onClick={() => setShowHistory(true)}>
                            <Badge badgeContent={acquisitionHistory.length} color="primary">
                                <HistoryIcon />
                            </Badge>
                        </IconButton>
                    </Box>
                </Box>

                {/* Status Cards */}
                <Grid container spacing={2} sx={{ mb: 3 }}>
                    {statusCards.map((card, index) => (
                        <Grid item xs={6} md={3} key={index}>
                            <StatusCard {...card} />
                        </Grid>
                    ))}
                </Grid>

                {/* Quick Actions */}
                <Paper elevation={1} sx={{ p: 2, mb: 3, borderRadius: 2 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                        Quick Actions
                    </Typography>
                    <Grid container spacing={1}>
                        {quickActions.map((action, index) => (
                            <Grid item xs={6} sm={4} md={2} key={index}>
                                <QuickActionCard
                                    {...action}
                                    disabled={!isConnected}
                                    onClick={action.action}
                                />
                            </Grid>
                        ))}
                    </Grid>
                </Paper>

                {/* Main Content */}
                <Grid container spacing={3}>
                    {/* Left Column - Atlas and Image */}
                    <Grid item xs={12} lg={4}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, height: '100%' }}>
                            {/* Atlas View */}
                            <Card>
                                <CardHeader
                                    title={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <NavigationIcon />
                                            <Typography variant="h6">Grid Atlas</Typography>
                                        </Box>
                                    }
                                    action={
                                        <Chip
                                            label={`${atlasData?.gridSquares?.length || 0} squares`}
                                            size="small"
                                            color="primary"
                                            variant="outlined"
                                        />
                                    }
                                />
                                <CardContent>
                                    {atlasData ? (
                                        <AtlasCanvas
                                            atlasData={atlasData}
                                            selectedSquare={selectedSquare}
                                            onSquareClick={setSelectedSquare}
                                            zoom={atlasZoom}
                                            setZoom={setAtlasZoom}
                                        />
                                    ) : (
                                        <Box sx={{
                                            height: 300,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            backgroundColor: 'action.hover',
                                            borderRadius: 1
                                        }}>
                                            <Typography color="text.secondary">
                                                {isConnected ? 'Loading atlas...' : 'Connect to view atlas'}
                                            </Typography>
                                        </Box>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Image Viewer */}
                            <Card sx={{ flex: 1 }}>
                                <CardHeader
                                    title={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <CameraIcon />
                                            <Typography variant="h6">Live View</Typography>
                                        </Box>
                                    }
                                    action={
                                        <Box sx={{ display: 'flex', gap: 1 }}>
                                            <IconButton
                                                size="small"
                                                onClick={() => setShowFFT(!showFFT)}
                                                color={showFFT ? "primary" : "default"}
                                            >
                                                {showFFT ? <VisibilityIcon /> : <VisibilityOffIcon />}
                                            </IconButton>
                                            <IconButton size="small">
                                                <FullscreenIcon />
                                            </IconButton>
                                        </Box>
                                    }
                                />
                                <CardContent>
                                    <Box sx={{
                                        aspectRatio: '1',
                                        backgroundColor: 'action.hover',
                                        borderRadius: 1,
                                        overflow: 'hidden',
                                        position: 'relative'
                                    }}>
                                        {lastImage ? (
                                            <>
                                                <img
                                                    src={lastImage}
                                                    alt="Acquired"
                                                    style={{
                                                        width: '100%',
                                                        height: '100%',
                                                        objectFit: 'contain'
                                                    }}
                                                />
                                                {showFFT && lastFFT && (
                                                    <Paper
                                                        elevation={3}
                                                        sx={{
                                                            position: 'absolute',
                                                            bottom: 8,
                                                            right: 8,
                                                            width: 80,
                                                            height: 80,
                                                            overflow: 'hidden',
                                                            border: `2px solid ${theme.palette.primary.main}`
                                                        }}
                                                    >
                                                        <img
                                                            src={lastFFT}
                                                            alt="FFT"
                                                            style={{
                                                                width: '100%',
                                                                height: '100%',
                                                                objectFit: 'contain'
                                                            }}
                                                        />
                                                    </Paper>
                                                )}
                                            </>
                                        ) : (
                                            <Box sx={{
                                                width: '100%',
                                                height: '100%',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center'
                                            }}>
                                                <CameraIcon sx={{ fontSize: 48, color: 'text.secondary' }} />
                                            </Box>
                                        )}
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                    </Grid>

                    {/* Right Column - Controls */}
                    <Grid item xs={12} lg={8}>
                        <Card sx={{ height: '100%' }}>
                            <CardHeader
                                title="Control Panel"
                                action={
                                    <IconButton onClick={() => setShowSettings(true)}>
                                        <SettingsIcon />
                                    </IconButton>
                                }
                            />
                            <CardContent>
                                <Tabs
                                    value={activeTab}
                                    onChange={(e, newValue) => setActiveTab(newValue)}
                                    sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}
                                >
                                    <Tab label="Control" />
                                    <Tab label="Presets" />
                                    <Tab label="Automation" />
                                </Tabs>

                                {/* Control Tab */}
                                {activeTab === 0 && (
                                    <Grid container spacing={3}>
                                        {/* Stage Control */}
                                        <Grid item xs={12} md={6}>
                                            <Paper elevation={1} sx={{ p: 2, borderRadius: 2 }}>
                                                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Move size={20} />
                                                    Stage Position
                                                </Typography>

                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                                    {['x', 'y', 'z'].map(axis => (
                                                        <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <Typography sx={{ minWidth: 20, fontWeight: 'bold' }}>
                                                                {axis.toUpperCase()}:
                                                            </Typography>
                                                            <IconButton size="small" disabled={!isConnected}>
                                                                <ChevronLeft size={16} />
                                                            </IconButton>
                                                            <TextField
                                                                size="small"
                                                                value={stagePosition[axis].toFixed(axis === 'z' ? 3 : 1)}
                                                                disabled={!isConnected}
                                                                InputProps={{
                                                                    endAdornment: (
                                                                        <Typography variant="caption" color="text.secondary">
                                                                            μm
                                                                        </Typography>
                                                                    )
                                                                }}
                                                                sx={{ width: 120 }}
                                                            />
                                                            <IconButton size="small" disabled={!isConnected}>
                                                                <ChevronRight size={16} />
                                                            </IconButton>
                                                        </Box>
                                                    ))}

                                                    {/* Angular positions */}
                                                    <Divider sx={{ my: 1 }} />
                                                    {['alpha', 'beta'].map(axis => (
                                                        <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <Typography sx={{ minWidth: 20, fontWeight: 'bold' }}>
                                                                {axis === 'alpha' ? 'α' : 'β'}:
                                                            </Typography>
                                                            <TextField
                                                                size="small"
                                                                value={(stagePosition[axis] * 180 / Math.PI).toFixed(1)}
                                                                disabled={!isConnected}
                                                                InputProps={{
                                                                    endAdornment: (
                                                                        <Typography variant="caption" color="text.secondary">
                                                                            °
                                                                        </Typography>
                                                                    )
                                                                }}
                                                                sx={{ width: 120, ml: 3 }}
                                                            />
                                                        </Box>
                                                    ))}
                                                </Box>
                                            </Paper>
                                        </Grid>

                                        {/* Optical Settings */}
                                        <Grid item xs={12} md={6}>
                                            <Paper elevation={1} sx={{ p: 2, borderRadius: 2 }}>
                                                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Focus size={20} />
                                                    Optical Settings
                                                </Typography>

                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                                    <FormControl size="small" fullWidth>
                                                        <InputLabel>Magnification</InputLabel>
                                                        <Select
                                                            value={opticalSettings.magnification}
                                                            onChange={(e) => setOpticalSettings(prev => ({ ...prev, magnification: e.target.value }))}
                                                            disabled={!isConnected}
                                                            label="Magnification"
                                                        >
                                                            <MenuItem value={2000}>2,000x</MenuItem>
                                                            <MenuItem value={5000}>5,000x</MenuItem>
                                                            <MenuItem value={10000}>10,000x</MenuItem>
                                                            <MenuItem value={25000}>25,000x</MenuItem>
                                                            <MenuItem value={50000}>50,000x</MenuItem>
                                                            <MenuItem value={81000}>81,000x</MenuItem>
                                                            <MenuItem value={105000}>105,000x</MenuItem>
                                                        </Select>
                                                    </FormControl>

                                                    <TextField
                                                        size="small"
                                                        label="Defocus"
                                                        type="number"
                                                        value={opticalSettings.defocus}
                                                        onChange={(e) => setOpticalSettings(prev => ({ ...prev, defocus: parseFloat(e.target.value) }))}
                                                        disabled={!isConnected}
                                                        InputProps={{
                                                            endAdornment: (
                                                                <Typography variant="caption" color="text.secondary">
                                                                    μm
                                                                </Typography>
                                                            )
                                                        }}
                                                    />

                                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                                        <TextField
                                                            size="small"
                                                            label="Spot Size"
                                                            type="number"
                                                            value={opticalSettings.spotSize}
                                                            onChange={(e) => setOpticalSettings(prev => ({ ...prev, spotSize: parseInt(e.target.value) }))}
                                                            disabled={!isConnected}
                                                            sx={{ flex: 1 }}
                                                        />
                                                        <TextField
                                                            size="small"
                                                            label="Intensity"
                                                            type="number"
                                                            value={opticalSettings.intensity}
                                                            onChange={(e) => setOpticalSettings(prev => ({ ...prev, intensity: parseFloat(e.target.value) }))}
                                                            disabled={!isConnected}
                                                            sx={{ flex: 1 }}
                                                        />
                                                    </Box>

                                                    <FormControlLabel
                                                        control={
                                                            <Switch
                                                                checked={opticalSettings.beamBlank}
                                                                onChange={(e) => setOpticalSettings(prev => ({ ...prev, beamBlank: e.target.checked }))}
                                                                disabled={!isConnected}
                                                            />
                                                        }
                                                        label="Beam Blank"
                                                    />
                                                </Box>
                                            </Paper>
                                        </Grid>

                                        {/* Acquisition Settings */}
                                        <Grid item xs={12}>
                                            <Paper elevation={1} sx={{ p: 2, borderRadius: 2 }}>
                                                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <CameraIcon />
                                                    Acquisition Settings
                                                </Typography>

                                                <Grid container spacing={2} sx={{ mb: 3 }}>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <TextField
                                                            size="small"
                                                            label="Exposure"
                                                            type="number"
                                                            value={acquisitionSettings.exposure}
                                                            onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, exposure: parseInt(e.target.value) }))}
                                                            disabled={!isConnected}
                                                            fullWidth
                                                            InputProps={{
                                                                endAdornment: (
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        ms
                                                                    </Typography>
                                                                )
                                                            }}
                                                        />
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <FormControl size="small" fullWidth>
                                                            <InputLabel>Binning</InputLabel>
                                                            <Select
                                                                value={acquisitionSettings.binning}
                                                                onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, binning: parseInt(e.target.value) }))}
                                                                disabled={!isConnected}
                                                                label="Binning"
                                                            >
                                                                <MenuItem value={1}>1x1</MenuItem>
                                                                <MenuItem value={2}>2x2</MenuItem>
                                                                <MenuItem value={4}>4x4</MenuItem>
                                                                <MenuItem value={8}>8x8</MenuItem>
                                                            </Select>
                                                        </FormControl>
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <FormControlLabel
                                                            control={
                                                                <Switch
                                                                    checked={acquisitionSettings.electronCounting}
                                                                    onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, electronCounting: e.target.checked }))}
                                                                    disabled={!isConnected}
                                                                />
                                                            }
                                                            label="Electron Counting"
                                                        />
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <FormControlLabel
                                                            control={
                                                                <Switch
                                                                    checked={acquisitionSettings.saveFrames}
                                                                    onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, saveFrames: e.target.checked }))}
                                                                    disabled={!isConnected}
                                                                />
                                                            }
                                                            label="Save Frames"
                                                        />
                                                    </Grid>
                                                </Grid>

                                                <Button
                                                    variant="contained"
                                                    size="large"
                                                    fullWidth
                                                    onClick={handleAcquireImage}
                                                    disabled={!isConnected || isAcquiring}
                                                    startIcon={isAcquiring ? <CircularProgress size={20} /> : <CameraIcon />}
                                                    sx={{ py: 1.5 }}
                                                >
                                                    {isAcquiring ? 'Acquiring...' : 'Acquire Image'}
                                                </Button>
                                            </Paper>
                                        </Grid>
                                    </Grid>
                                )}

                                {/* Presets Tab */}
                                {activeTab === 1 && (
                                    <Grid container spacing={2}>
                                        {presets.map(preset => (
                                            <Grid item xs={12} sm={6} md={4} key={preset.id}>
                                                <Paper
                                                    elevation={1}
                                                    sx={{
                                                        p: 2,
                                                        cursor: 'pointer',
                                                        borderRadius: 2,
                                                        transition: 'all 0.2s ease',
                                                        '&:hover': {
                                                            transform: 'translateY(-2px)',
                                                            boxShadow: 3,
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.05)
                                                        }
                                                    }}
                                                    onClick={() => handlePresetSelect(preset)}
                                                >
                                                    <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                                                        {preset.name}
                                                    </Typography>
                                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                                        <Typography variant="body2" color="text.secondary">
                                                            Magnification: {preset.mag.toLocaleString()}x
                                                        </Typography>
                                                        <Typography variant="body2" color="text.secondary">
                                                            Defocus: {preset.defocus} μm
                                                        </Typography>
                                                        <Typography variant="body2" color="text.secondary">
                                                            Spot Size: {preset.spot}
                                                        </Typography>
                                                    </Box>
                                                </Paper>
                                            </Grid>
                                        ))}
                                    </Grid>
                                )}

                                {/* Automation Tab */}
                                {activeTab === 2 && (
                                    <Grid container spacing={3}>
                                        <Grid item xs={12} md={6}>
                                            <Paper elevation={1} sx={{ p: 2, borderRadius: 2 }}>
                                                <Typography variant="h6" sx={{ mb: 2 }}>
                                                    Auto Functions
                                                </Typography>

                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                                    <FormControlLabel
                                                        control={
                                                            <Switch
                                                                checked={advancedSettings.autoFocus}
                                                                onChange={(e) => setAdvancedSettings(prev => ({ ...prev, autoFocus: e.target.checked }))}
                                                            />
                                                        }
                                                        label="Auto Focus"
                                                    />
                                                    <FormControlLabel
                                                        control={
                                                            <Switch
                                                                checked={advancedSettings.driftCorrection}
                                                                onChange={(e) => setAdvancedSettings(prev => ({ ...prev, driftCorrection: e.target.checked }))}
                                                            />
                                                        }
                                                        label="Drift Correction"
                                                    />
                                                    <FormControlLabel
                                                        control={
                                                            <Switch
                                                                checked={advancedSettings.autoStigmation}
                                                                onChange={(e) => setAdvancedSettings(prev => ({ ...prev, autoStigmation: e.target.checked }))}
                                                            />
                                                        }
                                                        label="Auto Stigmation"
                                                    />
                                                    <FormControlLabel
                                                        control={
                                                            <Switch
                                                                checked={advancedSettings.doseProtection}
                                                                onChange={(e) => setAdvancedSettings(prev => ({ ...prev, doseProtection: e.target.checked }))}
                                                            />
                                                        }
                                                        label="Dose Protection"
                                                    />
                                                </Box>
                                            </Paper>
                                        </Grid>

                                        <Grid item xs={12} md={6}>
                                            <Paper elevation={1} sx={{ p: 2, borderRadius: 2 }}>
                                                <Typography variant="h6" sx={{ mb: 2 }}>
                                                    Defocus Settings
                                                </Typography>

                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                                    <TextField
                                                        size="small"
                                                        label="Target Defocus"
                                                        type="number"
                                                        value={advancedSettings.targetDefocus}
                                                        onChange={(e) => setAdvancedSettings(prev => ({ ...prev, targetDefocus: parseFloat(e.target.value) }))}
                                                        InputProps={{
                                                            endAdornment: (
                                                                <Typography variant="caption" color="text.secondary">
                                                                    μm
                                                                </Typography>
                                                            )
                                                        }}
                                                    />

                                                    <Box sx={{ mt: 2 }}>
                                                        <Typography gutterBottom>
                                                            Defocus Range: ±0.5 μm
                                                        </Typography>
                                                        <Slider
                                                            value={0.5}
                                                            min={0.1}
                                                            max={2.0}
                                                            step={0.1}
                                                            marks
                                                            valueLabelDisplay="auto"
                                                            valueLabelFormat={(value) => `±${value} μm`}
                                                        />
                                                    </Box>
                                                </Box>
                                            </Paper>
                                        </Grid>
                                    </Grid>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            </Box>

            {/* History Drawer */}
            <Drawer
                anchor="right"
                open={showHistory}
                onClose={() => setShowHistory(false)}
                PaperProps={{
                    sx: { width: { xs: '100%', sm: 400 } }
                }}
            >
                <Box sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Acquisition History</Typography>
                        <IconButton onClick={() => setShowHistory(false)}>
                            <CloseIcon />
                        </IconButton>
                    </Box>

                    <List>
                        {acquisitionHistory.length === 0 ? (
                            <ListItem>
                                <ListItemText
                                    primary="No acquisitions yet"
                                    secondary="Start acquiring images to see them here"
                                />
                            </ListItem>
                        ) : (
                            acquisitionHistory.map(item => (
                                <ListItem key={item.id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, mb: 1 }}>
                                    <Box sx={{ display: 'flex', gap: 2, width: '100%' }}>
                                        <Box sx={{ position: 'relative' }}>
                                            <img
                                                src={item.thumbnail}
                                                alt="Thumbnail"
                                                style={{
                                                    width: 60,
                                                    height: 60,
                                                    objectFit: 'cover',
                                                    borderRadius: 4
                                                }}
                                            />
                                            {item.fft && (
                                                <Chip
                                                    label="FFT"
                                                    size="small"
                                                    color="primary"
                                                    sx={{
                                                        position: 'absolute',
                                                        bottom: -8,
                                                        right: -8,
                                                        fontSize: '0.6rem',
                                                        height: 16
                                                    }}
                                                />
                                            )}
                                        </Box>
                                        <Box sx={{ flex: 1 }}>
                                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                                {new Date(item.timestamp).toLocaleTimeString()}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" display="block">
                                                {item.settings.exposure}ms • {item.settings.binning}x{item.settings.binning}
                                                {item.settings.electronCounting && ' • Counting'}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" display="block">
                                                Defocus: {item.metadata.defocus.toFixed(1)}μm •
                                                Dose: {item.metadata.dose.toFixed(1)} e⁻/Å²
                                            </Typography>
                                        </Box>
                                    </Box>
                                </ListItem>
                            ))
                        )}
                    </List>
                </Box>
            </Drawer>

            {/* Settings Dialog */}
            <Dialog
                open={showSettings}
                onClose={() => setShowSettings(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Advanced Settings</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary">
                        Advanced microscope and camera configuration options would go here.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowSettings(false)}>Cancel</Button>
                    <Button onClick={() => setShowSettings(false)} variant="contained">Apply</Button>
                </DialogActions>
            </Dialog>

            {/* Connection Status Snackbar */}
            <Snackbar
                open={connectionStatus === 'connecting'}
                message="Connecting to microscope..."
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            />
        </Box>
    );
}