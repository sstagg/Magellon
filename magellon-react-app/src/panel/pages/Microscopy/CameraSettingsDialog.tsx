import React, { useState, useEffect } from 'react';
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
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Chip,
    Alert,
    AlertTitle,
    ToggleButton,
    ToggleButtonGroup,
    Stack,
    Divider,
    IconButton,
    Tooltip
} from '@mui/material';
import {
    PhotoCamera as PhotoCameraIcon,
    ExpandMore as ExpandMoreIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    Save as SaveIcon,
    Refresh as RefreshIcon,
    Settings as SettingsIcon,
    Memory as MemoryIcon,
    Tune as TuneIcon,
    Timer as TimerIcon,
    Storage as StorageIcon,
    Psychology as PsychologyIcon,
    Folder as FolderIcon,
} from '@mui/icons-material';

interface CameraSettingsDialogProps {
    open: boolean;
    onClose: () => void;
    cameraSettings: any;
    updateCameraSettings: (updates: any) => void;
    acquisitionSettings: any;
    updateAcquisitionSettings: (updates: any) => void;
    availableProperties?: string[];
    systemStatus?: {
        system: string;
        position: string;
        temperature: string;
    };
    onPropertyChange?: (propertyName: string, value: any) => Promise<void>;
}

export const CameraSettingsDialog: React.FC<CameraSettingsDialogProps> = ({
                                                                              open,
                                                                              onClose,
                                                                              cameraSettings,
                                                                              updateCameraSettings,
                                                                              acquisitionSettings,
                                                                              updateAcquisitionSettings,
                                                                              availableProperties = [],
                                                                              systemStatus,
                                                                              onPropertyChange
                                                                          }) => {
    const [hardwareExpanded, setHardwareExpanded] = useState(true);
    const [timingExpanded, setTimingExpanded] = useState(false);
    const [processingExpanded, setProcessingExpanded] = useState(false);
    const [autosaveExpanded, setAutosaveExpanded] = useState(false);
    const [advancedExpanded, setAdvancedExpanded] = useState(false);
    const [presets, setPresets] = useState<string[]>([]);
    const [currentPreset, setCurrentPreset] = useState('');

    // Check if property is available
    const isPropertyAvailable = (propertyName: string) => {
        return availableProperties.includes(propertyName);
    };

    // Handle DE-SDK property changes
    const handlePropertyChange = async (propertyName: string, value: any) => {
        if (!isPropertyAvailable(propertyName)) {
            console.warn(`Property ${propertyName} not available for this camera`);
            return;
        }

        if (onPropertyChange) {
            await onPropertyChange(propertyName, value);
        }
    };

    // Load presets on mount
    useEffect(() => {
        const loadPresets = async () => {
            if (isPropertyAvailable('Preset - List')) {
                // This would be loaded from the DE-SDK
                // setPresets(presetList);
            }
        };
        loadPresets();
    }, [availableProperties]);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={2}>
                    <PhotoCameraIcon color="primary" />
                    <Typography variant="h5" fontWeight="600">
                        DE Camera Settings
                    </Typography>
                    <Chip
                        icon={<CheckCircleIcon />}
                        label={systemStatus?.system || "Connected"}
                        color="success"
                        size="small"
                        variant="outlined"
                    />
                    <Tooltip title="Debug Properties">
                        <IconButton size="small">
                            {/*<Debug />*/}
                        </IconButton>
                    </Tooltip>
                </Box>
            </DialogTitle>

            <DialogContent>
                <Stack spacing={2} sx={{ mt: 1 }}>
                    {/* Status Alert */}
                    <Alert severity="info" icon={<InfoIcon />}>
                        <AlertTitle>DE-64 Counting Camera</AlertTitle>
                        Temperature: {systemStatus?.temperature || cameraSettings.temperature}°C •
                        Position: {systemStatus?.position || "Ready"} •
                        Status: {systemStatus?.system || "Ready"}
                    </Alert>

                    {/* Preset Selection */}
                    {isPropertyAvailable('Preset - Current') && (
                        <Paper elevation={1} sx={{ p: 2 }}>
                            <Grid container spacing={2} alignItems="center">
                                <Grid item xs={6}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Camera Preset</InputLabel>
                                        <Select
                                            value={currentPreset}
                                            label="Camera Preset"
                                            onChange={(e) => handlePropertyChange('Preset - Current', e.target.value)}
                                        >
                                            {presets.map(preset => (
                                                <MenuItem key={preset} value={preset}>{preset}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="body2" color="text.secondary">
                                        Select a preset to quickly configure camera settings
                                    </Typography>
                                </Grid>
                            </Grid>
                        </Paper>
                    )}

                    {/* Hardware Settings */}
                    <Accordion expanded={hardwareExpanded} onChange={(e, isExpanded) => setHardwareExpanded(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <MemoryIcon />
                                Hardware Configuration
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={3}>
                                    {/* Hardware Binning */}
                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Hardware Binning X</InputLabel>
                                            <Select
                                                value={cameraSettings['Hardware Binning X'] || 1}
                                                label="Hardware Binning X"
                                                onChange={(e) => handlePropertyChange('Hardware Binning X', e.target.value)}
                                                disabled={!isPropertyAvailable('Hardware Binning X')}
                                            >
                                                <MenuItem value={1}>1x</MenuItem>
                                                <MenuItem value={2}>2x</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Hardware Binning Y</InputLabel>
                                            <Select
                                                value={cameraSettings['Hardware Binning Y'] || 1}
                                                label="Hardware Binning Y"
                                                onChange={(e) => handlePropertyChange('Hardware Binning Y', e.target.value)}
                                                disabled={!isPropertyAvailable('Hardware Binning Y')}
                                            >
                                                <MenuItem value={1}>1x</MenuItem>
                                                <MenuItem value={2}>2x</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    {/* Hardware ROI */}
                                    <Grid item xs={3}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="ROI Offset X"
                                            type="number"
                                            value={cameraSettings['Hardware ROI - Offset X'] || 0}
                                            onChange={(e) => handlePropertyChange('Hardware ROI - Offset X', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Hardware ROI - Offset X')}
                                        />
                                    </Grid>

                                    <Grid item xs={3}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="ROI Offset Y"
                                            type="number"
                                            value={cameraSettings['Hardware ROI - Offset Y'] || 0}
                                            onChange={(e) => handlePropertyChange('Hardware ROI - Offset Y', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Hardware ROI - Offset Y')}
                                        />
                                    </Grid>

                                    <Grid item xs={3}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="ROI Size X"
                                            type="number"
                                            value={cameraSettings['Hardware ROI - Size X'] || 4096}
                                            onChange={(e) => handlePropertyChange('Hardware ROI - Size X', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Hardware ROI - Size X')}
                                        />
                                    </Grid>

                                    <Grid item xs={3}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="ROI Size Y"
                                            type="number"
                                            value={cameraSettings['Hardware ROI - Size Y'] || 4096}
                                            onChange={(e) => handlePropertyChange('Hardware ROI - Size Y', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Hardware ROI - Size Y')}
                                        />
                                    </Grid>

                                    {/* Readout Settings */}
                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Readout Shutter</InputLabel>
                                            <Select
                                                value={cameraSettings['Readout - Shutter'] || 'Rolling'}
                                                label="Readout Shutter"
                                                onChange={(e) => handlePropertyChange('Readout - Shutter', e.target.value)}
                                                disabled={!isPropertyAvailable('Readout - Shutter')}
                                            >
                                                <MenuItem value="Global">Global</MenuItem>
                                                <MenuItem value="Rolling">Rolling</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Hardware HDR</InputLabel>
                                            <Select
                                                value={cameraSettings['Readout - Hardware HDR'] || 'Off'}
                                                label="Hardware HDR"
                                                onChange={(e) => handlePropertyChange('Readout - Hardware HDR', e.target.value)}
                                                disabled={!isPropertyAvailable('Readout - Hardware HDR')}
                                            >
                                                <MenuItem value="On">On</MenuItem>
                                                <MenuItem value="Off">Off</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                </Grid>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>

                    {/* Timing & Exposure Settings */}
                    <Accordion expanded={timingExpanded} onChange={(e, isExpanded) => setTimingExpanded(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <TimerIcon />
                                Timing & Exposure
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Frames Per Second"
                                            type="number"
                                            value={cameraSettings['Frames Per Second'] || 40}
                                            onChange={(e) => handlePropertyChange('Frames Per Second', parseFloat(e.target.value))}
                                            disabled={!isPropertyAvailable('Frames Per Second')}
                                            inputProps={{ min: 0.06, step: 0.01 }}
                                            helperText="Min: 0.06 fps"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Frame Time (ns)"
                                            type="number"
                                            value={cameraSettings['Frame Time (nanoseconds)'] || 25000000}
                                            disabled // Read-only, linked to FPS
                                            helperText="Calculated from FPS"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Exposure Time (s)"
                                            type="number"
                                            value={cameraSettings['Exposure Time (seconds)'] || 1.0}
                                            onChange={(e) => handlePropertyChange('Exposure Time (seconds)', parseFloat(e.target.value))}
                                            disabled={!isPropertyAvailable('Exposure Time (seconds)')}
                                            inputProps={{ min: 0.001, max: 3600, step: 0.001 }}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Frame Count"
                                            type="number"
                                            value={cameraSettings['Frame Count'] || 1}
                                            onChange={(e) => handlePropertyChange('Frame Count', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Frame Count')}
                                            inputProps={{ min: 1, max: 1000000000 }}
                                        />
                                    </Grid>
                                </Grid>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>

                    {/* Image Processing Settings */}
                    <Accordion expanded={processingExpanded} onChange={(e, isExpanded) => setProcessingExpanded(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PsychologyIcon />
                                Image Processing
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Processing Mode</InputLabel>
                                            <Select
                                                value={cameraSettings['Image Processing - Mode'] || 'Integrating'}
                                                label="Processing Mode"
                                                onChange={(e) => handlePropertyChange('Image Processing - Mode', e.target.value)}
                                                disabled={!isPropertyAvailable('Image Processing - Mode')}
                                            >
                                                <MenuItem value="Integrating">Integrating</MenuItem>
                                                <MenuItem value="Counting">Counting</MenuItem>
                                                <MenuItem value="HDR Counting">HDR Counting</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Flatfield Correction</InputLabel>
                                            <Select
                                                value={cameraSettings['Image Processing - Flatfield Correction'] || 'Dark and Gain'}
                                                label="Flatfield Correction"
                                                onChange={(e) => handlePropertyChange('Image Processing - Flatfield Correction', e.target.value)}
                                                disabled={!isPropertyAvailable('Image Processing - Flatfield Correction')}
                                            >
                                                <MenuItem value="None">None</MenuItem>
                                                <MenuItem value="Dark">Dark</MenuItem>
                                                <MenuItem value="Dark and Gain">Dark and Gain</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    {/* Software Binning */}
                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Software Binning X</InputLabel>
                                            <Select
                                                value={cameraSettings['Binning X'] || 1}
                                                label="Software Binning X"
                                                onChange={(e) => handlePropertyChange('Binning X', e.target.value)}
                                                disabled={!isPropertyAvailable('Binning X')}
                                            >
                                                {[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024].map(bin => (
                                                    <MenuItem key={bin} value={bin}>{bin}x</MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Software Binning Y</InputLabel>
                                            <Select
                                                value={cameraSettings['Binning Y'] || 1}
                                                label="Software Binning Y"
                                                onChange={(e) => handlePropertyChange('Binning Y', e.target.value)}
                                                disabled={!isPropertyAvailable('Binning Y')}
                                            >
                                                {[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024].map(bin => (
                                                    <MenuItem key={bin} value={bin}>{bin}x</MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Binning Method</InputLabel>
                                            <Select
                                                value={cameraSettings['Binning Method'] || 'Average'}
                                                label="Binning Method"
                                                onChange={(e) => handlePropertyChange('Binning Method', e.target.value)}
                                                disabled={!isPropertyAvailable('Binning Method')}
                                            >
                                                <MenuItem value="Average">Average</MenuItem>
                                                <MenuItem value="Fourier Crop">Fourier Crop</MenuItem>
                                                <MenuItem value="Sample">Sample</MenuItem>
                                                <MenuItem value="Sum">Sum</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                </Grid>

                                <Divider />

                                {/* Gain Settings */}
                                <Grid container spacing={2}>
                                    <Grid item xs={6}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={cameraSettings['Image Processing - Apply Gain on Movie'] === 'On'}
                                                    onChange={(e) => handlePropertyChange('Image Processing - Apply Gain on Movie', e.target.checked ? 'On' : 'Off')}
                                                    disabled={!isPropertyAvailable('Image Processing - Apply Gain on Movie')}
                                                />
                                            }
                                            label="Apply Gain on Movie"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={cameraSettings['Image Processing - Apply Gain on Final'] === 'On'}
                                                    onChange={(e) => handlePropertyChange('Image Processing - Apply Gain on Final', e.target.checked ? 'On' : 'Off')}
                                                    disabled={!isPropertyAvailable('Image Processing - Apply Gain on Final')}
                                                />
                                            }
                                            label="Apply Gain on Final"
                                        />
                                    </Grid>
                                </Grid>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>

                    {/* Autosave Settings */}
                    <Accordion expanded={autosaveExpanded} onChange={(e, isExpanded) => setAutosaveExpanded(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <StorageIcon />
                                Autosave Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={3}>
                                    <Grid item xs={8}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Autosave Directory"
                                            value={cameraSettings['Autosave Directory'] || ''}
                                            onChange={(e) => handlePropertyChange('Autosave Directory', e.target.value)}
                                            disabled={!isPropertyAvailable('Autosave Directory')}
                                            placeholder="Enter save directory path"
                                        />
                                    </Grid>

                                    <Grid item xs={4}>
                                        <Button
                                            variant="outlined"
                                            startIcon={<FolderIcon />}
                                            fullWidth
                                            sx={{ height: '40px' }}
                                        >
                                            Browse
                                        </Button>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Filename Suffix"
                                            value={cameraSettings['Autosave Filename Suffix'] || ''}
                                            onChange={(e) => handlePropertyChange('Autosave Filename Suffix', e.target.value)}
                                            disabled={!isPropertyAvailable('Autosave Filename Suffix')}
                                            placeholder="Optional filename suffix"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>File Format</InputLabel>
                                            <Select
                                                value={cameraSettings['Autosave File Format'] || 'Auto'}
                                                label="File Format"
                                                onChange={(e) => handlePropertyChange('Autosave File Format', e.target.value)}
                                                disabled={!isPropertyAvailable('Autosave File Format')}
                                            >
                                                <MenuItem value="Auto">Auto</MenuItem>
                                                <MenuItem value="MRC">MRC</MenuItem>
                                                <MenuItem value="TIFF">TIFF</MenuItem>
                                                <MenuItem value="TIFF LZW">TIFF LZW</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <FormControl fullWidth size="small">
                                            <InputLabel>Movie File Format</InputLabel>
                                            <Select
                                                value={cameraSettings['Autosave Movie File Format'] || 'Auto'}
                                                label="Movie File Format"
                                                onChange={(e) => handlePropertyChange('Autosave Movie File Format', e.target.value)}
                                                disabled={!isPropertyAvailable('Autosave Movie File Format')}
                                            >
                                                <MenuItem value="Auto">Auto</MenuItem>
                                                <MenuItem value="MRC">MRC</MenuItem>
                                                <MenuItem value="TIFF">TIFF</MenuItem>
                                                <MenuItem value="TIFF LZW">TIFF LZW</MenuItem>
                                                <MenuItem value="DE5">DE5</MenuItem>
                                                <MenuItem value="HSPY">HSPY</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Movie Sum Count"
                                            type="number"
                                            value={cameraSettings['Autosave Movie Sum Count'] || 1}
                                            onChange={(e) => handlePropertyChange('Autosave Movie Sum Count', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Autosave Movie Sum Count')}
                                            inputProps={{ min: 1, max: 1000 }}
                                        />
                                    </Grid>
                                </Grid>

                                <Stack direction="row" spacing={2}>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={cameraSettings['Autosave Final Image'] === 'On'}
                                                onChange={(e) => handlePropertyChange('Autosave Final Image', e.target.checked ? 'On' : 'Off')}
                                                disabled={!isPropertyAvailable('Autosave Final Image')}
                                            />
                                        }
                                        label="Autosave Final Image"
                                    />

                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={cameraSettings['Autosave Movie'] === 'On'}
                                                onChange={(e) => handlePropertyChange('Autosave Movie', e.target.checked ? 'On' : 'Off')}
                                                disabled={!isPropertyAvailable('Autosave Movie')}
                                            />
                                        }
                                        label="Autosave Movie"
                                    />
                                </Stack>
                            </Stack>
                        </AccordionDetails>
                    </Accordion>

                    {/* Advanced Settings */}
                    <Accordion expanded={advancedExpanded} onChange={(e, isExpanded) => setAdvancedExpanded(isExpanded)}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <TuneIcon />
                                Advanced Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={3}>
                                <Grid container spacing={3}>
                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Crop Offset X"
                                            type="number"
                                            value={cameraSettings['Crop Offset X'] || 0}
                                            onChange={(e) => handlePropertyChange('Crop Offset X', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Crop Offset X')}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Crop Offset Y"
                                            type="number"
                                            value={cameraSettings['Crop Offset Y'] || 0}
                                            onChange={(e) => handlePropertyChange('Crop Offset Y', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Crop Offset Y')}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Crop Size X"
                                            type="number"
                                            value={cameraSettings['Crop Size X'] || 4096}
                                            onChange={(e) => handlePropertyChange('Crop Size X', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Crop Size X')}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            size="small"
                                            label="Crop Size Y"
                                            type="number"
                                            value={cameraSettings['Crop Size Y'] || 4096}
                                            onChange={(e) => handlePropertyChange('Crop Size Y', parseInt(e.target.value))}
                                            disabled={!isPropertyAvailable('Crop Size Y')}
                                        />
                                    </Grid>
                                </Grid>

                                <Divider />

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
                <Button variant="outlined" startIcon={<RefreshIcon />}>
                    Reset to Defaults
                </Button>
                <Button variant="contained" startIcon={<SaveIcon />}>
                    Apply Settings
                </Button>
            </DialogActions>
        </Dialog>
    );
};