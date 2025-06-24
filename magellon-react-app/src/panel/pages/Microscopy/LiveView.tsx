import React, { useState, useEffect } from 'react';
import {
    Card,
    CardHeader,
    CardContent,
    Typography,
    Box,
    Paper,
    IconButton,
    Switch,
    FormControlLabel,
    Tabs,
    Tab,
    CircularProgress,
    alpha,
    useTheme,
    Chip,
    Alert,
    Slider,
    Grid,
    Button
} from '@mui/material';
import {
    PlayArrow as PlayIcon,
    Stop as StopIcon,
    Fullscreen as FullscreenIcon,
    Settings as SettingsIcon,
    PhotoCamera as PhotoCameraIcon,
    Visibility as VisibilityIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    Refresh as RefreshIcon
} from '@mui/icons-material';
import { Eye, Monitor, Activity, Camera } from 'lucide-react';

// Import store hook
import { useMicroscopeStore } from './MicroscopeStore';

interface LiveViewProps {
    // Add any additional props if needed
}

export const LiveView: React.FC<LiveViewProps> = () => {
    const theme = useTheme();

    // Get state from store
    const {
        lastImage,
        lastFFT,
        isConnected,
        isAcquiring,
        showFFT,
        setShowFFT,
        opticalSettings,
        acquisitionSettings
    } = useMicroscopeStore();

    // Local state
    const [isLiveMode, setIsLiveMode] = useState(false);
    const [activeTab, setActiveTab] = useState(0);
    const [zoom, setZoom] = useState(1);
    const [brightness, setBrightness] = useState(50);
    const [contrast, setContrast] = useState(50);
    const [autoScale, setAutoScale] = useState(true);

    // Mock live image generation for demo
    const [liveImage, setLiveImage] = useState<string | null>(null);

    useEffect(() => {
        let interval: NodeJS.Timeout;

        if (isLiveMode && isConnected) {
            // Generate mock live images
            interval = setInterval(() => {
                generateMockLiveImage();
            }, 100); // Update every 100ms for live view
        }

        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isLiveMode, isConnected]);

    const generateMockLiveImage = () => {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 256;
        const ctx = canvas.getContext('2d')!;

        // Create a simple live view simulation
        const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
        gradient.addColorStop(0, '#444');
        gradient.addColorStop(1, '#000');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 256, 256);

        // Add some dynamic noise/features
        for (let i = 0; i < 20; i++) {
            const x = Math.random() * 256;
            const y = Math.random() * 256;
            const r = Math.random() * 8 + 2;
            const intensity = Math.random() * 0.3 + 0.2;

            const spotGradient = ctx.createRadialGradient(x, y, 0, x, y, r);
            spotGradient.addColorStop(0, `rgba(255, 255, 255, ${intensity})`);
            spotGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
            ctx.fillStyle = spotGradient;
            ctx.fillRect(x - r, y - r, r * 2, r * 2);
        }

        setLiveImage(canvas.toDataURL());
    };

    const handleToggleLive = () => {
        if (!isConnected) return;
        setIsLiveMode(!isLiveMode);
    };

    const getDisplayImage = () => {
        if (activeTab === 0) {
            // Main image view
            if (isLiveMode && liveImage) {
                return liveImage;
            } else if (lastImage) {
                return lastImage;
            }
        } else if (activeTab === 1 && lastFFT) {
            // FFT view
            return lastFFT;
        }
        return null;
    };

    const getImageStyle = () => {
        const brightnessValue = (brightness - 50) * 2; // -100 to 100
        const contrastValue = contrast * 2; // 0 to 100

        return {
            width: '100%',
            height: '100%',
            objectFit: 'contain' as const,
            transform: `scale(${zoom})`,
            filter: `brightness(${100 + brightnessValue}%) contrast(${contrastValue}%)`,
            transition: 'all 0.2s ease'
        };
    };

    const displayImage = getDisplayImage();

    return (
        <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardHeader
                title={
                    <Box display="flex" alignItems="center" gap={1}>
                        <Monitor size={20} />
                        Live View
                        {isLiveMode && (
                            <Chip
                                size="small"
                                label="LIVE"
                                color="success"
                                variant="filled"
                                icon={<Activity size={14} />}
                                sx={{ fontWeight: 600 }}
                            />
                        )}
                        {isAcquiring && (
                            <Chip
                                size="small"
                                label="ACQUIRING"
                                color="warning"
                                variant="filled"
                                icon={<CircularProgress size={12} />}
                                sx={{ fontWeight: 600 }}
                            />
                        )}
                    </Box>
                }
                action={
                    <Box display="flex" gap={1}>
                        <IconButton
                            onClick={handleToggleLive}
                            disabled={!isConnected}
                            color={isLiveMode ? "success" : "default"}
                            sx={{
                                backgroundColor: isLiveMode ? alpha(theme.palette.success.main, 0.1) : 'transparent',
                                '&:hover': {
                                    backgroundColor: isLiveMode
                                        ? alpha(theme.palette.success.main, 0.2)
                                        : alpha(theme.palette.action.hover, 0.1)
                                }
                            }}
                        >
                            {isLiveMode ? <StopIcon /> : <PlayIcon />}
                        </IconButton>
                        <IconButton>
                            <FullscreenIcon />
                        </IconButton>
                        <IconButton>
                            <SettingsIcon />
                        </IconButton>
                    </Box>
                }
                sx={{ pb: 1 }}
            />

            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', pt: 0 }}>
                {/* Tabs */}
                <Tabs
                    value={activeTab}
                    onChange={(e, newValue) => setActiveTab(newValue)}
                    sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
                    variant="fullWidth"
                >
                    <Tab
                        label="Image"
                        icon={<PhotoCameraIcon />}
                        disabled={!displayImage && activeTab !== 0}
                    />
                    <Tab
                        label="FFT"
                        icon={<Eye size={20} />}
                        disabled={!lastFFT}
                    />
                </Tabs>

                {/* Image Display Area */}
                <Box sx={{
                    flex: 1,
                    position: 'relative',
                    backgroundColor: '#000',
                    borderRadius: 1,
                    overflow: 'hidden',
                    border: `1px solid ${theme.palette.divider}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    {!isConnected ? (
                        <Alert severity="warning" sx={{ margin: 2 }}>
                            <Typography variant="body2">
                                Microscope not connected. Connect to view live images.
                            </Typography>
                        </Alert>
                    ) : displayImage ? (
                        <img
                            src={displayImage}
                            alt={activeTab === 0 ? "Live View" : "FFT"}
                            style={getImageStyle()}
                            onError={(e) => {
                                console.error('Image failed to load:', e);
                            }}
                        />
                    ) : (
                        <Box sx={{
                            textAlign: 'center',
                            color: 'text.secondary',
                            p: 4
                        }}>
                            <Camera size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                            <Typography variant="h6" gutterBottom>
                                {activeTab === 0 ? 'No Image Available' : 'No FFT Available'}
                            </Typography>
                            <Typography variant="body2">
                                {activeTab === 0
                                    ? isLiveMode
                                        ? 'Starting live view...'
                                        : 'Acquire an image or start live mode to view images'
                                    : 'Acquire an image to generate FFT'
                                }
                            </Typography>
                        </Box>
                    )}

                    {/* Image Info Overlay */}
                    {displayImage && (
                        <Box sx={{
                            position: 'absolute',
                            top: 8,
                            left: 8,
                            backgroundColor: alpha(theme.palette.background.paper, 0.9),
                            borderRadius: 1,
                            p: 1,
                            backdropFilter: 'blur(4px)'
                        }}>
                            <Typography variant="caption" display="block">
                                {activeTab === 0 ? (
                                    <>
                                        Mag: {opticalSettings.magnification.toLocaleString()}x
                                        <br />
                                        Defocus: {opticalSettings.defocus.toFixed(1)}μm
                                        {isLiveMode ? (
                                            <>
                                                <br />
                                                <Box component="span" sx={{ color: 'success.main', fontWeight: 600 }}>
                                                    ● LIVE
                                                </Box>
                                            </>
                                        ) : lastImage && (
                                            <>
                                                <br />
                                                Exposure: {acquisitionSettings.exposure}ms
                                            </>
                                        )}
                                    </>
                                ) : (
                                    'Fast Fourier Transform'
                                )}
                            </Typography>
                        </Box>
                    )}

                    {/* Zoom Controls */}
                    {displayImage && (
                        <Box sx={{
                            position: 'absolute',
                            bottom: 8,
                            right: 8,
                            display: 'flex',
                            gap: 1
                        }}>
                            <IconButton
                                size="small"
                                onClick={() => setZoom(Math.max(0.1, zoom - 0.1))}
                                sx={{
                                    backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                    '&:hover': { backgroundColor: alpha(theme.palette.background.paper, 1) }
                                }}
                            >
                                <ZoomOutIcon fontSize="small" />
                            </IconButton>
                            <Box sx={{
                                backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                borderRadius: 1,
                                px: 1,
                                display: 'flex',
                                alignItems: 'center',
                                minWidth: 60,
                                justifyContent: 'center'
                            }}>
                                <Typography variant="caption">
                                    {Math.round(zoom * 100)}%
                                </Typography>
                            </Box>
                            <IconButton
                                size="small"
                                onClick={() => setZoom(Math.min(3, zoom + 0.1))}
                                sx={{
                                    backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                    '&:hover': { backgroundColor: alpha(theme.palette.background.paper, 1) }
                                }}
                            >
                                <ZoomInIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    )}
                </Box>

                {/* Image Controls */}
                {displayImage && (
                    <Paper elevation={1} sx={{ mt: 2, p: 2 }}>
                        <Grid container spacing={2} alignItems="center">
                            <Grid item xs={12} sm={4}>
                                <Typography variant="body2" gutterBottom>
                                    Brightness: {brightness}%
                                </Typography>
                                <Slider
                                    size="small"
                                    value={brightness}
                                    onChange={(e, value) => setBrightness(value as number)}
                                    min={0}
                                    max={100}
                                    step={1}
                                />
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Typography variant="body2" gutterBottom>
                                    Contrast: {contrast}%
                                </Typography>
                                <Slider
                                    size="small"
                                    value={contrast}
                                    onChange={(e, value) => setContrast(value as number)}
                                    min={0}
                                    max={100}
                                    step={1}
                                />
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Box display="flex" gap={1} alignItems="center">
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                size="small"
                                                checked={autoScale}
                                                onChange={(e) => setAutoScale(e.target.checked)}
                                            />
                                        }
                                        label={<Typography variant="body2">Auto Scale</Typography>}
                                    />
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        onClick={() => {
                                            setZoom(1);
                                            setBrightness(50);
                                            setContrast(50);
                                        }}
                                        startIcon={<RefreshIcon />}
                                    >
                                        Reset
                                    </Button>
                                </Box>
                            </Grid>
                        </Grid>
                    </Paper>
                )}
            </CardContent>
        </Card>
    );
};

export default LiveView;