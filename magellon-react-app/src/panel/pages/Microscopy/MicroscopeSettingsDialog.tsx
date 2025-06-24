// Microscope Settings Dialog Component
import {useState} from "react";
import {Box, Dialog, DialogTitle, Typography} from "@mui/material";
import {Microscope} from "lucide-react";

export const MicroscopeSettingsDialog = ({ open, onClose, microscopeSettings, updateMicroscopeSettings, opticalSettings, updateOpticalSettings, advancedSettings, updateAdvancedSettings }) => {
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