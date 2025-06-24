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
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Chip,
    Alert,
    AlertTitle,
    ToggleButton,
    ToggleButtonGroup,
    Stack
} from '@mui/material';
import {
    PhotoCamera as PhotoCameraIcon,
    ExpandMore as ExpandMoreIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    Save as SaveIcon,
    Refresh as RefreshIcon,
    Settings as SettingsIcon,
    Memory as MemoryIcon, Tune
} from '@mui/icons-material';

interface CameraSettingsDialogProps {
    open: boolean;
    onClose: () => void;
    cameraSettings: any;
    updateCameraSettings: (updates: any) => void;
    acquisitionSettings: any;
    updateAcquisitionSettings: (updates: any) => void;
}

export const CameraSettingsDialog: React.FC<CameraSettingsDialogProps> = ({
                                                                              open,
                                                                              onClose,
                                                                              cameraSettings,
                                                                              updateCameraSettings,
                                                                              acquisitionSettings,
                                                                              updateAcquisitionSettings
                                                                          }) => {
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
                                <Tune />
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