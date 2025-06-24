import React, { useEffect } from 'react';
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
    useMediaQuery
} from '@mui/material';
import {
    History as HistoryIcon,
    Close as CloseIcon
} from '@mui/icons-material';
import { Zap, Monitor } from 'lucide-react';

// Import our new components
import { StatusCards } from './Microscopy/StatusCard';
import { QuickActions } from './Microscopy/QuickActions';
import { GridAtlas } from './Microscopy/GridAtlas';
import { LiveView } from './Microscopy/LiveView';
import { ControlPanel } from './Microscopy/ControlPanel';
import { useMicroscopeStore } from './Microscopy/MicroscopeStore';

// Mock API (same as before, but simplified)
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
}

const microscopeAPI = new MicroscopeAPI();
const DRAWER_WIDTH = 240;

export default function MicroscopyPageView() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Get state and actions from store
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

    // Track drawer state (you can move this to store if needed)
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
                <StatusCards />

                {/* Quick Actions */}
                <QuickActions />

                {/* Main Content */}
                <Grid container spacing={3}>
                    {/* Left Column - Atlas and Image */}
                    <Grid item xs={12} lg={4}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, height: '100%' }}>
                            <GridAtlas />
                            <LiveView />
                        </Box>
                    </Grid>

                    {/* Right Column - Controls */}
                    <Grid item xs={12} lg={8}>
                        <ControlPanel />
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