import React from 'react';
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
    useTheme
} from '@mui/material';
import {
    Settings as SettingsIcon,
    Camera as CameraIcon
} from '@mui/icons-material';
import {
    Move,
    Focus,
    ChevronLeft,
    ChevronRight
} from 'lucide-react';
import { useMicroscopeStore } from './microscopeStore';

// Mock API for image acquisition
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

export const ControlPanel: React.FC = () => {
    const theme = useTheme();
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
        addToHistory,
        advancedSettings,
        updateAdvancedSettings,
        presets,
        applyPreset,
        setShowSettings
    } = useMicroscopeStore();

    const handleAcquireImage = async () => {
        if (!isConnected || isAcquiring) return;

        try {
            setIsAcquiring(true);
            const result = await microscopeAPI.acquireImage(acquisitionSettings) as any;

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
                    pixelSize: 1.2,
                    dose: acquisitionSettings.exposure * 0.01,
                    defocus: opticalSettings.defocus,
                    astigmatism: 0.05
                }
            });
        } catch (error) {
            console.error('Failed to acquire image:', error);
        } finally {
            setIsAcquiring(false);
        }
    };

    return (
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
                                    {(['x', 'y', 'z'] as const).map(axis => (
                                        <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography sx={{ minWidth: 20, fontWeight: 'bold' }}>
                                                {axis.toUpperCase()}:
                                            </Typography>
                                            <IconButton
                                                size="small"
                                                disabled={!isConnected}
                                                onClick={() => {
                                                    const delta = axis === 'z' ? -0.001 : -0.1;
                                                    updateStagePosition({ [axis]: stagePosition[axis] + delta });
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
                                                sx={{ width: 120 }}
                                            />
                                            <IconButton
                                                size="small"
                                                disabled={!isConnected}
                                                onClick={() => {
                                                    const delta = axis === 'z' ? 0.001 : 0.1;
                                                    updateStagePosition({ [axis]: stagePosition[axis] + delta });
                                                }}
                                            >
                                                <ChevronRight size={16} />
                                            </IconButton>
                                        </Box>
                                    ))}

                                    <Divider sx={{ my: 1 }} />
                                    {(['alpha', 'beta'] as const).map(axis => (
                                        <Box key={axis} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography sx={{ minWidth: 20, fontWeight: 'bold' }}>
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
                                            onChange={(e) => updateOpticalSettings({ magnification: e.target.value as number })}
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

                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={opticalSettings.beamBlank}
                                                onChange={(e) => updateOpticalSettings({ beamBlank: e.target.checked })}
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
                                                onChange={(e) => updateAcquisitionSettings({ binning: parseInt(e.target.value as string) })}
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
                                                    onChange={(e) => updateAcquisitionSettings({ electronCounting: e.target.checked })}
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
                                                    onChange={(e) => updateAcquisitionSettings({ saveFrames: e.target.checked })}
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
                                    onClick={() => applyPreset(preset)}
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
                                                onChange={(e) => updateAdvancedSettings({ autoFocus: e.target.checked })}
                                            />
                                        }
                                        label="Auto Focus"
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={advancedSettings.driftCorrection}
                                                onChange={(e) => updateAdvancedSettings({ driftCorrection: e.target.checked })}
                                            />
                                        }
                                        label="Drift Correction"
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={advancedSettings.autoStigmation}
                                                onChange={(e) => updateAdvancedSettings({ autoStigmation: e.target.checked })}
                                            />
                                        }
                                        label="Auto Stigmation"
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={advancedSettings.doseProtection}
                                                onChange={(e) => updateAdvancedSettings({ doseProtection: e.target.checked })}
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
                                        onChange={(e) => updateAdvancedSettings({ targetDefocus: parseFloat(e.target.value) || 0 })}
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
    );
};