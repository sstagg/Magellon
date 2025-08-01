import React, { useState } from 'react';
import {
    Card,
    CardHeader,
    CardContent,
    Typography,
    Box,
    Paper,
    Grid,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    FormControlLabel,
    Switch,
    Button,
    IconButton,
    Tabs,
    Tab,
    Divider,
    Slider,
    CircularProgress,
    alpha,
    useTheme,
    Alert,
    Stack,
    Tooltip, Chip
} from '@mui/material';
import {
    Settings as SettingsIcon,
    Camera as CameraIcon,
    Science as ScienceIcon,
    Save as SaveIcon,
    Add,
} from '@mui/icons-material';
import {
    Move,
    Focus,
    ChevronLeft,
    ChevronRight,
    Target,
    Activity,
    Zap,
    Microscope, CheckCircleIcon, Grid3X3, Square, Circle, Eye
} from 'lucide-react';

// Import the separated dialog components
import { CameraSettingsDialog } from './CameraSettingsDialog';
import { MicroscopeSettingsDialog } from './MicroscopeSettingsDialog';

// Import store hook (this should be from your actual store file)
import { useMicroscopeStore } from './MicroscopeStore';

const microscopeAPI = {
    async acquireImage(settings: any) {
        return new Promise((resolve) => {
            setTimeout(() => {
                // Generate fake image data
                const canvas = document.createElement('canvas');
                canvas.width = 512;
                canvas.height = 512;
                const ctx = canvas.getContext('2d')!;

                const gradient = ctx.createRadialGradient(256, 256, 0, 256, 256, 256);
                gradient.addColorStop(0, '#666');
                gradient.addColorStop(1, '#000');
                ctx.fillStyle = gradient;
                ctx.fillRect(0, 0, 512, 512);

                for (let i = 0; i < 80; i++) {
                    const x = Math.random() * 512;
                    const y = Math.random() * 512;
                    const r = Math.random() * 15 + 5;
                    const intensity = Math.random() * 0.6 + 0.4;

                    const spotGradient = ctx.createRadialGradient(x, y, 0, x, y, r);
                    spotGradient.addColorStop(0, `rgba(255, 255, 255, ${intensity})`);
                    spotGradient.addColorStop(0.5, `rgba(200, 200, 200, ${intensity * 0.5})`);
                    spotGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
                    ctx.fillStyle = spotGradient;
                    ctx.fillRect(x - r, y - r, r * 2, r * 2);
                }

                const imageData = canvas.toDataURL();

                // Generate fake FFT
                const fftCanvas = document.createElement('canvas');
                fftCanvas.width = 256;
                fftCanvas.height = 256;
                const fftCtx = fftCanvas.getContext('2d')!;
                fftCtx.fillStyle = '#000';
                fftCtx.fillRect(0, 0, 256, 256);

                const centerGradient = fftCtx.createRadialGradient(128, 128, 0, 128, 128, 20);
                centerGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
                centerGradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.5)');
                centerGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
                fftCtx.fillStyle = centerGradient;
                fftCtx.fillRect(0, 0, 256, 256);

                const fftData = fftCanvas.toDataURL();

                resolve({ success: true, image: imageData, fft: fftData });
            }, settings.exposure);
        });
    }
};

export const ControlPanel = () => {
    const theme = useTheme();

    // Get state and actions from store
    const {
        activeTab,
        setActiveTab,
        stagePosition,
        updateStagePosition,
        opticalSettings,
        updateOpticalSettings,
        acquisitionSettings,
        updateAcquisitionSettings,
        isConnected,
        isAcquiring,
        setIsAcquiring,
        setLastImage,
        setLastFFT,
        lastImage,
        lastFFT,
        advancedSettings,
        updateAdvancedSettings,
        presets,
        applyPreset,
        addToHistory
    } = useMicroscopeStore();

    // Local state for settings dialogs
    const [showCameraSettings, setShowCameraSettings] = useState(false);
    const [showMicroscopeSettings, setShowMicroscopeSettings] = useState(false);
    const [showPresetEditor, setShowPresetEditor] = useState(false);

    // Mock camera and microscope settings (these would normally come from store)
    const [cameraSettings, setCameraSettings] = useState({
        gainReference: 'auto',
        readoutMode: 'correlated',
        driftCorrection: true,
        doseProtection: true,
        pixelSize: 1.2,
        temperature: -35.2
    });

    const [microscopeSettings, setMicroscopeSettings] = useState({
        lensConfiguration: 'standard',
        c2Aperture: 50,
        objectiveAperture: 100,
        phaseplate: false,
        phasePlateAdvance: 30,
        holderType: 'cryo',
        stageSpeed: 75
    });

    const [allPresets, setAllPresets] = useState([
        // Grid presets
        {
            id: 1,
            name: 'Grid Overview',
            category: 'Grid',
            type: 'Grid',
            description: 'Low magnification grid screening',
            mag: 2000,
            defocus: -10.0,
            spot: 8,
            exposure: 500,
            binning: 4,
            settings: {
                optical: { magnification: 2000, defocus: -10.0, spotSize: 8, intensity: 1e-6 },
                acquisition: { exposure: 500, binning: 4, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 15000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark', binningMethod: 'Average' }
            }
        },
        {
            id: 2,
            name: 'Grid Atlas',
            category: 'Grid',
            type: 'Grid',
            description: 'Medium magnification grid mapping',
            mag: 5000,
            defocus: -8.0,
            spot: 7,
            exposure: 800,
            binning: 2,
            settings: {
                optical: { magnification: 5000, defocus: -8.0, spotSize: 7, intensity: 8e-7 },
                acquisition: { exposure: 800, binning: 2, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 20000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        // Square presets
        {
            id: 3,
            name: 'Square Screening',
            category: 'Square',
            type: 'Square',
            description: 'Square navigation and screening',
            mag: 10000,
            defocus: -5.0,
            spot: 6,
            exposure: 1000,
            binning: 2,
            settings: {
                optical: { magnification: 10000, defocus: -5.0, spotSize: 6, intensity: 6e-7 },
                acquisition: { exposure: 1000, binning: 2, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 25000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        {
            id: 4,
            name: 'Square Atlas',
            category: 'Square',
            type: 'Square',
            description: 'High-resolution square mapping',
            mag: 25000,
            defocus: -3.0,
            spot: 5,
            exposure: 1200,
            binning: 1,
            settings: {
                optical: { magnification: 25000, defocus: -3.0, spotSize: 5, intensity: 4e-7 },
                acquisition: { exposure: 1200, binning: 1, mode: 'Integrating', electronCounting: false, saveFrames: true },
                camera: { frameTime: 30000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        // Hole presets
        {
            id: 5,
            name: 'Hole Targeting',
            category: 'Hole',
            type: 'Hole',
            description: 'Target selection in holes',
            mag: 50000,
            defocus: -2.5,
            spot: 5,
            exposure: 1500,
            binning: 1,
            settings: {
                optical: { magnification: 50000, defocus: -2.5, spotSize: 5, intensity: 3e-7 },
                acquisition: { exposure: 1500, binning: 1, mode: 'Integrating', electronCounting: false, saveFrames: true },
                camera: { frameTime: 35000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        // Focus presets
        {
            id: 6,
            name: 'Focus Check',
            category: 'Focus',
            type: 'Focus',
            description: 'Quick focus verification',
            mag: 81000,
            defocus: -1.5,
            spot: 4,
            exposure: 800,
            binning: 1,
            settings: {
                optical: { magnification: 81000, defocus: -1.5, spotSize: 4, intensity: 2e-7 },
                acquisition: { exposure: 800, binning: 1, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 25000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        {
            id: 7,
            name: 'Focus Fine',
            category: 'Focus',
            type: 'Focus',
            description: 'High-precision focus adjustment',
            mag: 105000,
            defocus: -1.0,
            spot: 3,
            exposure: 500,
            binning: 1,
            settings: {
                optical: { magnification: 105000, defocus: -1.0, spotSize: 3, intensity: 1e-7 },
                acquisition: { exposure: 500, binning: 1, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 20000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        // Exposure presets
        {
            id: 8,
            name: 'Test Exposure',
            category: 'Exposure',
            type: 'Exposure',
            description: 'Quick exposure test',
            mag: 81000,
            defocus: -2.0,
            spot: 5,
            exposure: 200,
            binning: 2,
            settings: {
                optical: { magnification: 81000, defocus: -2.0, spotSize: 5, intensity: 5e-7 },
                acquisition: { exposure: 200, binning: 2, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 15000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark', binningMethod: 'Average' }
            }
        },
        {
            id: 9,
            name: 'Data Collection',
            category: 'Exposure',
            type: 'Exposure',
            description: 'High-quality data acquisition',
            mag: 81000,
            defocus: -2.0,
            spot: 5,
            exposure: 2000,
            binning: 1,
            settings: {
                optical: { magnification: 81000, defocus: -2.0, spotSize: 5, intensity: 2e-7 },
                acquisition: { exposure: 2000, binning: 1, mode: 'Counting', electronCounting: true, saveFrames: true },
                camera: { frameTime: 40000000, processingMode: 'Counting', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        }
    ]);
    const updateCameraSettings = (updates: any) => {
        setCameraSettings(prev => ({ ...prev, ...updates }));
    };

    const updateMicroscopeSettings = (updates: any) => {
        setMicroscopeSettings(prev => ({ ...prev, ...updates }));
    };

    const handleAcquireImage = async () => {
        if (!isConnected || isAcquiring) return;

        try {
            setIsAcquiring(true);
            console.log('Starting image acquisition with settings:', acquisitionSettings);

            const result = await microscopeAPI.acquireImage(acquisitionSettings);
            console.log('Acquisition completed:', result);

            setLastImage(result.image);
            setLastFFT(result.fft);

            // Add to history
            addToHistory({
                id: Date.now(),
                timestamp: new Date().toISOString(),
                settings: acquisitionSettings,
                thumbnail: result.image,
                fft: result.fft,
                metadata: {
                    pixelSize: cameraSettings.pixelSize,
                    dose: acquisitionSettings.exposure * 0.01,
                    defocus: opticalSettings.defocus,
                    astigmatism: 0.05,
                    magnification: opticalSettings.magnification,
                    binning: acquisitionSettings.binning,
                    mode: acquisitionSettings.mode
                }
            });

            console.log('Image acquired successfully and added to history');
        } catch (error) {
            console.error('Failed to acquire image:', error);
        } finally {
            setIsAcquiring(false);
        }
    };
    const handleApplyPreset = (preset: any) => {
        // Apply optical settings
        updateOpticalSettings({
            magnification: preset.settings.optical.magnification,
            defocus: preset.settings.optical.defocus,
            spotSize: preset.settings.optical.spotSize,
            intensity: preset.settings.optical.intensity
        });

        // Apply acquisition settings
        updateAcquisitionSettings({
            exposure: preset.settings.acquisition.exposure,
            binning: preset.settings.acquisition.binning,
            mode: preset.settings.acquisition.mode,
            electronCounting: preset.settings.acquisition.electronCounting,
            saveFrames: preset.settings.acquisition.saveFrames
        });

        // Apply camera settings
        updateCameraSettings({
            frameTime: preset.settings.camera.frameTime,
            processingMode: preset.settings.camera.processingMode,
            flatfieldCorrection: preset.settings.camera.flatfieldCorrection,
            binningMethod: preset.settings.camera.binningMethod
        });

        console.log(`Applied preset: ${preset.name}`);
    };

    const handleSavePreset = (newPreset: any) => {
        setAllPresets(prev => [...prev, newPreset]);
    };

    const getPresetIcon = (type: string) => {
        switch (type) {
            case 'Grid': return <Grid3X3 size={18} />;
            case 'Square': return <Square size={18} />;
            case 'Hole': return <Circle size={18} />;
            case 'Focus': return <Focus size={18} />;
            case 'Exposure': return <Eye size={18} />;
            default: return <SaveIcon />;
        }
    };

    const getPresetColor = (type: string) => {
        switch (type) {
            case 'Grid': return 'primary';
            case 'Square': return 'secondary';
            case 'Hole': return 'success';
            case 'Focus': return 'warning';
            case 'Exposure': return 'info';
            default: return 'default';
        }
    };
    return (
        <>
            <Card sx={{ height: '100%' }}>
                <CardHeader
                    title="Advanced Control Panel"
                    subheader="Integrated Camera & Microscope Control"
                    action={
                        <Box display="flex" gap={1}>
                            <Tooltip title="Camera Settings">
                                <IconButton onClick={() => setShowCameraSettings(true)}>
                                    <CameraIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Microscope Settings">
                                <IconButton onClick={() => setShowMicroscopeSettings(true)}>
                                    <Microscope />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="General Settings">
                                <IconButton>
                                    <SettingsIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    }
                />
                <CardContent>
                    <Tabs
                        value={activeTab}
                        onChange={(e, newValue) => setActiveTab(newValue)}
                        sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}
                        variant="fullWidth"
                    >
                        <Tab label="Stage & Optics" icon={<Focus size={20} />} />
                        <Tab label="Acquisition" icon={<CameraIcon />} />
                        <Tab label="Presets" icon={<SaveIcon />} />
                        <Tab label="Automation" icon={<Target size={20} />} />
                    </Tabs>

                    {/* Stage & Optics Tab */}
                    {activeTab === 0 && (
                        <Grid container spacing={3}>
                            {/* Stage Control */}
                            <Grid item xs={12} md={6}>
                                <Paper
                                    elevation={2}
                                    sx={{
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.02)} 0%, ${alpha(theme.palette.primary.main, 0.05)} 100%)`
                                    }}
                                >
                                    <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, fontWeight: 600 }}>
                                        <Move size={20} />
                                        Stage Position
                                    </Typography>

                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                        {(['x', 'y', 'z']).map(axis => (
                                            <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Typography sx={{ minWidth: 20, fontWeight: 'bold', color: 'primary.main' }}>
                                                    {axis.toUpperCase()}:
                                                </Typography>
                                                <IconButton
                                                    size="small"
                                                    disabled={!isConnected}
                                                    onClick={() => {
                                                        const delta = axis === 'z' ? -0.001 : -0.1;
                                                        updateStagePosition({ [axis]: stagePosition[axis] + delta });
                                                    }}
                                                    sx={{
                                                        border: 1,
                                                        borderColor: 'divider',
                                                        '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.1) }
                                                    }}
                                                >
                                                    <ChevronLeft size={16} />
                                                </IconButton>
                                                <TextField
                                                    size="small"
                                                    value={stagePosition[axis].toFixed(axis === 'z' ? 3 : 1)}
                                                    disabled={!isConnected}
                                                    onChange={(e) => {
                                                        const value = parseFloat(e.target.value) || 0;
                                                        updateStagePosition({ [axis]: value });
                                                    }}
                                                    InputProps={{
                                                        endAdornment: (
                                                            <Typography variant="caption" color="text.secondary">
                                                                μm
                                                            </Typography>
                                                        )
                                                    }}
                                                    sx={{
                                                        width: 130,
                                                        '& .MuiOutlinedInput-root': {
                                                            backgroundColor: alpha(theme.palette.background.paper, 0.8)
                                                        }
                                                    }}
                                                />
                                                <IconButton
                                                    size="small"
                                                    disabled={!isConnected}
                                                    onClick={() => {
                                                        const delta = axis === 'z' ? 0.001 : 0.1;
                                                        updateStagePosition({ [axis]: stagePosition[axis] + delta });
                                                    }}
                                                    sx={{
                                                        border: 1,
                                                        borderColor: 'divider',
                                                        '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.1) }
                                                    }}
                                                >
                                                    <ChevronRight size={16} />
                                                </IconButton>
                                            </Box>
                                        ))}

                                        <Divider sx={{ my: 1 }} />
                                        {(['alpha', 'beta']).map(axis => (
                                            <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Typography sx={{ minWidth: 20, fontWeight: 'bold', color: 'primary.main' }}>
                                                    {axis === 'alpha' ? 'α' : 'β'}:
                                                </Typography>
                                                <TextField
                                                    size="small"
                                                    value={(stagePosition[axis] * 180 / Math.PI).toFixed(1)}
                                                    disabled={!isConnected}
                                                    onChange={(e) => {
                                                        const value = (parseFloat(e.target.value) || 0) * Math.PI / 180;
                                                        updateStagePosition({ [axis]: value });
                                                    }}
                                                    InputProps={{
                                                        endAdornment: (
                                                            <Typography variant="caption" color="text.secondary">
                                                                °
                                                            </Typography>
                                                        )
                                                    }}
                                                    sx={{
                                                        width: 130,
                                                        ml: 3,
                                                        '& .MuiOutlinedInput-root': {
                                                            backgroundColor: alpha(theme.palette.background.paper, 0.8)
                                                        }
                                                    }}
                                                />
                                            </Box>
                                        ))}
                                    </Box>

                                </Paper>
                            </Grid>

                            {/* Optical Settings */}
                            <Grid item xs={12} md={6}>
                                <Paper
                                    elevation={2}
                                    sx={{
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.secondary.main, 0.02)} 0%, ${alpha(theme.palette.secondary.main, 0.05)} 100%)`
                                    }}
                                >
                                    <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, fontWeight: 600 }}>
                                        <Focus size={20} />
                                        Optical Settings
                                        <Tooltip title="Advanced Microscope Settings">
                                            <IconButton
                                                size="small"
                                                onClick={() => setShowMicroscopeSettings(true)}
                                                sx={{ ml: 'auto' }}
                                            >
                                                <SettingsIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Typography>

                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                                        <FormControl size="small" fullWidth>
                                            <InputLabel>Magnification</InputLabel>
                                            <Select
                                                value={opticalSettings.magnification}
                                                onChange={(e) => updateOpticalSettings({ magnification: e.target.value })}
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
                                            onChange={(e) => updateOpticalSettings({ defocus: parseFloat(e.target.value) || 0 })}
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
                                                onChange={(e) => updateOpticalSettings({ spotSize: parseInt(e.target.value) || 1 })}
                                                disabled={!isConnected}
                                                sx={{ flex: 1 }}
                                            />
                                            <TextField
                                                size="small"
                                                label="Intensity"
                                                type="number"
                                                value={opticalSettings.intensity}
                                                onChange={(e) => updateOpticalSettings({ intensity: parseFloat(e.target.value) || 0 })}
                                                disabled={!isConnected}
                                                sx={{ flex: 1 }}
                                            />
                                        </Box>

                                        <Box sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            p: 1.5,
                                            borderRadius: 1,
                                            backgroundColor: opticalSettings.beamBlank ? alpha(theme.palette.error.main, 0.1) : alpha(theme.palette.success.main, 0.1)
                                        }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Zap size={18} color={opticalSettings.beamBlank ? theme.palette.error.main : theme.palette.success.main} />
                                                <Typography variant="body2" fontWeight="medium">
                                                    {opticalSettings.beamBlank ? 'Beam Blanked' : 'Beam On'}
                                                </Typography>
                                            </Box>
                                            <Switch
                                                checked={!opticalSettings.beamBlank}
                                                onChange={(e) => updateOpticalSettings({ beamBlank: !e.target.checked })}
                                                disabled={!isConnected}
                                                color={opticalSettings.beamBlank ? "error" : "success"}
                                            />
                                        </Box>
                                    </Box>
                                </Paper>
                            </Grid>
                        </Grid>
                    )}

                    {/* Acquisition Tab */}
                    {activeTab === 1 && (
                        <Grid container spacing={3}>
                            <Grid item xs={12}>
                                <Paper
                                    elevation={2}
                                    sx={{
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.info.main, 0.02)} 0%, ${alpha(theme.palette.info.main, 0.05)} 100%)`
                                    }}
                                >
                                    <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, fontWeight: 600 }}>
                                        <CameraIcon />
                                        Acquisition Settings
                                        <Tooltip title="Advanced Camera Settings">
                                            <IconButton
                                                size="small"
                                                onClick={() => setShowCameraSettings(true)}
                                                sx={{ ml: 'auto' }}
                                            >
                                                <SettingsIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Typography>

                                    <Grid container spacing={2} sx={{ mb: 3 }}>
                                        <Grid item xs={12} sm={6} md={3}>
                                            <TextField
                                                size="small"
                                                label="Exposure"
                                                type="number"
                                                value={acquisitionSettings.exposure}
                                                onChange={(e) => updateAcquisitionSettings({ exposure: parseInt(e.target.value) || 1000 })}
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
                                                    onChange={(e) => updateAcquisitionSettings({ binning: parseInt(e.target.value) })}
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
                                            <FormControl size="small" fullWidth>
                                                <InputLabel>Mode</InputLabel>
                                                <Select
                                                    value={acquisitionSettings.mode}
                                                    onChange={(e) => updateAcquisitionSettings({ mode: e.target.value })}
                                                    disabled={!isConnected}
                                                    label="Mode"
                                                >
                                                    <MenuItem value="Integrating">Integrating</MenuItem>
                                                    <MenuItem value="Counting">Counting</MenuItem>
                                                    <MenuItem value="Super Resolution">Super Resolution</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={12} sm={6} md={3}>
                                            <Box sx={{ display: 'flex', gap: 1, height: '100%' }}>
                                                <FormControlLabel
                                                    control={
                                                        <Switch
                                                            checked={acquisitionSettings.electronCounting}
                                                            onChange={(e) => updateAcquisitionSettings({ electronCounting: e.target.checked })}
                                                            disabled={!isConnected}
                                                            size="small"
                                                        />
                                                    }
                                                    label={<Typography variant="body2">Counting</Typography>}
                                                />
                                                <FormControlLabel
                                                    control={
                                                        <Switch
                                                            checked={acquisitionSettings.saveFrames}
                                                            onChange={(e) => updateAcquisitionSettings({ saveFrames: e.target.checked })}
                                                            disabled={!isConnected}
                                                            size="small"
                                                        />
                                                    }
                                                    label={<Typography variant="body2">Frames</Typography>}
                                                />
                                            </Box>
                                        </Grid>
                                    </Grid>

                                    <Button
                                        variant="contained"
                                        size="large"
                                        fullWidth
                                        onClick={handleAcquireImage}
                                        disabled={!isConnected || isAcquiring}
                                        startIcon={isAcquiring ? <CircularProgress size={20} /> : <CameraIcon />}
                                        sx={{
                                            py: 1.5,
                                            fontSize: '1.1rem',
                                            fontWeight: 600,
                                            background: isAcquiring
                                                ? 'linear-gradient(45deg, #ff9800 30%, #f57c00 90%)'
                                                : 'linear-gradient(45deg, #2196f3 30%, #21cbf3 90%)',
                                            boxShadow: 3,
                                            '&:hover': {
                                                boxShadow: 6,
                                                transform: 'translateY(-1px)'
                                            },
                                            transition: 'all 0.2s ease'
                                        }}
                                    >
                                        {isAcquiring ? 'Acquiring...' : 'Acquire Image'}
                                    </Button>

                                    {/* Image Preview */}
                                    {lastImage && (
                                        <Box sx={{ mt: 3 }}>
                                            <Typography variant="subtitle2" gutterBottom>
                                                Last Acquired Image
                                            </Typography>
                                            <Paper
                                                elevation={1}
                                                sx={{
                                                    p: 1,
                                                    borderRadius: 1,
                                                    display: 'flex',
                                                    gap: 2,
                                                    alignItems: 'center'
                                                }}
                                            >
                                                <Box sx={{
                                                    width: 80,
                                                    height: 80,
                                                    borderRadius: 1,
                                                    overflow: 'hidden',
                                                    border: '1px solid',
                                                    borderColor: 'divider'
                                                }}>
                                                    <img
                                                        src={lastImage}
                                                        alt="Last acquired"
                                                        style={{
                                                            width: '100%',
                                                            height: '100%',
                                                            objectFit: 'cover'
                                                        }}
                                                    />
                                                </Box>
                                                <Box sx={{ flex: 1 }}>
                                                    <Typography variant="body2" fontWeight="medium">
                                                        Acquisition Details
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary" component="div">
                                                        • Mode: {acquisitionSettings.mode}
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary" component="div">
                                                        • Exposure: {acquisitionSettings.exposure}ms
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary" component="div">
                                                        • Binning: {acquisitionSettings.binning}x{acquisitionSettings.binning}
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary" component="div">
                                                        • Magnification: {opticalSettings.magnification.toLocaleString()}x
                                                    </Typography>
                                                </Box>
                                                {lastFFT && (
                                                    <Box sx={{
                                                        width: 60,
                                                        height: 60,
                                                        borderRadius: 1,
                                                        overflow: 'hidden',
                                                        border: '1px solid',
                                                        borderColor: 'divider'
                                                    }}>
                                                        <img
                                                            src={lastFFT}
                                                            alt="FFT"
                                                            style={{
                                                                width: '100%',
                                                                height: '100%',
                                                                objectFit: 'cover'
                                                            }}
                                                        />
                                                    </Box>
                                                )}
                                            </Paper>
                                        </Box>
                                    )}
                                </Paper>
                            </Grid>
                        </Grid>
                    )}

                    {/* Presets Tab */}
                    {activeTab === 2 && (
                        <Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                                <Typography variant="h6" fontWeight="600">
                                    Preset Library
                                </Typography>
                                <Button
                                    variant="contained"
                                    startIcon={<Add />}
                                    onClick={() => setShowPresetEditor(true)}
                                    sx={{ borderRadius: 2 }}
                                >
                                    Create Preset
                                </Button>
                            </Box>

                            {/* Preset Categories */}
                            {['Grid', 'Square', 'Hole', 'Focus', 'Exposure'].map(category => {
                                const categoryPresets = allPresets.filter(preset => preset.type === category);
                                if (categoryPresets.length === 0) return null;

                                return (
                                    <Box key={category} sx={{ mb: 4 }}>
                                        <Typography
                                            variant="subtitle1"
                                            fontWeight="600"
                                            sx={{
                                                mb: 2,
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: 1,
                                                color: `${getPresetColor(category)}.main`
                                            }}
                                        >
                                            {getPresetIcon(category)}
                                            {category} Presets
                                        </Typography>

                                        <Grid container spacing={2}>
                                            {categoryPresets.map(preset => (
                                                <Grid item xs={12} sm={6} md={4} key={preset.id}>
                                                    <Paper
                                                        elevation={2}
                                                        sx={{
                                                            p: 2.5,
                                                            borderRadius: 2,
                                                            transition: 'all 0.3s ease',
                                                            background: `linear-gradient(135deg, ${alpha(theme.palette[getPresetColor(category)].main, 0.05)} 0%, ${alpha(theme.palette[getPresetColor(category)].main, 0.1)} 100%)`,
                                                            border: `1px solid ${alpha(theme.palette[getPresetColor(category)].main, 0.2)}`,
                                                            '&:hover': {
                                                                transform: 'translateY(-2px)',
                                                                boxShadow: 6,
                                                                backgroundColor: alpha(theme.palette[getPresetColor(category)].main, 0.15)
                                                            }
                                                        }}
                                                    >
                                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                                                            <Typography variant="h6" sx={{ fontWeight: 600, color: `${getPresetColor(category)}.main` }}>
                                                                {preset.name}
                                                            </Typography>
                                                            <Chip
                                                                label={preset.type}
                                                                size="small"
                                                                color={getPresetColor(category)}
                                                                variant="outlined"
                                                                icon={getPresetIcon(category)}
                                                            />
                                                        </Box>

                                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
                                                            {preset.description}
                                                        </Typography>

                                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 2 }}>
                                                            <Typography variant="body2" color="text.secondary">
                                                                📏 Magnification: {preset.mag.toLocaleString()}x
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                🎯 Defocus: {preset.defocus} μm
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                ⚡ Spot Size: {preset.spot}
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                📸 Exposure: {preset.exposure}ms
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                🔢 Binning: {preset.binning}x{preset.binning}
                                                            </Typography>
                                                        </Box>

                                                        <Button
                                                            variant="contained"
                                                            color={getPresetColor(category)}
                                                            fullWidth
                                                            onClick={() => handleApplyPreset(preset)}
                                                            disabled={!isConnected}
                                                            startIcon={<CheckCircleIcon />}
                                                            sx={{
                                                                fontWeight: 600,
                                                                py: 1,
                                                                borderRadius: 1.5,
                                                                '&:hover': {
                                                                    transform: 'translateY(-1px)'
                                                                }
                                                            }}
                                                        >
                                                            Apply
                                                        </Button>
                                                    </Paper>
                                                </Grid>
                                            ))}
                                        </Grid>
                                    </Box>
                                );
                            })}
                        </Box>
                    )}

                    {/* Automation Tab */}
                    {activeTab === 3 && (
                        <Grid container spacing={3}>
                            <Grid item xs={12} md={6}>
                                <Paper
                                    elevation={2}
                                    sx={{
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.02)} 0%, ${alpha(theme.palette.success.main, 0.05)} 100%)`
                                    }}
                                >
                                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                                        Auto Functions
                                    </Typography>

                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={advancedSettings.autoFocus}
                                                    onChange={(e) => updateAdvancedSettings({ autoFocus: e.target.checked })}
                                                    color="success"
                                                />
                                            }
                                            label={
                                                <Box>
                                                    <Typography variant="body1" fontWeight="medium">Auto Focus</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        Automatically maintain eucentric focus
                                                    </Typography>
                                                </Box>
                                            }
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={advancedSettings.driftCorrection}
                                                    onChange={(e) => updateAdvancedSettings({ driftCorrection: e.target.checked })}
                                                    color="success"
                                                />
                                            }
                                            label={
                                                <Box>
                                                    <Typography variant="body1" fontWeight="medium">Drift Correction</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        Compensate for specimen drift
                                                    </Typography>
                                                </Box>
                                            }
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={advancedSettings.autoStigmation}
                                                    onChange={(e) => updateAdvancedSettings({ autoStigmation: e.target.checked })}
                                                    color="success"
                                                />
                                            }
                                            label={
                                                <Box>
                                                    <Typography variant="body1" fontWeight="medium">Auto Stigmation</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        Automatic stigmator correction
                                                    </Typography>
                                                </Box>
                                            }
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={advancedSettings.doseProtection}
                                                    onChange={(e) => updateAdvancedSettings({ doseProtection: e.target.checked })}
                                                    color="success"
                                                />
                                            }
                                            label={
                                                <Box>
                                                    <Typography variant="body1" fontWeight="medium">Dose Protection</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        Minimize beam exposure between acquisitions
                                                    </Typography>
                                                </Box>
                                            }
                                        />
                                    </Box>
                                </Paper>
                            </Grid>

                            <Grid item xs={12} md={6}>
                                <Paper
                                    elevation={2}
                                    sx={{
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.02)} 0%, ${alpha(theme.palette.warning.main, 0.05)} 100%)`
                                    }}
                                >
                                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                                        Defocus Settings
                                    </Typography>

                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                        <TextField
                                            size="small"
                                            label="Target Defocus"
                                            type="number"
                                            value={advancedSettings.targetDefocus}
                                            onChange={(e) => updateAdvancedSettings({ targetDefocus: parseFloat(e.target.value) || 0 })}
                                            InputProps={{
                                                endAdornment: (
                                                    <Typography variant="caption" color="text.secondary">
                                                        μm
                                                    </Typography>
                                                )
                                            }}
                                        />

                                        <Box>
                                            <Typography gutterBottom fontWeight="medium">
                                                Defocus Range: ±{advancedSettings.defocusRange} μm
                                            </Typography>
                                            <Slider
                                                value={advancedSettings.defocusRange}
                                                onChange={(e, value) => updateAdvancedSettings({ defocusRange: value })}
                                                min={0.1}
                                                max={2.0}
                                                step={0.1}
                                                marks={[
                                                    { value: 0.5, label: '0.5' },
                                                    { value: 1.0, label: '1.0' },
                                                    { value: 1.5, label: '1.5' },
                                                    { value: 2.0, label: '2.0' }
                                                ]}
                                                valueLabelDisplay="auto"
                                                valueLabelFormat={(value) => `±${value} μm`}
                                            />
                                        </Box>

                                        <Alert severity="info" sx={{ mt: 2 }}>
                                            <Typography variant="body2">
                                                Automatic defocus will vary between {advancedSettings.targetDefocus - advancedSettings.defocusRange}
                                                and {advancedSettings.targetDefocus + advancedSettings.defocusRange} μm
                                            </Typography>
                                        </Alert>
                                    </Box>
                                </Paper>
                            </Grid>
                        </Grid>
                    )}
                </CardContent>
            </Card>

            {/* Camera Settings Dialog */}
            <CameraSettingsDialog
                open={showCameraSettings}
                onClose={() => setShowCameraSettings(false)}
                cameraSettings={cameraSettings}
                updateCameraSettings={updateCameraSettings}
                acquisitionSettings={acquisitionSettings}
                updateAcquisitionSettings={updateAcquisitionSettings}
            />

            {/* Microscope Settings Dialog */}
            <MicroscopeSettingsDialog
                open={showMicroscopeSettings}
                onClose={() => setShowMicroscopeSettings(false)}
                microscopeSettings={microscopeSettings}
                updateMicroscopeSettings={updateMicroscopeSettings}
                opticalSettings={opticalSettings}
                updateOpticalSettings={updateOpticalSettings}
                advancedSettings={advancedSettings}
                updateAdvancedSettings={updateAdvancedSettings}
            />
        </>
    );
};

export default ControlPanel;