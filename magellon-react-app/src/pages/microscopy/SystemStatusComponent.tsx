import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Chip,
    Stack,
    Divider,
    LinearProgress,
    useTheme,
    alpha,
    IconButton,
    Tooltip,
    Badge,
    Button,
    Collapse,
    CircularProgress,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
    Zap,
    Thermometer,
    Droplets,
    Activity,
    Camera,
    Monitor,
    CheckCircle,
    AlertTriangle,
    XCircle,
    Settings,
    Gauge,
    Database,
    Wifi,
    WifiOff,
    ChevronDown,
    ChevronUp,
} from 'lucide-react';

// Mock data - replace with real data from your store/API
const mockSystemStatus = {
    microscope: {
        connected: true,
        model: 'Titan Krios G4',
        highTension: 300000,
        columnValve: 'open',
        vacuumStatus: 'ready',
        temperature: -192.3,
        autoloader: 'ready',
        refrigerantLevel: 85,
        beamCurrent: 150, // pA
        gun: {
            status: 'ready',
            emission: 4.2, // µA
        }
    },
    camera: {
        connected: true,
        model: 'DE-64',
        temperature: -15.2,
        mode: 'Integrating',
        fps: 40,
        binning: '1x1',
        status: 'ready',
        exposure: 1.0,
        frameCount: 40,
    },
    system: {
        dataPath: '/data/acquisitions',
        diskSpace: 75, // percentage used
        networkStatus: 'connected',
        lastUpdate: new Date(),
    }
};

interface StatusIndicatorProps {
    status: 'ready' | 'warning' | 'error' | 'offline';
    label: string;
    size?: 'small' | 'medium';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status, label, size = 'small' }) => {
    const getStatusConfig = () => {
        switch (status) {
            case 'ready':
                return { icon: CheckCircle, color: 'success.main', bgColor: 'success.light' };
            case 'warning':
                return { icon: AlertTriangle, color: 'warning.main', bgColor: 'warning.light' };
            case 'error':
                return { icon: XCircle, color: 'error.main', bgColor: 'error.light' };
            case 'offline':
                return { icon: WifiOff, color: 'grey.500', bgColor: 'grey.200' };
            default:
                return { icon: CheckCircle, color: 'success.main', bgColor: 'success.light' };
        }
    };

    const { icon: Icon, color, bgColor } = getStatusConfig();
    const iconSize = size === 'small' ? 14 : 18;

    return (
        <Chip
            icon={<Icon size={iconSize} />}
            label={label}
            size={size}
            variant="outlined"
            sx={{
                color,
                borderColor: color,
                backgroundColor: (theme) => alpha(theme.palette[bgColor.split('.')[0]][bgColor.split('.')[1]], 0.1),
                '& .MuiChip-icon': { color },
                fontWeight: 500,
            }}
        />
    );
};

interface MetricItemProps {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    unit?: string;
    color?: string;
    progress?: number;
}

const MetricItem: React.FC<MetricItemProps> = ({
                                                   icon,
                                                   label,
                                                   value,
                                                   unit = '',
                                                   color = 'text.primary',
                                                   progress
                                               }) => {
    const theme = useTheme();

    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
            <Box sx={{ color: color, flexShrink: 0 }}>
                {icon}
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    {label}
                </Typography>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 600,
                        fontSize: '0.875rem',
                        color: color,
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: 0.5
                    }}
                >
                    {value}
                    {unit && (
                        <Typography component="span" variant="caption" color="text.secondary">
                            {unit}
                        </Typography>
                    )}
                </Typography>
                {progress !== undefined && (
                    <LinearProgress
                        variant="determinate"
                        value={progress}
                        sx={{
                            height: 3,
                            borderRadius: 1.5,
                            mt: 0.5,
                            backgroundColor: alpha(theme.palette.grey[300], 0.3),
                            '& .MuiLinearProgress-bar': {
                                backgroundColor: progress > 80 ? theme.palette.warning.main : theme.palette.primary.main,
                            }
                        }}
                    />
                )}
            </Box>
        </Box>
    );
};

interface SystemStatusComponentProps {
    // Connection-related props
    isConnected?: boolean;
    connectionStatus?: 'connected' | 'connecting' | 'disconnected';
    onConnect?: () => void;

    // Camera-related props
    cameraConnected?: boolean;
    cameraLoading?: boolean;
    onCameraSettings?: () => void;

    // Collapsible state
    defaultExpanded?: boolean;
}

export const SystemStatusComponent: React.FC<SystemStatusComponentProps> = ({
                                                                                isConnected = false,
                                                                                connectionStatus = 'disconnected',
                                                                                onConnect,
                                                                                cameraConnected = false,
                                                                                cameraLoading = false,
                                                                                onCameraSettings,
                                                                                defaultExpanded = true
                                                                            }) => {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const status = mockSystemStatus; // Replace with actual data from props or store
    const [expanded, setExpanded] = useState(defaultExpanded);

    const handleConnect = () => {
        if (onConnect) {
            onConnect();
        }
    };

    const handleCameraSettings = () => {
        if (onCameraSettings) {
            onCameraSettings();
        }
    };

    return (
        <Card
            elevation={2}
            sx={{
                borderRadius: 3,
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                background: isDark
                    ? `linear-gradient(135deg, ${alpha(theme.palette.background.paper, 0.9)} 0%, ${alpha(theme.palette.background.default, 0.95)} 100%)`
                    : `linear-gradient(135deg, ${alpha(theme.palette.background.paper, 1)} 0%, ${alpha(theme.palette.grey[50], 0.8)} 100%)`,
                backdropFilter: 'blur(10px)',
                transition: 'all 0.3s ease-in-out',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: theme.shadows[8],
                }
            }}
        >
            <CardContent sx={{ p: 3 }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Activity size={24} color={theme.palette.primary.main} />
                        <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary' }}>
                            System Status
                        </Typography>
                        <IconButton
                            size="small"
                            onClick={() => setExpanded(!expanded)}
                            sx={{ ml: 1 }}
                        >
                            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                        </IconButton>
                    </Box>

                    <Stack direction="row" spacing={1} alignItems="center">
                        <StatusIndicator
                            status={status.microscope.connected ? 'ready' : 'offline'}
                            label="Microscope"
                        />
                        <StatusIndicator
                            status={status.camera.connected ? 'ready' : 'offline'}
                            label="Camera"
                        />
                        <Tooltip title="System Settings">
                            <IconButton size="small" sx={{ ml: 1 }}>
                                <Settings size={18} />
                            </IconButton>
                        </Tooltip>
                    </Stack>
                </Box>

                {/* Collapsible Content */}
                <Collapse in={expanded} timeout="auto">
                    {/* Main Content Grid */}
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                        {/* Microscope Section */}
                        <Grid xs={12} size={4}>
                            <Box sx={{
                                p: 2,
                                borderRadius: 2,
                                backgroundColor: alpha(theme.palette.primary.main, 0.04),
                                border: `1px solid ${alpha(theme.palette.primary.main, 0.12)}`,
                                height: '100%'
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                    <Monitor size={18} color={theme.palette.primary.main} />
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                                        {status.microscope.model}
                                    </Typography>
                                </Box>

                                <Grid container spacing={1.5}>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Zap size={14} />}
                                            label="High Tension"
                                            value={(status.microscope.highTension / 1000).toFixed(0)}
                                            unit="kV"
                                            color="primary.main"
                                        />
                                        
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Gauge size={14} />}
                                            label="Beam Current"
                                            value={status.microscope.beamCurrent}
                                            unit="pA"
                                            color="primary.main"
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Thermometer size={14} />}
                                            label="Cryo Temp"
                                            value={status.microscope.temperature}
                                            unit="°C"
                                            color="info.main"
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Droplets size={14} />}
                                            label="Refrigerant Level"
                                            value={status.microscope.refrigerantLevel}
                                            unit="%"
                                            color={status.microscope.refrigerantLevel < 20 ? "warning.main" : "success.main"}
                                            progress={status.microscope.refrigerantLevel}
                                        />
                                    </Grid>
                                </Grid>
                            </Box>
                        </Grid>

                        {/* Camera Section */}
                        <Grid xs={12} size={4}>
                            <Box sx={{
                                p: 2,
                                borderRadius: 2,
                                backgroundColor: alpha(theme.palette.secondary.main, 0.04),
                                border: `1px solid ${alpha(theme.palette.secondary.main, 0.12)}`,
                                height: '100%'
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                    <Camera size={18} color={theme.palette.secondary.main} />
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'secondary.main' }}>
                                        {status.camera.model}
                                    </Typography>
                                </Box>

                                <Grid container spacing={1.5}>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Settings size={14} />}
                                            label="Mode"
                                            value={status.camera.mode}
                                            color="secondary.main"
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Activity size={14} />}
                                            label="Frame Rate"
                                            value={status.camera.fps}
                                            unit="FPS"
                                            color="secondary.main"
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Thermometer size={14} />}
                                            label="Detector Temp"
                                            value={status.camera.temperature}
                                            unit="°C"
                                            color="info.main"
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Gauge size={14} />}
                                            label="Exposure"
                                            value={status.camera.exposure}
                                            unit="s"
                                            color="secondary.main"
                                        />
                                    </Grid>
                                </Grid>
                            </Box>
                        </Grid>

                        {/* System Resources Section */}
                        <Grid xs={12} size={4}>
                            <Box sx={{
                                p: 2,
                                borderRadius: 2,
                                backgroundColor: alpha(theme.palette.success.main, 0.04),
                                border: `1px solid ${alpha(theme.palette.success.main, 0.12)}`,
                                height: '100%'
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                    <Database size={18} color={theme.palette.success.main} />
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'success.main' }}>
                                        System Resources
                                    </Typography>
                                </Box>

                                <Grid container spacing={1.5}>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={status.system.networkStatus === 'connected' ? <Wifi size={14} /> : <WifiOff size={14} />}
                                            label="Network"
                                            value={status.system.networkStatus === 'connected' ? 'Connected' : 'Offline'}
                                            color={status.system.networkStatus === 'connected' ? "success.main" : "error.main"}
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <MetricItem
                                            icon={<Database size={14} />}
                                            label="Storage"
                                            value={status.system.diskSpace}
                                            unit="%"
                                            color={status.system.diskSpace > 90 ? "error.main" : status.system.diskSpace > 75 ? "warning.main" : "success.main"}
                                            progress={status.system.diskSpace}
                                        />
                                    </Grid>
                                    <Grid size={3}>
                                        <Box sx={{ pt: 1 }}>
                                            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                                                CPU
                                            </Typography>
                                            <Typography
                                                variant="body2"
                                                sx={{
                                                    fontWeight: 600,
                                                    fontSize: '0.875rem',
                                                    color: 'text.primary',
                                                    display: 'flex',
                                                    alignItems: 'baseline',
                                                    gap: 0.5
                                                }}
                                            >
                                                75%
                                                <Typography component="span" variant="caption" color="text.secondary">
                                                    Used
                                                </Typography>
                                            </Typography>
                                            <LinearProgress
                                                variant="determinate"
                                                value={75}
                                                sx={{
                                                    height: 3,
                                                    borderRadius: 1.5,
                                                    mt: 0.5,
                                                    backgroundColor: alpha(theme.palette.grey[300], 0.3),
                                                    '& .MuiLinearProgress-bar': {
                                                        backgroundColor: 75 > 80 ? theme.palette.warning.main : theme.palette.primary.main,
                                                    }
                                                }}
                                            />
                                        </Box>
                                    </Grid>
                                    <Grid size={3}>
                                        <Box sx={{ pt: 1 }}>
                                            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                                                Memory
                                            </Typography>
                                            <Typography
                                                variant="body2"
                                                sx={{
                                                    fontWeight: 600,
                                                    fontSize: '0.875rem',
                                                    color: 'text.primary',
                                                    display: 'flex',
                                                    alignItems: 'baseline',
                                                    gap: 0.5
                                                }}
                                            >
                                                60%
                                                <Typography component="span" variant="caption" color="text.secondary">
                                                    Used
                                                </Typography>
                                            </Typography>
                                            <LinearProgress
                                                variant="determinate"
                                                value={60}
                                                sx={{
                                                    height: 3,
                                                    borderRadius: 1.5,
                                                    mt: 0.5,
                                                    backgroundColor: alpha(theme.palette.grey[300], 0.3),
                                                    '& .MuiLinearProgress-bar': {
                                                        backgroundColor: 60 > 80 ? theme.palette.warning.main : theme.palette.primary.main,
                                                    }
                                                }}
                                            />
                                        </Box>
                                    </Grid>
                                </Grid>
                            </Box>
                        </Grid>
                    </Grid>
                </Collapse>

                {/* Quick Actions - Now includes the main control buttons */}
                <Box sx={{
                    pt: expanded ? 2 : 0,
                    borderTop: expanded ? `1px solid ${alpha(theme.palette.divider, 0.1)}` : 'none',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <Typography variant="caption" color="text.secondary">
                        System operational • All subsystems nominal
                    </Typography>

                    <Stack direction="row" spacing={1}>
                        {/* Connection Button - Moved from MicroscopyPageView */}
                        <Button
                            variant={isConnected ? "outlined" : "contained"}
                            color={isConnected ? "error" : "primary"}
                            onClick={handleConnect}
                            disabled={connectionStatus === 'connecting'}
                            startIcon={connectionStatus === 'connecting' ? <CircularProgress size={16} /> : <Monitor size={16} />}
                            size="small"
                        >
                            {connectionStatus === 'connecting' ? 'Connecting...' : isConnected ? 'Disconnect' : 'Connect'}
                        </Button>

                        {/* Camera Settings Button - Moved from MicroscopyPageView */}
                        <Button
                            variant="outlined"
                            onClick={handleCameraSettings}
                            disabled={!cameraConnected || cameraLoading}
                            startIcon={cameraLoading ? <CircularProgress size={16} /> : <Camera size={16} />}
                            size="small"
                        >
                            Camera Settings
                        </Button>

                        {/* Live Status Chip */}
                        <Chip
                            label="Live"
                            size="small"
                            color="success"
                            variant="filled"
                            sx={{
                                animation: 'pulse 2s infinite',
                                '@keyframes pulse': {
                                    '0%': { opacity: 1 },
                                    '50%': { opacity: 0.7 },
                                    '100%': { opacity: 1 }
                                }
                            }}
                        />
                    </Stack>
                </Box>
            </CardContent>
        </Card>
    );
};