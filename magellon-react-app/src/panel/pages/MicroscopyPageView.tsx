import React, { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    IconButton,
    Badge,
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
    AlertTitle,
    Button
} from '@mui/material';
import Grid from '@mui/material/Grid'; // Using Grid v2
import {
    History as HistoryIcon,
    Close as CloseIcon,
    Settings as SettingsIcon,
    Tune as TuneIcon
} from '@mui/icons-material';
import { Zap, Monitor, Microscope as MicroscopeIcon } from 'lucide-react';
import { Layout, Model, TabNode, Actions, DockLocation } from 'flexlayout-react';
import 'flexlayout-react/style/light.css';

// Import components
import { SystemStatusComponent } from './SystemStatusComponent'; // Our updated component
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

// FlexLayout JSON configuration
const flexLayoutJson = {
    global: {
        tabEnableClose: false,
        tabEnableRename: false,
        tabEnableDrag: true,
        tabEnableFloat: true,
        borderBarSize: 30,
        borderEnableAutoHide: false,
    },
    layout: {
        type: "row",
        weight: 100,
        children: [
            {
                type: "tabset",
                weight: 33,
                children: [
                    {
                        type: "tab",
                        name: "Grid Atlas",
                        component: "GridAtlas",
                        config: {}
                    }
                ]
            },
            {
                type: "tabset",
                weight: 33,
                children: [
                    {
                        type: "tab",
                        name: "Live View",
                        component: "LiveView",
                        config: {}
                    }
                ]
            },
            {
                type: "tabset",
                weight: 34,
                children: [
                    {
                        type: "tab",
                        name: "Control Panel",
                        component: "ControlPanel",
                        config: {}
                    }
                ]
            }
        ]
    }
};

const microscopeAPI = new MicroscopeAPI();
const DRAWER_WIDTH = 240;

export default function MicroscopyPageView() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Camera-related state
    const [showCameraSettings, setShowCameraSettings] = useState(false);
    const [cameraClient] = useState(() => new MockDE_SDKClient());
    const [cameraError, setCameraError] = useState<string | null>(null);

    // FlexLayout model
    const [model, setModel] = useState(() => Model.fromJson(flexLayoutJson));

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

    // Additional drawer states for new panels
    const [showMicroscopePanel, setShowMicroscopePanel] = useState(false);
    const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

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

    // FlexLayout factory function for rendering components
    const factory = (node: TabNode) => {
        const component = node.getComponent();

        switch (component) {
            case "GridAtlas":
                return <GridAtlas />;
            case "LiveView":
                return <LiveView />;
            case "ControlPanel":
                return <ControlPanel />;
            default:
                return <div>Component {component} not found</div>;
        }
    };

    const handleFlexLayoutAction = (action: any) => {
        return action;
    };

    return (
        <>
            {/* Add global styles to ensure parent elements have proper height */}
            <style>
                {`
                    html, body, #root {
                        height: 100% !important;
                        margin: 0;
                        padding: 0;
                    }
                `}
            </style>

            <Box sx={{
                position: 'fixed',
                top: 64, // Your app bar height
                left: leftMargin,
                right: 0,
                bottom: 0,
                height: 'calc(100vh - 64px)', // Explicit height calculation
                backgroundColor: 'background.default',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                transition: theme.transitions.create(['left'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
            }}>
                {/* Fixed Header Section */}
                <Box sx={{
                    flexShrink: 0,
                    p: { xs: 1, sm: 2, md: 3 },
                    pb: { xs: 1, sm: 1, md: 2 },
                    borderBottom: `1px solid ${theme.palette.divider}`,
                    backgroundColor: 'background.paper',
                }}>
                    {/* Header */}
                    <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
                            <IconButton onClick={() => setShowHistory(true)} title="Acquisition History">
                                <Badge badgeContent={acquisitionHistory.length} color="primary">
                                    <HistoryIcon />
                                </Badge>
                            </IconButton>

                            <IconButton onClick={() => setShowMicroscopePanel(true)} title="Microscope Details">
                                <MicroscopeIcon size={24} />
                            </IconButton>

                            <IconButton onClick={() => setShowAdvancedSettings(true)} title="Advanced Settings">
                                <TuneIcon />
                            </IconButton>
                        </Box>
                    </Box>

                    {/* Error Handling */}
                    {cameraError && (
                        <Box sx={{ mb: 2 }}>
                            <Alert
                                severity="error"
                                onClose={() => setCameraError(null)}
                            >
                                <AlertTitle>Camera Error</AlertTitle>
                                <Typography variant="body2">{cameraError}</Typography>
                            </Alert>
                        </Box>
                    )}

                    {/* System Status */}
                    <SystemStatusComponent
                        isConnected={isConnected}
                        connectionStatus={connectionStatus}
                        onConnect={handleConnect}
                        cameraConnected={cameraConnected}
                        cameraLoading={cameraLoading}
                        onCameraSettings={() => setShowCameraSettings(true)}
                    />
                </Box>

                {/* FlexLayout Container - Uses remaining space */}
                <Box sx={{
                    flex: 1,
                    minHeight: 0,
                    position: 'relative',
                    '& .flexlayout__layout': {
                        width: '100%',
                        height: '100%',
                        backgroundColor: 'transparent',
                    },
                    '& .flexlayout__tabset_header': {
                        backgroundColor: theme.palette.background.paper,
                        borderBottom: `1px solid ${theme.palette.divider}`,
                    },
                    '& .flexlayout__tab_button': {
                        backgroundColor: theme.palette.background.default,
                        color: theme.palette.text.primary,
                        '&:hover': {
                            backgroundColor: theme.palette.action.hover,
                        }
                    },
                    '& .flexlayout__tab_button--selected': {
                        backgroundColor: theme.palette.primary.main,
                        color: theme.palette.primary.contrastText,
                    },
                    '& .flexlayout__tabset_content': {
                        backgroundColor: theme.palette.background.paper,
                    }
                }}>
                    <Layout
                        model={model}
                        factory={factory}
                        onAction={handleFlexLayoutAction}
                    />
                </Box>

                {/* Camera Settings Dialog */}
                <CameraSettingsDialog
                    open={showCameraSettings}
                    onClose={() => setShowCameraSettings(false)}
                    cameraSettings={cameraSettings}
                    updateCameraSettings={() => {}}
                    acquisitionSettings={cameraSettings}
                    updateAcquisitionSettings={() => {}}
                    availableProperties={availableProperties}
                    systemStatus={cameraSystemStatus}
                    onPropertyChange={handleCameraPropertyChange}
                />

                {/* Drawers and other components remain the same */}
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
                                                    Defocus: {item.metadata.defocus?.toFixed(1)}μm •
                                                    Dose: {item.metadata.dose?.toFixed(1)} e⁻/Å²
                                                </Typography>
                                            </Box>
                                        </Box>
                                    </ListItem>
                                ))
                            )}
                        </List>
                    </Box>
                </Drawer>

                {/* Other drawers... */}
                <Drawer
                    anchor="right"
                    open={showMicroscopePanel}
                    onClose={() => setShowMicroscopePanel(false)}
                    PaperProps={{
                        sx: { width: { xs: '100%', sm: 500 } }
                    }}
                >
                    <Box sx={{ p: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Microscope Details</Typography>
                            <IconButton onClick={() => setShowMicroscopePanel(false)}>
                                <CloseIcon />
                            </IconButton>
                        </Box>

                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            Detailed microscope status, alignments, and operational parameters.
                        </Typography>

                        <Box sx={{ mt: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>System Information</Typography>
                            <Typography variant="body2">Model: Titan Krios G4</Typography>
                            <Typography variant="body2">High Tension: 300 kV</Typography>
                            <Typography variant="body2">Column Valve: Open</Typography>
                            <Typography variant="body2">Vacuum Status: Ready</Typography>
                        </Box>
                    </Box>
                </Drawer>

                <Drawer
                    anchor="right"
                    open={showAdvancedSettings}
                    onClose={() => setShowAdvancedSettings(false)}
                    PaperProps={{
                        sx: { width: { xs: '100%', sm: 600 } }
                    }}
                >
                    <Box sx={{ p: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Advanced Settings</Typography>
                            <IconButton onClick={() => setShowAdvancedSettings(false)}>
                                <CloseIcon />
                            </IconButton>
                        </Box>

                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            Advanced microscope and camera configuration options.
                        </Typography>

                        <Box sx={{ mt: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>Camera Integration</Typography>
                            <Grid container spacing={2}>
                                <Grid size={6}>
                                    <Button
                                        variant="outlined"
                                        fullWidth
                                        onClick={refreshCameraProperties}
                                        disabled={cameraLoading}
                                    >
                                        Refresh Camera Properties
                                    </Button>
                                </Grid>
                                <Grid size={6}>
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
                    </Box>
                </Drawer>

                {/* Snackbars */}
                <Snackbar
                    open={connectionStatus === 'connecting'}
                    message="Connecting to microscope..."
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                />

                <Snackbar
                    open={!!cameraError}
                    message={`Camera Error: ${cameraError}`}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                    autoHideDuration={6000}
                    onClose={() => setCameraError(null)}
                />
            </Box>
        </>
    );
}