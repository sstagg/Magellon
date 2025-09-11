import React, { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Button,
    IconButton,
    Grid,
    Badge,
    CircularProgress,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Drawer,
    List,
    ListItem,
    ListItemText,
    Snackbar,
    Chip,
    useTheme,
    useMediaQuery,
    Alert,
    AlertTitle
} from '@mui/material';
import {
    History as HistoryIcon,
    Close as CloseIcon,
    Camera as CameraIcon
} from '@mui/icons-material';
import { Zap, Monitor } from 'lucide-react';

// Import components
import { StatusCards } from './Microscopy/StatusCard';
import { GridAtlas } from './Microscopy/GridAtlas';
import { LiveView } from './Microscopy/LiveView';
import { ControlPanel } from './Microscopy/ControlPanel';
import { useMicroscopeStore } from './Microscopy/MicroscopeStore';
import { CameraSettingsDialog } from './Microscopy/CameraSettingsDialog';
import { useDeCamera, DE_PROPERTIES } from './Microscopy/useDeCamera.ts';

// Enhanced Mock API with camera integration
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
            refrigerantLevel: 85,
            // Add camera status
            cameraConnected: true,
            cameraModel: 'DE-64',
            cameraTemperature: -15.2
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
}

// Mock DE-SDK Client
class MockDE_SDKClient {
    private properties: { [key: string]: any } = {
        [DE_PROPERTIES.HARDWARE_BINNING_X]: 1,
        [DE_PROPERTIES.HARDWARE_BINNING_Y]: 1,
        [DE_PROPERTIES.HARDWARE_ROI_OFFSET_X]: 0,
        [DE_PROPERTIES.HARDWARE_ROI_OFFSET_Y]: 0,
        [DE_PROPERTIES.HARDWARE_ROI_SIZE_X]: 4096,
        [DE_PROPERTIES.HARDWARE_ROI_SIZE_Y]: 4096,
        [DE_PROPERTIES.READOUT_SHUTTER]: 'Rolling',
        [DE_PROPERTIES.READOUT_HARDWARE_HDR]: 'Off',
        [DE_PROPERTIES.FRAMES_PER_SECOND]: 40,
        [DE_PROPERTIES.FRAME_TIME_NANOSECONDS]: 25000000,
        [DE_PROPERTIES.EXPOSURE_TIME_SECONDS]: 1.0,
        [DE_PROPERTIES.FRAME_COUNT]: 40,
        [DE_PROPERTIES.IMAGE_PROCESSING_MODE]: 'Integrating',
        [DE_PROPERTIES.IMAGE_PROCESSING_FLATFIELD]: 'Dark and Gain',
        [DE_PROPERTIES.IMAGE_PROCESSING_GAIN_MOVIE]: 'Off',
        [DE_PROPERTIES.IMAGE_PROCESSING_GAIN_FINAL]: 'On',
        [DE_PROPERTIES.BINNING_X]: 1,
        [DE_PROPERTIES.BINNING_Y]: 1,
        [DE_PROPERTIES.BINNING_METHOD]: 'Average',
        [DE_PROPERTIES.CROP_OFFSET_X]: 0,
        [DE_PROPERTIES.CROP_OFFSET_Y]: 0,
        [DE_PROPERTIES.CROP_SIZE_X]: 4096,
        [DE_PROPERTIES.CROP_SIZE_Y]: 4096,
        [DE_PROPERTIES.AUTOSAVE_DIRECTORY]: '/data/acquisitions',
        [DE_PROPERTIES.AUTOSAVE_FILENAME_SUFFIX]: '',
        [DE_PROPERTIES.AUTOSAVE_FILE_FORMAT]: 'Auto',
        [DE_PROPERTIES.AUTOSAVE_MOVIE_FORMAT]: 'Auto',
        [DE_PROPERTIES.AUTOSAVE_FINAL_IMAGE]: 'On',
        [DE_PROPERTIES.AUTOSAVE_MOVIE]: 'Off',
        [DE_PROPERTIES.AUTOSAVE_MOVIE_SUM_COUNT]: 1,
        [DE_PROPERTIES.PRESET_LIST]: 'Default,High Speed,High Quality,Counting Mode,Cryo-EM Standard',
        [DE_PROPERTIES.PRESET_CURRENT]: 'Default',
        [DE_PROPERTIES.SYSTEM_STATUS]: 'Ready',
        [DE_PROPERTIES.CAMERA_POSITION_STATUS]: 'Inserted',
        [DE_PROPERTIES.TEMPERATURE_DETECTOR_STATUS]: '-15.2',
    };

    async ListProperties(): Promise<string[]> {
        await new Promise(resolve => setTimeout(resolve, 100));
        return Object.keys(this.properties);
    }

    async GetProperty(propertyName: string): Promise<any> {
        await new Promise(resolve => setTimeout(resolve, 50));

        if (!(propertyName in this.properties)) {
            throw new Error(`Property ${propertyName} not found`);
        }

        return this.properties[propertyName];
    }

    async SetProperty(propertyName: string, value: any): Promise<boolean> {
        await new Promise(resolve => setTimeout(resolve, 100));

        if (!(propertyName in this.properties)) {
            return false;
        }

        // Simulate hardware adjustments for linked properties
        if (propertyName === DE_PROPERTIES.FRAMES_PER_SECOND) {
            this.properties[DE_PROPERTIES.FRAME_TIME_NANOSECONDS] = Math.round(1000000000 / value);
        } else if (propertyName === DE_PROPERTIES.EXPOSURE_TIME_SECONDS) {
            const fps = this.properties[DE_PROPERTIES.FRAMES_PER_SECOND];
            this.properties[DE_PROPERTIES.FRAME_COUNT] = Math.round(value * fps);
        }

        this.properties[propertyName] = value;
        return true;
    }

    async GetErrorDescription(): Promise<string> {
        return 'No error';
    }
}

const microscopeAPI = new MicroscopeAPI();
const DRAWER_WIDTH = 240;

export default function MicroscopyPageView() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Camera-related state
    const [showCameraSettings, setShowCameraSettings] = useState(false);
    const [cameraClient] = useState(() => new MockDE_SDKClient());
    const [cameraError, setCameraError] = useState<string | null>(null);

    // Initialize DE Camera hook
    const {
        isConnected: cameraConnected,
        isLoading: cameraLoading,
        error: cameraHookError,
        availableProperties,
        settings: cameraSettings,
        systemStatus: cameraSystemStatus,
        setProperty: setCameraProperty,
        refreshProperties: refreshCameraProperties,
        loadPresets,
        setPreset: setCameraPreset,
        debug: debugCamera,
    } = useDeCamera(cameraClient);

    // Get state and actions from microscope store
    const {
        isConnected,
        connectionStatus,
        setConnectionStatus,
        setIsConnected,
        setMicroscopeStatus,
        setAtlasData,
        acquisitionHistory,
        showHistory,
        setShowHistory,
        showSettings,
        setShowSettings
    } = useMicroscopeStore();

    // Track drawer state
    const [isDrawerOpen, setIsDrawerOpen] = React.useState(() => {
        if (typeof window !== 'undefined') {
            const savedState = localStorage.getItem('drawerOpen');
            return savedState ? JSON.parse(savedState) : false;
        }
        return false;
    });

    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    // Initialize connection and API listeners
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

        // Handle drawer state changes
        const handleStorageChange = () => {
            if (typeof window !== 'undefined') {
                const savedState = localStorage.getItem('drawerOpen');
                setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
            }
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, [setIsConnected, setConnectionStatus]);

    // Handle camera errors
    useEffect(() => {
        if (cameraHookError) {
            setCameraError(cameraHookError);
        }
    }, [cameraHookError]);

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

    // Handle camera property changes
    const handleCameraPropertyChange = async (propertyName: string, value: any) => {
        try {
            await setCameraProperty(propertyName, value);
            console.log(`Successfully set ${propertyName} to ${value}`);
            setCameraError(null);
        } catch (err) {
            const errorMsg = `Failed to set ${propertyName}: ${err}`;
            console.error(errorMsg);
            setCameraError(errorMsg);
        }
    };

    // Quick camera presets
    const handleQuickPreset = async (presetName: string) => {
        try {
            await setCameraPreset(presetName);
            console.log(`Applied preset: ${presetName}`);
            setCameraError(null);
        } catch (err) {
            const errorMsg = `Failed to apply preset ${presetName}: ${err}`;
            console.error(errorMsg);
            setCameraError(errorMsg);
        }
    };

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

                        <Button
                            variant="outlined"
                            onClick={() => setShowCameraSettings(true)}
                            disabled={!cameraConnected || cameraLoading}
                            startIcon={cameraLoading ? <CircularProgress size={16} /> : <CameraIcon />}
                        >
                            Camera Settings
                        </Button>

                        <IconButton onClick={() => setShowHistory(true)}>
                            <Badge badgeContent={acquisitionHistory.length} color="primary">
                                <HistoryIcon />
                            </Badge>
                        </IconButton>
                    </Box>
                </Box>

                {/* Combined System Status Alert */}
                {(cameraError || (isConnected && cameraConnected)) && (
                    <Box sx={{ mb: 2 }}>
                        {cameraError && (
                            <Alert severity="error" sx={{ mb: 1 }} onClose={() => setCameraError(null)}>
                                <AlertTitle>Camera Error</AlertTitle>
                                {cameraError}
                            </Alert>
                        )}

                        {isConnected && cameraConnected && (
                            <Alert severity="success">
                                <AlertTitle>System Status</AlertTitle>
                                <Box component="span" sx={{ display: 'block', mb: 1 }}>
                                    <strong>Microscope:</strong> Titan Krios G4 Connected • Column: Open • Vacuum: Ready
                                </Box>
                                <Box component="span" sx={{ display: 'block' }}>
                                    <strong>DE Camera:</strong> {cameraSettings[DE_PROPERTIES.IMAGE_PROCESSING_MODE] || 'Unknown'} Mode •
                                    {' '}{cameraSettings[DE_PROPERTIES.FRAMES_PER_SECOND] || 'Unknown'} FPS •
                                    {' '}{cameraSystemStatus.temperature || 'Unknown'}°C
                                </Box>
                            </Alert>
                        )}
                    </Box>
                )}

                {/* Status Cards - Full Width */}
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid item xs={12}>
                        <StatusCards />
                    </Grid>
                </Grid>

                {/* Main Content - Three Column Layout */}
                <Grid container spacing={3} sx={{ height: 'calc(100vh - 350px)', minHeight: '600px' }}>
                    {/* Grid Atlas */}
                    <Grid item xs={12} lg={4}>
                        <Box sx={{ height: '100%' }}>
                            <GridAtlas />
                        </Box>
                    </Grid>

                    {/* Live View */}
                    <Grid item xs={12} lg={4}>
                        <Box sx={{ height: '100%' }}>
                            <LiveView />
                        </Box>
                    </Grid>

                    {/* Control Panel */}
                    <Grid item xs={12} lg={4}>
                        <Box sx={{ height: '100%' }}>
                            <ControlPanel />
                        </Box>
                    </Grid>
                </Grid>
            </Box>

            {/* Camera Settings Dialog */}
            <CameraSettingsDialog
                open={showCameraSettings}
                onClose={() => setShowCameraSettings(false)}
                cameraSettings={cameraSettings}
                updateCameraSettings={() => {}} // Legacy - not used with DE-SDK
                acquisitionSettings={cameraSettings}
                updateAcquisitionSettings={() => {}} // Legacy - not used with DE-SDK
                availableProperties={availableProperties}
                systemStatus={cameraSystemStatus}
                onPropertyChange={handleCameraPropertyChange}
            />

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
                                                Dose: {item.metadata.dose.toFixed(1)} e⁻/Ų
                                            </Typography>
                                        </Box>
                                    </Box>
                                </ListItem>
                            ))
                        )}
                    </List>
                </Box>
            </Drawer>

            {/* General Settings Dialog */}
            <Dialog
                open={showSettings}
                onClose={() => setShowSettings(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Advanced Settings</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        Advanced microscope and camera configuration options.
                    </Typography>

                    {/* Camera Integration Section */}
                    <Box sx={{ mt: 2 }}>
                        <Typography variant="h6" gutterBottom>Camera Integration</Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    onClick={refreshCameraProperties}
                                    disabled={cameraLoading}
                                >
                                    Refresh Camera Properties
                                </Button>
                            </Grid>
                            <Grid item xs={6}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    onClick={() => setShowCameraSettings(true)}
                                    disabled={!cameraConnected}
                                >
                                    Open Camera Settings
                                </Button>
                            </Grid>
                        </Grid>

                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            Camera Status: {cameraConnected ? 'Connected' : 'Disconnected'} •
                            Properties: {availableProperties.length} available
                        </Typography>
                    </Box>
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

            {/* Camera Error Snackbar */}
            <Snackbar
                open={!!cameraError}
                message={`Camera Error: ${cameraError}`}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                autoHideDuration={6000}
                onClose={() => setCameraError(null)}
            />
        </Box>
    );
}