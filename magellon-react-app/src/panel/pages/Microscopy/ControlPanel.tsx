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
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Chip,
    Alert,
    AlertTitle,
    ButtonGroup,
    ToggleButton,
    ToggleButtonGroup,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Stack,
    Tooltip
} from '@mui/material';
import {
    Settings as SettingsIcon,
    Camera as CameraIcon,
    ExpandMore as ExpandMoreIcon,
    Science as ScienceIcon,
    PhotoCamera as PhotoCameraIcon,
    Tune as TuneIcon,
    Save as SaveIcon,
    Refresh as RefreshIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    Warning as WarningIcon,
    Brightness4 as Brightness4Icon,
    Layers as LayersIcon,
    Speed as SpeedIcon,
    Visibility as VisibilityIcon,
    ZoomIn as ZoomInIcon,
    Memory as MemoryIcon
} from '@mui/icons-material';
import {
    Move,
    Focus,
    ChevronLeft,
    ChevronRight,
    Target,
    Activity,
    ScanLine,
    Zap,
    Thermometer,
    Gauge, Microscope
} from 'lucide-react';

// Mock microscope store (simplified for demo)
const useMicroscopeStore = () => {
    const [activeTab, setActiveTab] = useState(0);
    const [stagePosition, setStagePosition] = useState({ x: 12.345, y: -23.456, z: 0.234, alpha: 0.0, beta: 0.0 });
    const [opticalSettings, setOpticalSettings] = useState({
        magnification: 81000,
        defocus: -2.0,
        spotSize: 3,
        intensity: 0.00045,
        beamBlank: false
    });
    const [acquisitionSettings, setAcquisitionSettings] = useState({
        exposure: 1000,
        binning: 1,
        electronCounting: true,
        saveFrames: false,
        frameTime: 50,
        mode: 'Counting',
        frameRate: 40
    });
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
    const [advancedSettings, setAdvancedSettings] = useState({
        autoFocus: true,
        driftCorrection: true,
        autoStigmation: false,
        doseProtection: true,
        beamTiltCompensation: true,
        targetDefocus: -2.0,
        defocusRange: 0.5
    });
    const [isConnected] = useState(true);
    const [isAcquiring, setIsAcquiring] = useState(false);
    const [lastImage, setLastImage] = useState(null);
    const [lastFFT, setLastFFT] = useState(null);
    const [showCameraSettings, setShowCameraSettings] = useState(false);
    const [showMicroscopeSettings, setShowMicroscopeSettings] = useState(false);

    const presets = [
        { id: 1, name: 'Atlas', mag: 200, defocus: -100, spot: 5 },
        { id: 2, name: 'Square', mag: 2000, defocus: -50, spot: 4 },
        { id: 3, name: 'Hole', mag: 10000, defocus: -10, spot: 3 },
        { id: 4, name: 'Focus', mag: 50000, defocus: -2, spot: 3 },
        { id: 5, name: 'Record', mag: 81000, defocus: -2, spot: 3 },
    ];

    return {
        activeTab, setActiveTab,
        stagePosition, updateStagePosition: (updates) => setStagePosition(prev => ({ ...prev, ...updates })),
        opticalSettings, updateOpticalSettings: (updates) => setOpticalSettings(prev => ({ ...prev, ...updates })),
        acquisitionSettings, updateAcquisitionSettings: (updates) => setAcquisitionSettings(prev => ({ ...prev, ...updates })),
        cameraSettings, updateCameraSettings: (updates) => setCameraSettings(prev => ({ ...prev, ...updates })),
        microscopeSettings, updateMicroscopeSettings: (updates) => setMicroscopeSettings(prev => ({ ...prev, ...updates })),
        advancedSettings, updateAdvancedSettings: (updates) => setAdvancedSettings(prev => ({ ...prev, ...updates })),
        isConnected, isAcquiring, setIsAcquiring,
        lastImage, setLastImage, lastFFT, setLastFFT,
        showCameraSettings, setShowCameraSettings,
        showMicroscopeSettings, setShowMicroscopeSettings,
        presets,
        applyPreset: (preset) => {
            setOpticalSettings(prev => ({
                ...prev,
                magnification: preset.mag,
                defocus: preset.defocus,
                spotSize: preset.spot
            }));
        }
    };
};

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

// Camera Settings Dialog Component
const CameraSettingsDialog = ({ open, onClose, cameraSettings, updateCameraSettings, acquisitionSettings, updateAcquisitionSettings }) => {
    const [advancedOpen, setAdvancedOpen] = useState(false);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={2}>
                    <PhotoCameraIcon color="primary" />
                    <Typography variant="h5" fontWeight="600">
                        Camera Settings
                    </Typography>
                    <Chip
                        icon={<CheckCircleIcon />}
                        label="Connected"
                        color="success"
                        size="small"
                        variant="outlined"
                    />
                </Box>
            </DialogTitle>
            <DialogContent>
                <Stack spacing={3} sx={{ mt: 1 }}>
                    {/* Status Alert */}
                    <Alert severity="info" icon={<InfoIcon />}>
                        <AlertTitle>DE-64 Counting Camera</AlertTitle>
                        Temperature: {cameraSettings.temperature}°C • Status: Ready • Last Calibration: 2024-06-20
                    </Alert>

                    {/* Basic Settings */}
                    <Paper elevation={1} sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <MemoryIcon />
                            Basic Settings
                        </Typography>

                        <Grid container spacing={3}>
                            <Grid item xs={6}>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Camera Mode</InputLabel>
                                    <Select
                                        value={acquisitionSettings.mode}
                                        label="Camera Mode"
                                        onChange={(e) => updateAcquisitionSettings({ mode: e.target.value })}
                                    >
                                        <MenuItem value="Integrating">Integrating</MenuItem>
                                        <MenuItem value="Counting">Counting</MenuItem>
                                        <MenuItem value="Super Resolution">Super Resolution</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>

                            <Grid item xs={6}>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Frame Rate</InputLabel>
                                    <Select
                                        value={acquisitionSettings.frameRate}
                                        label="Frame Rate"
                                        onChange={(e) => updateAcquisitionSettings({ frameRate: e.target.value })}
                                    >
                                        <MenuItem value={40}>40 fps</MenuItem>
                                        <MenuItem value={75}>75 fps</MenuItem>
                                        <MenuItem value={100}>100 fps</MenuItem>
                                        <MenuItem value={200}>200 fps</MenuItem>
                                        <MenuItem value={400}>400 fps</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>

                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label="Exposure (ms)"
                                    type="number"
                                    value={acquisitionSettings.exposure}
                                    onChange={(e) => updateAcquisitionSettings({ exposure: parseInt(e.target.value) })}
                                    inputProps={{ min: 10, max: 10000 }}
                                />
                            </Grid>

                            <Grid item xs={6}>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Binning</InputLabel>
                                    <Select
                                        value={acquisitionSettings.binning}
                                        label="Binning"
                                        onChange={(e) => updateAcquisitionSettings({ binning: e.target.value })}
                                    >
                                        <MenuItem value={1}>1x1</MenuItem>
                                        <MenuItem value={2}>2x2</MenuItem>
                                        <MenuItem value={4}>4x4</MenuItem>
                                        <MenuItem value={8}>8x8</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                        </Grid>

                        {/* Hardware Binning Buttons */}
                        <Box mt={3}>
                            <Typography variant="subtitle2" gutterBottom>Hardware Binning Quick Select</Typography>
                            <ToggleButtonGroup
                                value={acquisitionSettings.binning}
                                exclusive
                                onChange={(e, value) => value && updateAcquisitionSettings({ binning: value })}
                                size="small"
                            >
                                <ToggleButton value={1}>1x1</ToggleButton>
                                <ToggleButton value={2}>2x2</ToggleButton>
                                <ToggleButton value={4}>4x4</ToggleButton>
                                <ToggleButton value={8}>8x8</ToggleButton>
                            </ToggleButtonGroup>
                        </Box>

                        {/* Switches */}
                        <Stack spacing={2} sx={{ mt: 3 }}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={acquisitionSettings.electronCounting}
                                        onChange={(e) => updateAcquisitionSettings({ electronCounting: e.target.checked })}
                                        color="primary"
                                    />
                                }
                                label="Electron Counting Mode"
                            />

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={acquisitionSettings.saveFrames}
                                        onChange={(e) => updateAcquisitionSettings({ saveFrames: e.target.checked })}
                                        color="primary"
                                    />
                                }
                                label="Save Individual Frames"
                            />

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={cameraSettings.driftCorrection}
                                        onChange={(e) => updateCameraSettings({ driftCorrection: e.target.checked })}
                                        color="primary"
                                    />
                                }
                                label="Real-time Drift Correction"
                            />

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={cameraSettings.doseProtection}
                                        onChange={(e) => updateCameraSettings({ doseProtection: e.target.checked })}
                                        color="primary"
                                    />
                                }
                                label="Dose Protection"
                            />
                        </Stack>

                        {/* Frame Time (conditional) */}
                        {acquisitionSettings.saveFrames && (
                            <Box mt={3}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label="Frame Time (ms)"
                                    type="number"
                                    value={acquisitionSettings.frameTime}
                                    onChange={(e) => updateAcquisitionSettings({ frameTime: parseInt(e.target.value) })}
                                    helperText={`${Math.floor(acquisitionSettings.exposure / acquisitionSettings.frameTime)} frames will be saved`}
                                />
                            </Box>
                        )}
                    </Paper>

                    {/* Advanced Settings Accordion */}
                    <Accordion expanded={advancedOpen} onChange={(e, isExpanded) => setAdvancedOpen(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <TuneIcon />
                                Advanced Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={2}>
                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Readout Mode</InputLabel>
                                            <Select
                                                value={cameraSettings.readoutMode}
                                                label="Readout Mode"
                                                onChange={(e) => updateCameraSettings({ readoutMode: e.target.value })}
                                            >
                                                <MenuItem value="correlated">Correlated Double Sampling</MenuItem>
                                                <MenuItem value="standard">Standard</MenuItem>
                                                <MenuItem value="fast">Fast Readout</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Gain Reference</InputLabel>
                                            <Select
                                                value={cameraSettings.gainReference}
                                                label="Gain Reference"
                                                onChange={(e) => updateCameraSettings({ gainReference: e.target.value })}
                                            >
                                                <MenuItem value="auto">Auto</MenuItem>
                                                <MenuItem value="manual">Manual</MenuItem>
                                                <MenuItem value="factory">Factory Default</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                </Grid>

                                <Box>
                                    <Typography variant="subtitle2" gutterBottom>
                                        Pixel Size Calibration
                                    </Typography>
                                    <Grid container spacing={2}>
                                        <Grid item xs={8}>
                                            <TextField
                                                fullWidth
                                                size="small"
                                                value={cameraSettings.pixelSize}
                                                onChange={(e) => updateCameraSettings({ pixelSize: parseFloat(e.target.value) })}
                                                type="number"
                                                step="0.1"
                                            />
                                        </Grid>
                                        <Grid item xs={4}>
                                            <TextField
                                                fullWidth
                                                size="small"
                                                value="Å/pixel"
                                                disabled
                                            />
                                        </Grid>
                                    </Grid>
                                </Box>

                                <Stack direction="row" spacing={2}>
                                    <Button variant="outlined" startIcon={<RefreshIcon />} fullWidth>
                                        Acquire Dark Reference
                                    </Button>
                                    <Button variant="outlined" startIcon={<RefreshIcon />} fullWidth>
                                        Update Gain Reference
                                    </Button>
                                </Stack>

                                <Button variant="outlined" startIcon={<SettingsIcon />} fullWidth>
                                    Update Defect Map
                                </Button>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" startIcon={<SaveIcon />}>
                    Apply Settings
                </Button>
            </DialogActions>
        </Dialog>
    );
};

// Microscope Settings Dialog Component
const MicroscopeSettingsDialog = ({ open, onClose, microscopeSettings, updateMicroscopeSettings, opticalSettings, updateOpticalSettings, advancedSettings, updateAdvancedSettings }) => {
    const [advancedOpen, setAdvancedOpen] = useState(false);

    const magnificationOptions = [2000, 5000, 10000, 25000, 50000, 81000, 105000, 130000];

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={2}>
                    <Microscope color="primary" />
                    <Typography variant="h5" fontWeight="600">
                        Microscope Settings
                    </Typography>
                    <Chip
                        icon={<CheckCircleIcon />}
                        label="Ready"
                        color="success"
                        size="small"
                        variant="outlined"
                    />
                </Box>
            </DialogTitle>
            <DialogContent>
                <Stack spacing={3} sx={{ mt: 1 }}>
                    {/* Status Alert */}
                    <Alert severity="success" icon={<CheckCircleIcon />}>
                        <AlertTitle>Titan Krios G4</AlertTitle>
                        HT: 300kV • Vacuum: 5.2e-8 Pa • Column: Open • Temperature: -192.3°C
                    </Alert>

                    {/* Optical Settings */}
                    <Paper elevation={1} sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <ZoomInIcon />
                            Optical Settings
                        </Typography>

                        <Grid container spacing={3}>
                            <Grid item xs={12}>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Magnification</InputLabel>
                                    <Select
                                        value={opticalSettings.magnification}
                                        label="Magnification"
                                        onChange={(e) => updateOpticalSettings({ magnification: e.target.value })}
                                    >
                                        {magnificationOptions.map(mag => (
                                            <MenuItem key={mag} value={mag}>
                                                {mag.toLocaleString()}x
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            </Grid>

                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label="Defocus (μm)"
                                    type="number"
                                    step="0.1"
                                    value={opticalSettings.defocus}
                                    onChange={(e) => updateOpticalSettings({ defocus: parseFloat(e.target.value) })}
                                />
                            </Grid>

                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label="Spot Size"
                                    type="number"
                                    inputProps={{ min: 1, max: 11 }}
                                    value={opticalSettings.spotSize}
                                    onChange={(e) => updateOpticalSettings({ spotSize: parseInt(e.target.value) })}
                                />
                            </Grid>

                            <Grid item xs={12}>
                                <Typography variant="subtitle2" gutterBottom>
                                    Intensity: {opticalSettings.intensity.toExponential(2)}
                                </Typography>
                                <Slider
                                    value={Math.log10(opticalSettings.intensity)}
                                    onChange={(e, value) => updateOpticalSettings({ intensity: Math.pow(10, value) })}
                                    min={-6}
                                    max={-3}
                                    step={0.1}
                                    marks={[
                                        { value: -6, label: '10⁻⁶' },
                                        { value: -4.5, label: '10⁻⁴·⁵' },
                                        { value: -3, label: '10⁻³' }
                                    ]}
                                />
                            </Grid>
                        </Grid>

                        {/* Beam Control */}
                        <Box mt={3}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={!opticalSettings.beamBlank}
                                        onChange={(e) => updateOpticalSettings({ beamBlank: !e.target.checked })}
                                        color={opticalSettings.beamBlank ? "error" : "success"}
                                    />
                                }
                                label={
                                    <Box display="flex" alignItems="center" gap={1}>
                                        <Brightness4Icon />
                                        {opticalSettings.beamBlank ? 'Beam Blanked' : 'Beam On'}
                                    </Box>
                                }
                            />
                        </Box>
                    </Paper>

                    {/* Advanced Settings Accordion */}
                    <Accordion expanded={advancedOpen} onChange={(e, isExpanded) => setAdvancedOpen(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <TuneIcon />
                                Advanced Configuration
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                {/* Lens Configuration */}
                                <FormControl fullWidth size="small">
                                    <InputLabel>Lens Configuration</InputLabel>
                                    <Select
                                        value={microscopeSettings.lensConfiguration}
                                        label="Lens Configuration"
                                        onChange={(e) => updateMicroscopeSettings({ lensConfiguration: e.target.value })}
                                    >
                                        <MenuItem value="standard">Standard</MenuItem>
                                        <MenuItem value="lowmag">Low Magnification</MenuItem>
                                        <MenuItem value="diffraction">Diffraction</MenuItem>
                                        <MenuItem value="stem">STEM</MenuItem>
                                    </Select>
                                </FormControl>

                                {/* Apertures */}
                                <Box>
                                    <Typography variant="subtitle2" gutterBottom>Apertures</Typography>
                                    <Grid container spacing={2}>
                                        <Grid item xs={6}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>C2 Aperture</InputLabel>
                                                <Select
                                                    value={microscopeSettings.c2Aperture}
                                                    label="C2 Aperture"
                                                    onChange={(e) => updateMicroscopeSettings({ c2Aperture: e.target.value })}
                                                >
                                                    <MenuItem value={30}>30 μm</MenuItem>
                                                    <MenuItem value={50}>50 μm</MenuItem>
                                                    <MenuItem value={70}>70 μm</MenuItem>
                                                    <MenuItem value={100}>100 μm</MenuItem>
                                                    <MenuItem value={150}>150 μm</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>Objective Aperture</InputLabel>
                                                <Select
                                                    value={microscopeSettings.objectiveAperture}
                                                    label="Objective Aperture"
                                                    onChange={(e) => updateMicroscopeSettings({ objectiveAperture: e.target.value })}
                                                >
                                                    <MenuItem value={10}>10 μm</MenuItem>
                                                    <MenuItem value={30}>30 μm</MenuItem>
                                                    <MenuItem value={70}>70 μm</MenuItem>
                                                    <MenuItem value={100}>100 μm</MenuItem>
                                                    <MenuItem value="open">Open</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                    </Grid>
                                </Box>

                                {/* Phase Plate */}
                                <Box>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={microscopeSettings.phaseplate}
                                                onChange={(e) => updateMicroscopeSettings({ phaseplate: e.target.checked })}
                                            />
                                        }
                                        label="Volta Phase Plate"
                                    />
                                    {microscopeSettings.phaseplate && (
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Advance Interval (min)"
                                            type="number"
                                            value={microscopeSettings.phasePlateAdvance}
                                            onChange={(e) => updateMicroscopeSettings({ phasePlateAdvance: parseInt(e.target.value) })}
                                            sx={{ mt: 2 }}
                                        />
                                    )}
                                </Box>

                                {/* Auto Functions */}
                                <Box>
                                    <Typography variant="subtitle2" gutterBottom>Auto Functions</Typography>
                                    <Stack spacing={1}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={advancedSettings.autoFocus}
                                                    onChange={(e) => updateAdvancedSettings({ autoFocus: e.target.checked })}
                                                />
                                            }
                                            label="Auto Eucentric Focus"
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
                                                    checked={advancedSettings.beamTiltCompensation}
                                                    onChange={(e) => updateAdvancedSettings({ beamTiltCompensation: e.target.checked })}
                                                />
                                            }
                                            label="Beam Tilt Compensation"
                                        />
                                    </Stack>
                                </Box>

                                {/* Stage Settings */}
                                <Box>
                                    <Typography variant="subtitle2" gutterBottom>Stage Configuration</Typography>
                                    <Grid container spacing={2}>
                                        <Grid item xs={6}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>Holder Type</InputLabel>
                                                <Select
                                                    value={microscopeSettings.holderType}
                                                    label="Holder Type"
                                                    onChange={(e) => updateMicroscopeSettings({ holderType: e.target.value })}
                                                >
                                                    <MenuItem value="cryo">Cryo Holder</MenuItem>
                                                    <MenuItem value="single">Single Tilt</MenuItem>
                                                    <MenuItem value="double">Double Tilt</MenuItem>
                                                    <MenuItem value="tomography">Tomography Holder</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <Typography variant="body2" gutterBottom>
                                                Stage Speed: {microscopeSettings.stageSpeed}%
                                            </Typography>
                                            <Slider
                                                value={microscopeSettings.stageSpeed}
                                                onChange={(e, value) => updateMicroscopeSettings({ stageSpeed: value })}
                                                min={10}
                                                max={100}
                                                step={5}
                                                marks={[
                                                    { value: 25, label: '25%' },
                                                    { value: 50, label: '50%' },
                                                    { value: 75, label: '75%' },
                                                    { value: 100, label: '100%' }
                                                ]}
                                            />
                                        </Grid>
                                    </Grid>
                                </Box>

                                {/* Quick Alignment Buttons */}
                                <Box>
                                    <Typography variant="subtitle2" gutterBottom>Direct Alignments</Typography>
                                    <Grid container spacing={1}>
                                        {['Gun Tilt', 'Gun Shift', 'Beam Tilt', 'Beam Shift', 'Coma Free', 'Rotation Center'].map(alignment => (
                                            <Grid item xs={6} key={alignment}>
                                                <Button
                                                    variant="outlined"
                                                    size="small"
                                                    fullWidth
                                                    startIcon={<TuneIcon />}
                                                >
                                                    {alignment}
                                                </Button>
                                            </Grid>
                                        ))}
                                    </Grid>
                                </Box>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" startIcon={<SaveIcon />}>
                    Apply Settings
                </Button>
            </DialogActions>
        </Dialog>
    );
};

// Main Control Panel Component
export const ControlPanel = () => {
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
        cameraSettings,
        updateCameraSettings,
        microscopeSettings,
        updateMicroscopeSettings,
        isConnected,
        isAcquiring,
        setIsAcquiring,
        setLastImage,
        setLastFFT,
        advancedSettings,
        updateAdvancedSettings,
        presets,
        applyPreset,
        showCameraSettings,
        setShowCameraSettings,
        showMicroscopeSettings,
        setShowMicroscopeSettings
    } = useMicroscopeStore();

    const handleAcquireImage = async () => {
        if (!isConnected || isAcquiring) return;

        try {
            setIsAcquiring(true);
            const result = await microscopeAPI.acquireImage(acquisitionSettings);

            setLastImage(result.image);
            setLastFFT(result.fft);
        } catch (error) {
            console.error('Failed to acquire image:', error);
        } finally {
            setIsAcquiring(false);
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
                        <Tab label="Control" icon={<Focus size={20} />} />
                        <Tab label="Presets" icon={<SaveIcon />} />
                        <Tab label="Automation" icon={<Target size={20} />} />
                    </Tabs>

                    {/* Control Tab */}
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

                                    {/* Quick Actions */}
                                    <Box mt={3}>
                                        <Typography variant="subtitle2" gutterBottom color="text.secondary">
                                            Quick Actions
                                        </Typography>
                                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                            <Button size="small" variant="outlined" startIcon={<Target size={16} />}>
                                                Eucentric
                                            </Button>
                                            <Button size="small" variant="outlined" startIcon={<Activity size={16} />}>
                                                Reset
                                            </Button>
                                        </Stack>
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

                            {/* Acquisition Settings */}
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
                                        elevation={2}
                                        sx={{
                                            p: 2.5,
                                            cursor: 'pointer',
                                            borderRadius: 2,
                                            transition: 'all 0.3s ease',
                                            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(theme.palette.primary.main, 0.1)} 100%)`,
                                            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
                                            '&:hover': {
                                                transform: 'translateY(-4px)',
                                                boxShadow: 6,
                                                backgroundColor: alpha(theme.palette.primary.main, 0.15)
                                            }
                                        }}
                                        onClick={() => applyPreset(preset)}
                                    >
                                        <Typography variant="h6" sx={{ mb: 1.5, fontWeight: 600, color: 'primary.main' }}>
                                            {preset.name}
                                        </Typography>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                            <Typography variant="body2" color="text.secondary">
                                                📏 Magnification: {preset.mag.toLocaleString()}x
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                🎯 Defocus: {preset.defocus} μm
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                ⚡ Spot Size: {preset.spot}
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