import React, { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
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
    Chip,
    Alert,
    AlertTitle,
    Slider,
    Stack,
    useTheme,
    Tab,
    Tabs,
    IconButton,
    Tooltip
} from '@mui/material';
import {
    CheckCircle as CheckCircleIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    ZoomIn as ZoomInIcon,
    Tune as TuneIcon,
    Save as SaveIcon,
    Brightness4 as Brightness4Icon,
    FlashOn as FlashOnIcon,
    Thermostat as ThermostatIcon,
    Air as AirIcon,
    Build as BuildIcon,
    Security as SecurityIcon,
    AutoAwesome as AutoAwesomeIcon,
    Refresh as RefreshIcon, Security, Thermostat
} from '@mui/icons-material';
import { Microscope, Zap, Move, Eye } from 'lucide-react';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`microscope-tabpanel-${index}`}
            aria-labelledby={`microscope-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
        </div>
    );
}

interface MicroscopeSettingsDialogProps {
    open: boolean;
    onClose: () => void;

    // Electron Gun & High Voltage
    gunSettings?: {
        highTension: number;
        highTensionState: 'on' | 'off' | 'disabled';
        emission: boolean;
        gunTilt: { x: number; y: number };
        gunShift: { x: number; y: number };
        extractorVoltage?: number;
    };
    updateGunSettings?: (updates: any) => void;

    // Illumination System
    illuminationSettings?: {
        intensity: number;
        spotSize: number;
        probeMode: 'micro' | 'nano';
        beamBlank: boolean;
        beamShift: { x: number; y: number };
        beamTilt: { x: number; y: number };
        condenserStigmator: { x: number; y: number };
        darkFieldMode: 'off' | 'cartesian' | 'conical';
    };
    updateIlluminationSettings?: (updates: any) => void;

    // Projection System
    projectionSettings?: {
        magnification: number;
        projectionMode: 'imaging' | 'diffraction';
        projectionSubmode: 'LM' | 'Mi' | 'SA' | 'Mh' | 'LAD' | 'D';
        defocus: number;
        focus: number;
        imageShift: { x: number; y: number };
        diffractionShift: { x: number; y: number };
        objectiveStigmator: { x: number; y: number };
        diffractionStigmator: { x: number; y: number };
    };
    updateProjectionSettings?: (updates: any) => void;

    // Stage Control
    stageSettings?: {
        position: { x: number; y: number; z: number; a: number; b: number };
        status: 'ready' | 'busy' | 'moving';
        speed: number;
    };
    updateStageSettings?: (updates: any) => void;

    // System Status
    systemStatus?: {
        vacuumStatus: 'ready' | 'off' | 'busy' | 'camera' | 'unknown';
        columnPressure: number;
        projectionPressure: number;
        bufferTankPressure: number;
        columnValvePosition: 'open' | 'closed';
        mainScreenPosition: 'up' | 'down';
        screenCurrent: number;
    };

    // Advanced Settings
    advancedSettings?: {
        apertures: {
            condenser2: number;
            objective: number | 'open';
            selectedArea: number | 'open';
        };
        lowDose: {
            enabled: boolean;
            mode: 'exposure' | 'focus1' | 'focus2' | 'search';
        };
        energyFilter?: {
            enabled: boolean;
            width: number;
            offset: number;
        };
        phaseplate?: {
            enabled: boolean;
            position: number;
        };
        autoFunctions: {
            autoFocus: boolean;
            autoStigmation: boolean;
            beamTiltCompensation: boolean;
        };
        holderType: 'single tilt' | 'cryo' | 'tomography';
        refrigerantLevel?: number;
    };
    updateAdvancedSettings?: (updates: any) => void;
}

export const MicroscopeSettingsDialog: React.FC<MicroscopeSettingsDialogProps> = ({
                                                                                      open,
                                                                                      onClose,
                                                                                      gunSettings,
                                                                                      updateGunSettings,
                                                                                      illuminationSettings,
                                                                                      updateIlluminationSettings,
                                                                                      projectionSettings,
                                                                                      updateProjectionSettings,
                                                                                      stageSettings,
                                                                                      updateStageSettings,
                                                                                      systemStatus,
                                                                                      advancedSettings,
                                                                                      updateAdvancedSettings
                                                                                  }) => {
    const theme = useTheme();
    const [tabValue, setTabValue] = useState(0);

    // Default values to prevent undefined errors
    const defaultGunSettings = {
        highTension: 300,
        highTensionState: 'on' as const,
        emission: true,
        gunTilt: { x: 0, y: 0 },
        gunShift: { x: 0, y: 0 },
        extractorVoltage: 4500
    };

    const defaultIlluminationSettings = {
        intensity: 1e-6,
        spotSize: 5,
        probeMode: 'micro' as const,
        beamBlank: false,
        beamShift: { x: 0, y: 0 },
        beamTilt: { x: 0, y: 0 },
        condenserStigmator: { x: 0, y: 0 },
        darkFieldMode: 'off' as const
    };

    const defaultProjectionSettings = {
        magnification: 50000,
        projectionMode: 'imaging' as const,
        projectionSubmode: 'SA' as const,
        defocus: -2.0,
        focus: 0,
        imageShift: { x: 0, y: 0 },
        diffractionShift: { x: 0, y: 0 },
        objectiveStigmator: { x: 0, y: 0 },
        diffractionStigmator: { x: 0, y: 0 }
    };

    const defaultStageSettings = {
        position: { x: 0, y: 0, z: 0, a: 0, b: 0 },
        status: 'ready' as const,
        speed: 50
    };

    const defaultSystemStatus = {
        vacuumStatus: 'ready' as const,
        columnPressure: 5.2e-8,
        projectionPressure: 1.1e-8,
        bufferTankPressure: 2.3e-6,
        columnValvePosition: 'open' as const,
        mainScreenPosition: 'up' as const,
        screenCurrent: 12.5
    };

    const defaultAdvancedSettings = {
        apertures: {
            condenser2: 50,
            objective: 100 as const,
            selectedArea: 30 as const
        },
        lowDose: {
            enabled: false,
            mode: 'exposure' as const
        },
        energyFilter: {
            enabled: false,
            width: 20,
            offset: 0
        },
        phaseplate: {
            enabled: false,
            position: 1
        },
        autoFunctions: {
            autoFocus: false,
            autoStigmation: false,
            beamTiltCompensation: false
        },
        holderType: 'cryo' as const,
        refrigerantLevel: 85
    };

    // Use provided props or fall back to defaults with deep merging for nested objects
    const safeGunSettings = {
        ...defaultGunSettings,
        ...gunSettings,
        gunTilt: {
            ...defaultGunSettings.gunTilt,
            ...gunSettings?.gunTilt
        },
        gunShift: {
            ...defaultGunSettings.gunShift,
            ...gunSettings?.gunShift
        }
    };

    const safeIlluminationSettings = {
        ...defaultIlluminationSettings,
        ...illuminationSettings,
        beamShift: {
            ...defaultIlluminationSettings.beamShift,
            ...illuminationSettings?.beamShift
        },
        beamTilt: {
            ...defaultIlluminationSettings.beamTilt,
            ...illuminationSettings?.beamTilt
        },
        condenserStigmator: {
            ...defaultIlluminationSettings.condenserStigmator,
            ...illuminationSettings?.condenserStigmator
        }
    };

    const safeProjectionSettings = {
        ...defaultProjectionSettings,
        ...projectionSettings,
        imageShift: {
            ...defaultProjectionSettings.imageShift,
            ...projectionSettings?.imageShift
        },
        diffractionShift: {
            ...defaultProjectionSettings.diffractionShift,
            ...projectionSettings?.diffractionShift
        },
        objectiveStigmator: {
            ...defaultProjectionSettings.objectiveStigmator,
            ...projectionSettings?.objectiveStigmator
        },
        diffractionStigmator: {
            ...defaultProjectionSettings.diffractionStigmator,
            ...projectionSettings?.diffractionStigmator
        }
    };

    const safeStageSettings = {
        ...defaultStageSettings,
        ...stageSettings,
        position: {
            ...defaultStageSettings.position,
            ...stageSettings?.position
        }
    };

    const safeSystemStatus = {
        ...defaultSystemStatus,
        ...systemStatus
    };

    const safeAdvancedSettings = {
        ...defaultAdvancedSettings,
        ...advancedSettings,
        apertures: {
            ...defaultAdvancedSettings.apertures,
            ...advancedSettings?.apertures
        },
        lowDose: {
            ...defaultAdvancedSettings.lowDose,
            ...advancedSettings?.lowDose
        },
        energyFilter: {
            ...defaultAdvancedSettings.energyFilter,
            ...advancedSettings?.energyFilter
        },
        phaseplate: {
            ...defaultAdvancedSettings.phaseplate,
            ...advancedSettings?.phaseplate
        },
        autoFunctions: {
            ...defaultAdvancedSettings.autoFunctions,
            ...advancedSettings?.autoFunctions
        }
    };

    // Safe update functions
    const safeUpdateGunSettings = updateGunSettings || (() => {});
    const safeUpdateIlluminationSettings = updateIlluminationSettings || (() => {});
    const safeUpdateProjectionSettings = updateProjectionSettings || (() => {});
    const safeUpdateStageSettings = updateStageSettings || (() => {});
    const safeUpdateAdvancedSettings = updateAdvancedSettings || (() => {});

    const magnificationOptions = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 25000, 50000, 81000, 105000, 130000, 165000, 215000];
    const spotSizeOptions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const apertureOptions = [10, 30, 50, 70, 100, 150, 200];

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'ready':
            case 'on':
            case 'open':
                return <CheckCircleIcon color="success" />;
            case 'busy':
            case 'moving':
                return <WarningIcon color="warning" />;
            case 'off':
            case 'closed':
            case 'disabled':
                return <ErrorIcon color="error" />;
            default:
                return <WarningIcon color="warning" />;
        }
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box display="flex" alignItems="center" gap={2}>
                        <Microscope size={24} />
                        <Typography variant="h5" fontWeight="600">
                            Microscope Control Center
                        </Typography>
                        <Chip
                            icon={getStatusIcon(safeSystemStatus.vacuumStatus)}
                            label={`${safeSystemStatus.vacuumStatus.toUpperCase()}`}
                            color={safeSystemStatus.vacuumStatus === 'ready' ? 'success' : 'warning'}
                            size="small"
                            variant="outlined"
                        />
                    </Box>
                    <IconButton onClick={() => window.location.reload()}>
                        <RefreshIcon />
                    </IconButton>
                </Box>
            </DialogTitle>

            <DialogContent>
                <Stack spacing={3} sx={{ mt: 1 }}>
                    {/* System Status Alert */}
                    <Alert
                        severity={safeSystemStatus.vacuumStatus === 'ready' ? 'success' : 'warning'}
                        icon={getStatusIcon(safeSystemStatus.vacuumStatus)}
                    >
                        <AlertTitle>System Status - Titan Krios G4</AlertTitle>
                        HT: {safeGunSettings.highTension}kV • Vacuum: {safeSystemStatus.columnPressure.toExponential(1)} Pa •
                        Column: {safeSystemStatus.columnValvePosition} • Magnification: {safeProjectionSettings.magnification.toLocaleString()}x
                        {safeAdvancedSettings.refrigerantLevel !== undefined && ` • LN2: ${safeAdvancedSettings.refrigerantLevel}%`}
                    </Alert>

                    {/* Main Control Tabs */}
                    <Paper elevation={1}>
                        <Tabs value={tabValue} onChange={handleTabChange} variant="scrollable" scrollButtons="auto">
                            <Tab icon={<FlashOnIcon />} label="Gun & HT" />
                            <Tab icon={<Brightness4Icon />} label="Illumination" />
                            <Tab icon={<ZoomInIcon />} label="Projection" />
                            <Tab icon={<Move />} label="Stage" />
                            <Tab icon={<AirIcon />} label="Vacuum" />
                            <Tab icon={<TuneIcon />} label="Advanced" />
                        </Tabs>

                        {/* Gun & High Tension Tab */}
                        <TabPanel value={tabValue} index={0}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Zap size={20} />
                                    Electron Gun & High Tension
                                </Typography>

                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="High Tension (kV)"
                                            type="number"
                                            value={safeGunSettings.highTension}
                                            onChange={(e) => safeUpdateGunSettings({ highTension: parseFloat(e.target.value) })}
                                            slotProps={{
                                                input: {
                                                    endAdornment: (
                                                        <Chip
                                                            icon={getStatusIcon(safeGunSettings.highTensionState)}
                                                            label={safeGunSettings.highTensionState.toUpperCase()}
                                                            size="small"
                                                            color={safeGunSettings.highTensionState === 'on' ? 'success' : 'default'}
                                                        />
                                                    )
                                                }
                                            }}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={safeGunSettings.emission}
                                                    onChange={(e) => safeUpdateGunSettings({ emission: e.target.checked })}
                                                    color="success"
                                                />
                                            }
                                            label="Gun Emission"
                                        />
                                    </Grid>

                                    {safeGunSettings.extractorVoltage !== undefined && (
                                        <Grid item xs={6}>
                                            <TextField
                                                fullWidth
                                                label="Extractor Voltage (V)"
                                                type="number"
                                                value={safeGunSettings.extractorVoltage}
                                                onChange={(e) => safeUpdateGunSettings({ extractorVoltage: parseFloat(e.target.value) })}
                                            />
                                        </Grid>
                                    )}

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Gun Tilt (μrad)</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="0.1"
                                                    value={safeGunSettings.gunTilt.x}
                                                    onChange={(e) => safeUpdateGunSettings({
                                                        gunTilt: { ...safeGunSettings.gunTilt, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="0.1"
                                                    value={safeGunSettings.gunTilt.y}
                                                    onChange={(e) => safeUpdateGunSettings({
                                                        gunTilt: { ...safeGunSettings.gunTilt, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Gun Shift (nm)</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="1"
                                                    value={safeGunSettings.gunShift.x}
                                                    onChange={(e) => safeUpdateGunSettings({
                                                        gunShift: { ...safeGunSettings.gunShift, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="1"
                                                    value={safeGunSettings.gunShift.y}
                                                    onChange={(e) => safeUpdateGunSettings({
                                                        gunShift: { ...safeGunSettings.gunShift, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </TabPanel>

                        {/* Illumination Tab */}
                        <TabPanel value={tabValue} index={1}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Brightness4Icon />
                                    Illumination System
                                </Typography>

                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <FormControl fullWidth>
                                            <InputLabel>Spot Size</InputLabel>
                                            <Select
                                                value={safeIlluminationSettings.spotSize}
                                                label="Spot Size"
                                                onChange={(e) => safeUpdateIlluminationSettings({ spotSize: Number(e.target.value) })}
                                            >
                                                {spotSizeOptions.map(size => (
                                                    <MenuItem key={size} value={size}>{size}</MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth>
                                            <InputLabel>Probe Mode</InputLabel>
                                            <Select
                                                value={safeIlluminationSettings.probeMode}
                                                label="Probe Mode"
                                                onChange={(e) => safeUpdateIlluminationSettings({ probeMode: e.target.value })}
                                            >
                                                <MenuItem value="micro">Micro Probe</MenuItem>
                                                <MenuItem value="nano">Nano Probe</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>
                                            Intensity: {safeIlluminationSettings.intensity.toExponential(2)}
                                        </Typography>
                                        <Slider
                                            value={Math.log10(safeIlluminationSettings.intensity)}
                                            onChange={(e, value) => safeUpdateIlluminationSettings({ intensity: Math.pow(10, value as number) })}
                                            min={-8}
                                            max={-3}
                                            step={0.1}
                                            marks={[
                                                { value: -8, label: '10⁻⁸' },
                                                { value: -6, label: '10⁻⁶' },
                                                { value: -4, label: '10⁻⁴' },
                                                { value: -3, label: '10⁻³' }
                                            ]}
                                        />
                                    </Grid>

                                    <Grid item xs={12}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={!safeIlluminationSettings.beamBlank}
                                                    onChange={(e) => safeUpdateIlluminationSettings({ beamBlank: !e.target.checked })}
                                                    color={safeIlluminationSettings.beamBlank ? "error" : "success"}
                                                />
                                            }
                                            label={
                                                <Box display="flex" alignItems="center" gap={1}>
                                                    <Security />
                                                    {safeIlluminationSettings.beamBlank ? 'Beam Blanked' : 'Beam On'}
                                                </Box>
                                            }
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Beam Shift (nm)</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="1"
                                                    value={safeIlluminationSettings.beamShift.x}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        beamShift: { ...safeIlluminationSettings.beamShift, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="1"
                                                    value={safeIlluminationSettings.beamShift.y}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        beamShift: { ...safeIlluminationSettings.beamShift, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Beam Tilt (μrad)</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="0.1"
                                                    value={safeIlluminationSettings.beamTilt.x}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        beamTilt: { ...safeIlluminationSettings.beamTilt, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="0.1"
                                                    value={safeIlluminationSettings.beamTilt.y}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        beamTilt: { ...safeIlluminationSettings.beamTilt, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Condenser Stigmator</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="0.01"
                                                    value={safeIlluminationSettings.condenserStigmator.x}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        condenserStigmator: { ...safeIlluminationSettings.condenserStigmator, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="0.01"
                                                    value={safeIlluminationSettings.condenserStigmator.y}
                                                    onChange={(e) => safeUpdateIlluminationSettings({
                                                        condenserStigmator: { ...safeIlluminationSettings.condenserStigmator, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth>
                                            <InputLabel>Dark Field Mode</InputLabel>
                                            <Select
                                                value={safeIlluminationSettings.darkFieldMode}
                                                label="Dark Field Mode"
                                                onChange={(e) => safeUpdateIlluminationSettings({ darkFieldMode: e.target.value })}
                                            >
                                                <MenuItem value="off">Off</MenuItem>
                                                <MenuItem value="cartesian">Cartesian</MenuItem>
                                                <MenuItem value="conical">Conical</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </TabPanel>

                        {/* Projection Tab */}
                        <TabPanel value={tabValue} index={2}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Eye size={20} />
                                    Projection System
                                </Typography>

                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <FormControl fullWidth>
                                            <InputLabel>Magnification</InputLabel>
                                            <Select
                                                value={safeProjectionSettings.magnification}
                                                label="Magnification"
                                                onChange={(e) => safeUpdateProjectionSettings({ magnification: Number(e.target.value) })}
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
                                        <FormControl fullWidth>
                                            <InputLabel>Projection Mode</InputLabel>
                                            <Select
                                                value={safeProjectionSettings.projectionMode}
                                                label="Projection Mode"
                                                onChange={(e) => safeUpdateProjectionSettings({ projectionMode: e.target.value })}
                                            >
                                                <MenuItem value="imaging">Imaging</MenuItem>
                                                <MenuItem value="diffraction">Diffraction</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Defocus (μm)"
                                            type="number"
                                            step="0.1"
                                            value={safeProjectionSettings.defocus}
                                            onChange={(e) => safeUpdateProjectionSettings({ defocus: parseFloat(e.target.value) })}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Focus"
                                            type="number"
                                            step="0.001"
                                            value={safeProjectionSettings.focus}
                                            onChange={(e) => safeUpdateProjectionSettings({ focus: parseFloat(e.target.value) })}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Image Shift (nm)</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="1"
                                                    value={safeProjectionSettings.imageShift.x}
                                                    onChange={(e) => safeUpdateProjectionSettings({
                                                        imageShift: { ...safeProjectionSettings.imageShift, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="1"
                                                    value={safeProjectionSettings.imageShift.y}
                                                    onChange={(e) => safeUpdateProjectionSettings({
                                                        imageShift: { ...safeProjectionSettings.imageShift, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Typography variant="subtitle2" gutterBottom>Objective Stigmator</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="X"
                                                    type="number"
                                                    step="0.01"
                                                    value={safeProjectionSettings.objectiveStigmator.x}
                                                    onChange={(e) => safeUpdateProjectionSettings({
                                                        objectiveStigmator: { ...safeProjectionSettings.objectiveStigmator, x: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    size="small"
                                                    label="Y"
                                                    type="number"
                                                    step="0.01"
                                                    value={safeProjectionSettings.objectiveStigmator.y}
                                                    onChange={(e) => safeUpdateProjectionSettings({
                                                        objectiveStigmator: { ...safeProjectionSettings.objectiveStigmator, y: parseFloat(e.target.value) }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    {safeProjectionSettings.projectionMode === 'diffraction' && (
                                        <Grid item xs={6}>
                                            <Typography variant="subtitle2" gutterBottom>Diffraction Shift (nm)</Typography>
                                            <Grid container spacing={1}>
                                                <Grid item xs={6}>
                                                    <TextField
                                                        size="small"
                                                        label="X"
                                                        type="number"
                                                        step="1"
                                                        value={safeProjectionSettings.diffractionShift.x}
                                                        onChange={(e) => safeUpdateProjectionSettings({
                                                            diffractionShift: { ...safeProjectionSettings.diffractionShift, x: parseFloat(e.target.value) }
                                                        })}
                                                    />
                                                </Grid>
                                                <Grid item xs={6}>
                                                    <TextField
                                                        size="small"
                                                        label="Y"
                                                        type="number"
                                                        step="1"
                                                        value={safeProjectionSettings.diffractionShift.y}
                                                        onChange={(e) => safeUpdateProjectionSettings({
                                                            diffractionShift: { ...safeProjectionSettings.diffractionShift, y: parseFloat(e.target.value) }
                                                        })}
                                                    />
                                                </Grid>
                                            </Grid>
                                        </Grid>
                                    )}

                                    <Grid item xs={12}>
                                        <FormControl fullWidth>
                                            <InputLabel>Projection Submode</InputLabel>
                                            <Select
                                                value={safeProjectionSettings.projectionSubmode}
                                                label="Projection Submode"
                                                onChange={(e) => safeUpdateProjectionSettings({ projectionSubmode: e.target.value })}
                                            >
                                                <MenuItem value="LM">LM (Low Magnification)</MenuItem>
                                                <MenuItem value="Mi">Mi (Micro)</MenuItem>
                                                <MenuItem value="SA">SA (Selected Area)</MenuItem>
                                                <MenuItem value="Mh">Mh (Micro High)</MenuItem>
                                                <MenuItem value="LAD">LAD (Large Area Diffraction)</MenuItem>
                                                <MenuItem value="D">D (Diffraction)</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </TabPanel>

                        {/* Stage Tab */}
                        <TabPanel value={tabValue} index={3}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Box display="flex" alignItems="center" justifyContent="space-between">
                                    <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Move size={20} />
                                        Stage Control
                                    </Typography>
                                    <Chip
                                        icon={getStatusIcon(safeStageSettings.status)}
                                        label={`Stage: ${safeStageSettings.status.toUpperCase()}`}
                                        color={safeStageSettings.status === 'ready' ? 'success' : 'warning'}
                                        size="small"
                                    />
                                </Box>

                                <Grid container spacing={3}>
                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>Stage Position</Typography>
                                        <Grid container spacing={2}>
                                            <Grid item xs={4}>
                                                <TextField
                                                    fullWidth
                                                    label="X (μm)"
                                                    type="number"
                                                    step="0.1"
                                                    value={(safeStageSettings.position.x * 1e6)?.toFixed(1)}
                                                    onChange={(e) => safeUpdateStageSettings({
                                                        position: {
                                                            ...safeStageSettings.position,
                                                            x: parseFloat(e.target.value) / 1e6
                                                        }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={4}>
                                                <TextField
                                                    fullWidth
                                                    label="Y (μm)"
                                                    type="number"
                                                    step="0.1"
                                                    value={(safeStageSettings.position.y * 1e6)?.toFixed(1)}
                                                    onChange={(e) => safeUpdateStageSettings({
                                                        position: {
                                                            ...safeStageSettings.position,
                                                            y: parseFloat(e.target.value) / 1e6
                                                        }
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={4}>
                                                <TextField
                                                    fullWidth
                                                    label="Z (μm)"
                                                    type="number"
                                                    step="0.1"
                                                    value={(safeStageSettings.position.z * 1e6)?.toFixed(1)}
                                                    onChange={(e) => safeUpdateStageSettings({
                                                        position: {
                                                            ...safeStageSettings.position,
                                                            z: parseFloat(e.target.value) / 1e6
                                                        }
                                                    })}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>Tilt Angles</Typography>
                                        <Grid container spacing={2}>
                                            <Grid item xs={6}>
                                                <TextField
                                                    fullWidth
                                                    label="Alpha (°)"
                                                    type="number"
                                                    step="0.1"
                                                    value={(safeStageSettings.position.a * 180 / Math.PI)?.toFixed(1)}
                                                    onChange={(e) => safeUpdateStageSettings({
                                                        position: {
                                                            ...safeStageSettings.position,
                                                            a: parseFloat(e.target.value) * Math.PI / 180
                                                        }
                                                    })}
                                                    slotProps={{
                                                        htmlInput: { min: -70, max: 70 }
                                                    }}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    fullWidth
                                                    label="Beta (°)"
                                                    type="number"
                                                    step="0.1"
                                                    value={(safeStageSettings.position.b * 180 / Math.PI)?.toFixed(1)}
                                                    onChange={(e) => safeUpdateStageSettings({
                                                        position: {
                                                            ...safeStageSettings.position,
                                                            b: parseFloat(e.target.value) * Math.PI / 180
                                                        }
                                                    })}
                                                    slotProps={{
                                                        htmlInput: { min: -90, max: 90 }
                                                    }}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Grid>

                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>
                                            Stage Speed: {safeStageSettings.speed}%
                                        </Typography>
                                        <Slider
                                            value={safeStageSettings.speed}
                                            onChange={(e, value) => safeUpdateStageSettings({ speed: value })}
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

                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>Quick Stage Actions</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Go to Zero
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Eucentric Height
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Save Position
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Load Position
                                                </Button>
                                            </Grid>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </TabPanel>

                        {/* Vacuum Tab */}
                        <TabPanel value={tabValue} index={4}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <AirIcon />
                                    Vacuum System
                                </Typography>

                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <Paper elevation={2} sx={{ p: 2 }}>
                                            <Typography variant="subtitle1" gutterBottom>System Status</Typography>
                                            <Box display="flex" alignItems="center" gap={1} mb={1}>
                                                {getStatusIcon(safeSystemStatus.vacuumStatus)}
                                                <Typography variant="body1">
                                                    Vacuum: {safeSystemStatus.vacuumStatus.toUpperCase()}
                                                </Typography>
                                            </Box>
                                            <Box display="flex" alignItems="center" gap={1}>
                                                {getStatusIcon(safeSystemStatus.columnValvePosition)}
                                                <Typography variant="body1">
                                                    Column Valve: {safeSystemStatus.columnValvePosition.toUpperCase()}
                                                </Typography>
                                            </Box>
                                        </Paper>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <Paper elevation={2} sx={{ p: 2 }}>
                                            <Typography variant="subtitle1" gutterBottom>Screen Status</Typography>
                                            <Box display="flex" alignItems="center" gap={1} mb={1}>
                                                {getStatusIcon(safeSystemStatus.mainScreenPosition)}
                                                <Typography variant="body1">
                                                    Main Screen: {safeSystemStatus.mainScreenPosition.toUpperCase()}
                                                </Typography>
                                            </Box>
                                            <Typography variant="body2">
                                                Screen Current: {safeSystemStatus.screenCurrent?.toFixed(2)} pA
                                            </Typography>
                                        </Paper>
                                    </Grid>

                                    <Grid item xs={4}>
                                        <TextField
                                            fullWidth
                                            label="Column Pressure"
                                            value={safeSystemStatus.columnPressure.toExponential(2)}
                                            slotProps={{
                                                input: {
                                                    readOnly: true,
                                                    endAdornment: <Typography variant="caption">Pa</Typography>
                                                }
                                            }}
                                        />
                                    </Grid>

                                    <Grid item xs={4}>
                                        <TextField
                                            fullWidth
                                            label="Projection Pressure"
                                            value={safeSystemStatus.projectionPressure.toExponential(2)}
                                            slotProps={{
                                                input: {
                                                    readOnly: true,
                                                    endAdornment: <Typography variant="caption">Pa</Typography>
                                                }
                                            }}
                                        />
                                    </Grid>

                                    <Grid item xs={4}>
                                        <TextField
                                            fullWidth
                                            label="Buffer Tank Pressure"
                                            value={safeSystemStatus.bufferTankPressure.toExponential(2)}
                                            slotProps={{
                                                input: {
                                                    readOnly: true,
                                                    endAdornment: <Typography variant="caption">Pa</Typography>
                                                }
                                            }}
                                        />
                                    </Grid>

                                    <Grid item xs={12}>
                                        <Typography variant="subtitle2" gutterBottom>Vacuum Controls</Typography>
                                        <Grid container spacing={1}>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Open Column Valve
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Close Column Valve
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth>
                                                    Buffer Cycle
                                                </Button>
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button variant="outlined" size="small" fullWidth color="warning">
                                                    Emergency Vent
                                                </Button>
                                            </Grid>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </TabPanel>

                        {/* Advanced Tab */}
                        <TabPanel value={tabValue} index={5}>
                            <Stack spacing={3} sx={{ p: 3 }}>
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <TuneIcon />
                                    Advanced Configuration
                                </Typography>

                                {/* Apertures */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom>Apertures</Typography>
                                    <Grid container spacing={2}>
                                        <Grid item xs={4}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>C2 Aperture</InputLabel>
                                                <Select
                                                    value={safeAdvancedSettings.apertures.condenser2}
                                                    label="C2 Aperture"
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        apertures: {
                                                            ...safeAdvancedSettings.apertures,
                                                            condenser2: Number(e.target.value)
                                                        }
                                                    })}
                                                >
                                                    {apertureOptions.map(size => (
                                                        <MenuItem key={size} value={size}>{size} μm</MenuItem>
                                                    ))}
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>Objective Aperture</InputLabel>
                                                <Select
                                                    value={safeAdvancedSettings.apertures.objective}
                                                    label="Objective Aperture"
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        apertures: {
                                                            ...safeAdvancedSettings.apertures,
                                                            objective: e.target.value
                                                        }
                                                    })}
                                                >
                                                    {apertureOptions.map(size => (
                                                        <MenuItem key={size} value={size}>{size} μm</MenuItem>
                                                    ))}
                                                    <MenuItem value="open">Open</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>SA Aperture</InputLabel>
                                                <Select
                                                    value={safeAdvancedSettings.apertures.selectedArea}
                                                    label="SA Aperture"
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        apertures: {
                                                            ...safeAdvancedSettings.apertures,
                                                            selectedArea: e.target.value
                                                        }
                                                    })}
                                                >
                                                    {apertureOptions.map(size => (
                                                        <MenuItem key={size} value={size}>{size} μm</MenuItem>
                                                    ))}
                                                    <MenuItem value="open">Open</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                    </Grid>
                                </Paper>

                                {/* Low Dose Mode */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom>Low Dose Mode</Typography>
                                    <Grid container spacing={2} alignItems="center">
                                        <Grid item xs={6}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={safeAdvancedSettings.lowDose.enabled}
                                                        onChange={(e) => safeUpdateAdvancedSettings({
                                                            lowDose: {
                                                                ...safeAdvancedSettings.lowDose,
                                                                enabled: e.target.checked
                                                            }
                                                        })}
                                                    />
                                                }
                                                label="Enable Low Dose"
                                            />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <FormControl fullWidth size="small" disabled={!safeAdvancedSettings.lowDose.enabled}>
                                                <InputLabel>Low Dose Mode</InputLabel>
                                                <Select
                                                    value={safeAdvancedSettings.lowDose.mode}
                                                    label="Low Dose Mode"
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        lowDose: {
                                                            ...safeAdvancedSettings.lowDose,
                                                            mode: e.target.value
                                                        }
                                                    })}
                                                >
                                                    <MenuItem value="exposure">Exposure</MenuItem>
                                                    <MenuItem value="focus1">Focus 1</MenuItem>
                                                    <MenuItem value="focus2">Focus 2</MenuItem>
                                                    <MenuItem value="search">Search</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                    </Grid>
                                </Paper>

                                {/* Energy Filter */}
                                {safeAdvancedSettings.energyFilter && (
                                    <Paper elevation={1} sx={{ p: 2 }}>
                                        <Typography variant="subtitle1" gutterBottom>Energy Filter</Typography>
                                        <Grid container spacing={2} alignItems="center">
                                            <Grid item xs={4}>
                                                <FormControlLabel
                                                    control={
                                                        <Switch
                                                            checked={safeAdvancedSettings.energyFilter.enabled}
                                                            onChange={(e) => safeUpdateAdvancedSettings({
                                                                energyFilter: {
                                                                    ...safeAdvancedSettings.energyFilter,
                                                                    enabled: e.target.checked
                                                                }
                                                            })}
                                                        />
                                                    }
                                                    label="Enable Filter"
                                                />
                                            </Grid>
                                            <Grid item xs={4}>
                                                <TextField
                                                    fullWidth
                                                    size="small"
                                                    label="Width (eV)"
                                                    type="number"
                                                    value={safeAdvancedSettings.energyFilter.width}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        energyFilter: {
                                                            ...safeAdvancedSettings.energyFilter,
                                                            width: parseFloat(e.target.value)
                                                        }
                                                    })}
                                                    disabled={!safeAdvancedSettings.energyFilter.enabled}
                                                />
                                            </Grid>
                                            <Grid item xs={4}>
                                                <TextField
                                                    fullWidth
                                                    size="small"
                                                    label="Offset (eV)"
                                                    type="number"
                                                    value={safeAdvancedSettings.energyFilter.offset}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        energyFilter: {
                                                            ...safeAdvancedSettings.energyFilter,
                                                            offset: parseFloat(e.target.value)
                                                        }
                                                    })}
                                                    disabled={!safeAdvancedSettings.energyFilter.enabled}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Paper>
                                )}

                                {/* Phase Plate */}
                                {safeAdvancedSettings.phaseplate && (
                                    <Paper elevation={1} sx={{ p: 2 }}>
                                        <Typography variant="subtitle1" gutterBottom>Volta Phase Plate</Typography>
                                        <Grid container spacing={2} alignItems="center">
                                            <Grid item xs={6}>
                                                <FormControlLabel
                                                    control={
                                                        <Switch
                                                            checked={safeAdvancedSettings.phaseplate.enabled}
                                                            onChange={(e) => safeUpdateAdvancedSettings({
                                                                phaseplate: {
                                                                    ...safeAdvancedSettings.phaseplate,
                                                                    enabled: e.target.checked
                                                                }
                                                            })}
                                                        />
                                                    }
                                                    label="Enable Phase Plate"
                                                />
                                            </Grid>
                                            <Grid item xs={3}>
                                                <TextField
                                                    fullWidth
                                                    size="small"
                                                    label="Position"
                                                    type="number"
                                                    value={safeAdvancedSettings.phaseplate.position}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        phaseplate: {
                                                            ...safeAdvancedSettings.phaseplate,
                                                            position: parseInt(e.target.value)
                                                        }
                                                    })}
                                                    disabled={!safeAdvancedSettings.phaseplate.enabled}
                                                />
                                            </Grid>
                                            <Grid item xs={3}>
                                                <Button
                                                    variant="outlined"
                                                    size="small"
                                                    fullWidth
                                                    disabled={!safeAdvancedSettings.phaseplate.enabled}
                                                >
                                                    Next Position
                                                </Button>
                                            </Grid>
                                        </Grid>
                                    </Paper>
                                )}

                                {/* Auto Functions */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <AutoAwesomeIcon />
                                        Auto Functions
                                    </Typography>
                                    <Stack spacing={1}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={safeAdvancedSettings.autoFunctions.autoFocus}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        autoFunctions: {
                                                            ...safeAdvancedSettings.autoFunctions,
                                                            autoFocus: e.target.checked
                                                        }
                                                    })}
                                                />
                                            }
                                            label="Auto Eucentric Focus"
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={safeAdvancedSettings.autoFunctions.autoStigmation}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        autoFunctions: {
                                                            ...safeAdvancedSettings.autoFunctions,
                                                            autoStigmation: e.target.checked
                                                        }
                                                    })}
                                                />
                                            }
                                            label="Auto Stigmation"
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={safeAdvancedSettings.autoFunctions.beamTiltCompensation}
                                                    onChange={(e) => safeUpdateAdvancedSettings({
                                                        autoFunctions: {
                                                            ...safeAdvancedSettings.autoFunctions,
                                                            beamTiltCompensation: e.target.checked
                                                        }
                                                    })}
                                                />
                                            }
                                            label="Beam Tilt Compensation"
                                        />
                                    </Stack>
                                </Paper>

                                {/* Specimen Holder */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom>Specimen Holder</Typography>
                                    <Grid container spacing={2} alignItems="center">
                                        <Grid item xs={6}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel>Holder Type</InputLabel>
                                                <Select
                                                    value={safeAdvancedSettings.holderType}
                                                    label="Holder Type"
                                                    onChange={(e) => safeUpdateAdvancedSettings({ holderType: e.target.value })}
                                                >
                                                    <MenuItem value="single tilt">Single Tilt</MenuItem>
                                                    <MenuItem value="cryo">Cryo Holder</MenuItem>
                                                    <MenuItem value="tomography">Tomography Holder</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        {safeAdvancedSettings.refrigerantLevel !== undefined && (
                                            <Grid item xs={6}>
                                                <Box>
                                                    <Typography variant="body2" gutterBottom>
                                                        Refrigerant Level: {safeAdvancedSettings.refrigerantLevel}%
                                                    </Typography>
                                                    <Box display="flex" alignItems="center" gap={1}>
                                                        <Thermostat color={safeAdvancedSettings.refrigerantLevel > 20 ? 'primary' : 'error'} />
                                                        <Box
                                                            sx={{
                                                                width: '100%',
                                                                height: 8,
                                                                bgcolor: 'grey.300',
                                                                borderRadius: 1,
                                                                overflow: 'hidden'
                                                            }}
                                                        >
                                                            <Box
                                                                sx={{
                                                                    width: `${safeAdvancedSettings.refrigerantLevel}%`,
                                                                    height: '100%',
                                                                    bgcolor: safeAdvancedSettings.refrigerantLevel > 20 ? 'success.main' : 'error.main',
                                                                    transition: 'width 0.3s'
                                                                }}
                                                            />
                                                        </Box>
                                                    </Box>
                                                </Box>
                                            </Grid>
                                        )}
                                    </Grid>
                                </Paper>

                                {/* Quick Alignment Buttons */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom>Direct Alignments</Typography>
                                    <Grid container spacing={1}>
                                        {['Gun Tilt', 'Gun Shift', 'Beam Tilt', 'Beam Shift', 'Coma Free', 'Rotation Center'].map(alignment => (
                                            <Grid item xs={4} key={alignment}>
                                                <Button
                                                    variant="outlined"
                                                    size="small"
                                                    fullWidth
                                                    startIcon={<BuildIcon />}
                                                >
                                                    {alignment}
                                                </Button>
                                            </Grid>
                                        ))}
                                    </Grid>
                                </Paper>
                            </Stack>
                        </TabPanel>
                    </Paper>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="outlined" startIcon={<RefreshIcon />}>
                    Reset to Defaults
                </Button>
                <Button variant="contained" startIcon={<SaveIcon />} color="primary">
                    Apply Settings
                </Button>
            </DialogActions>
        </Dialog>
    );
};