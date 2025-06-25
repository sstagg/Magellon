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
    Stack,
    Chip,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    alpha,
    useTheme
} from '@mui/material';
import {
    Save as SaveIcon,
    Camera as CameraIcon,
    Memory as MemoryIcon,
    ZoomIn as ZoomInIcon,
    ExpandMore as ExpandMoreIcon
} from '@mui/icons-material';
import {
    BookOpen,
    Layers
} from 'lucide-react';

interface PresetSettings {
    optical: {
        magnification: number;
        defocus: number;
        spotSize: number;
        intensity: number;
    };
    acquisition: {
        exposure: number;
        binning: number;
        mode: string;
        electronCounting: boolean;
        saveFrames: boolean;
    };
    camera: {
        frameTime: number;
        processingMode: string;
        flatfieldCorrection: string;
        binningMethod: string;
    };
}

interface Preset {
    id: number;
    name: string;
    category: string;
    description: string;
    mag: number;
    defocus: number;
    spot: number;
    exposure: number;
    binning: number;
    settings: PresetSettings;
}

interface PresetEditorProps {
    open: boolean;
    onClose: () => void;
    onSave: (preset: Preset) => void;
}

const PresetEditor: React.FC<PresetEditorProps> = ({ open, onClose, onSave }) => {
    const theme = useTheme();
    const [selectedTemplate, setSelectedTemplate] = useState('');
    const [presetName, setPresetName] = useState('');
    const [presetCategory, setPresetCategory] = useState('Custom');
    const [description, setDescription] = useState('');

    const [opticalSettings, setOpticalSettings] = useState({
        magnification: 50000,
        defocus: -2.0,
        spotSize: 5,
        intensity: 1e-6
    });

    const [acquisitionSettings, setAcquisitionSettings] = useState({
        exposure: 1000,
        binning: 1,
        mode: 'Integrating',
        electronCounting: false,
        saveFrames: true
    });

    const [cameraSettings, setCameraSettings] = useState({
        frameTime: 25000000,
        processingMode: 'Integrating',
        flatfieldCorrection: 'Dark and Gain',
        binningMethod: 'Average'
    });

    const templates = [
        {
            name: 'High Resolution Template',
            category: 'Imaging',
            description: 'For atomic resolution work',
            settings: {
                optical: { magnification: 105000, defocus: -1.5, spotSize: 5, intensity: 8e-7 },
                acquisition: { exposure: 500, binning: 1, mode: 'Integrating', electronCounting: false, saveFrames: true },
                camera: { frameTime: 25000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        {
            name: 'Cryo-EM Template',
            category: 'Cryo-EM',
            description: 'Low dose cryo conditions',
            settings: {
                optical: { magnification: 81000, defocus: -2.0, spotSize: 6, intensity: 2e-7 },
                acquisition: { exposure: 2000, binning: 1, mode: 'Counting', electronCounting: true, saveFrames: true },
                camera: { frameTime: 40000000, processingMode: 'Counting', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        {
            name: 'Tomography Template',
            category: 'Tomography',
            description: 'Optimized for tilt series',
            settings: {
                optical: { magnification: 25000, defocus: -8.0, spotSize: 7, intensity: 5e-7 },
                acquisition: { exposure: 1500, binning: 2, mode: 'Integrating', electronCounting: false, saveFrames: true },
                camera: { frameTime: 30000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark and Gain', binningMethod: 'Average' }
            }
        },
        {
            name: 'Screening Template',
            category: 'General',
            description: 'Fast grid screening',
            settings: {
                optical: { magnification: 10000, defocus: -5.0, spotSize: 8, intensity: 1e-6 },
                acquisition: { exposure: 800, binning: 4, mode: 'Integrating', electronCounting: false, saveFrames: false },
                camera: { frameTime: 20000000, processingMode: 'Integrating', flatfieldCorrection: 'Dark', binningMethod: 'Average' }
            }
        }
    ];

    const applyTemplate = (template: typeof templates[0]) => {
        setOpticalSettings(template.settings.optical);
        setAcquisitionSettings(template.settings.acquisition);
        setCameraSettings(template.settings.camera);
        setPresetCategory(template.category);
        setDescription(template.description);
    };

    const handleSave = () => {
        const newPreset: Preset = {
            id: Date.now(),
            name: presetName,
            category: presetCategory,
            description,
            mag: opticalSettings.magnification,
            defocus: opticalSettings.defocus,
            spot: opticalSettings.spotSize,
            exposure: acquisitionSettings.exposure,
            binning: acquisitionSettings.binning,
            settings: {
                optical: opticalSettings,
                acquisition: acquisitionSettings,
                camera: cameraSettings
            }
        };
        onSave(newPreset);
        onClose();

        // Reset form
        setPresetName('');
        setSelectedTemplate('');
        setDescription('');
        setPresetCategory('Custom');
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={2}>
                    <BookOpen size={24} />
                    <Typography variant="h5" fontWeight="600">
                        Preset Editor
                    </Typography>
                </Box>
            </DialogTitle>

            <DialogContent>
                <Stack spacing={3} sx={{ mt: 1 }}>
                    {/* Template Selection */}
                    <Paper elevation={1} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Layers size={20} />
                            Select Template
                        </Typography>

                        <Grid container spacing={2}>
                            {templates.map((template, index) => (
                                <Grid item xs={12} sm={6} md={3} key={index}>
                                    <Paper
                                        elevation={selectedTemplate === template.name ? 3 : 1}
                                        sx={{
                                            p: 2,
                                            cursor: 'pointer',
                                            borderRadius: 2,
                                            border: selectedTemplate === template.name ? 2 : 1,
                                            borderColor: selectedTemplate === template.name ? 'primary.main' : 'divider',
                                            background: selectedTemplate === template.name
                                                ? `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.1)} 0%, ${alpha(theme.palette.primary.main, 0.05)} 100%)`
                                                : 'background.paper',
                                            '&:hover': {
                                                transform: 'translateY(-2px)',
                                                boxShadow: 3
                                            },
                                            transition: 'all 0.2s ease'
                                        }}
                                        onClick={() => {
                                            setSelectedTemplate(template.name);
                                            applyTemplate(template);
                                        }}
                                    >
                                        <Typography variant="subtitle1" fontWeight="600" gutterBottom>
                                            {template.name}
                                        </Typography>
                                        <Chip
                                            label={template.category}
                                            size="small"
                                            color="primary"
                                            variant="outlined"
                                            sx={{ mb: 1 }}
                                        />
                                        <Typography variant="body2" color="text.secondary">
                                            {template.description}
                                        </Typography>
                                    </Paper>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>

                    {/* Basic Information */}
                    <Paper elevation={1} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>Preset Information</Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    label="Preset Name"
                                    value={presetName}
                                    onChange={(e) => setPresetName(e.target.value)}
                                    placeholder="Enter preset name"
                                />
                            </Grid>
                            <Grid item xs={6}>
                                <FormControl fullWidth>
                                    <InputLabel>Category</InputLabel>
                                    <Select
                                        value={presetCategory}
                                        label="Category"
                                        onChange={(e) => setPresetCategory(e.target.value)}
                                    >
                                        <MenuItem value="Custom">Custom</MenuItem>
                                        <MenuItem value="Imaging">Imaging</MenuItem>
                                        <MenuItem value="Cryo-EM">Cryo-EM</MenuItem>
                                        <MenuItem value="Tomography">Tomography</MenuItem>
                                        <MenuItem value="Spectroscopy">Spectroscopy</MenuItem>
                                        <MenuItem value="General">General</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={12}>
                                <TextField
                                    fullWidth
                                    label="Description"
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    multiline
                                    rows={2}
                                    placeholder="Describe the purpose and use case for this preset"
                                />
                            </Grid>
                        </Grid>
                    </Paper>

                    {/* Optical Settings */}
                    <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ZoomInIcon />
                                Optical Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Magnification</InputLabel>
                                        <Select
                                            value={opticalSettings.magnification}
                                            label="Magnification"
                                            onChange={(e) => setOpticalSettings(prev => ({ ...prev, magnification: e.target.value as number }))}
                                        >
                                            <MenuItem value={2000}>2,000x</MenuItem>
                                            <MenuItem value={5000}>5,000x</MenuItem>
                                            <MenuItem value={10000}>10,000x</MenuItem>
                                            <MenuItem value={25000}>25,000x</MenuItem>
                                            <MenuItem value={50000}>50,000x</MenuItem>
                                            <MenuItem value={81000}>81,000x</MenuItem>
                                            <MenuItem value={105000}>105,000x</MenuItem>
                                            <MenuItem value={165000}>165,000x</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <TextField
                                        fullWidth
                                        label="Defocus (μm)"
                                        type="number"
                                        value={opticalSettings.defocus}
                                        onChange={(e) => setOpticalSettings(prev => ({ ...prev, defocus: parseFloat(e.target.value) }))}
                                    />
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Spot Size</InputLabel>
                                        <Select
                                            value={opticalSettings.spotSize}
                                            label="Spot Size"
                                            onChange={(e) => setOpticalSettings(prev => ({ ...prev, spotSize: e.target.value as number }))}
                                        >
                                            {[1,2,3,4,5,6,7,8,9,10,11].map(size => (
                                                <MenuItem key={size} value={size}>{size}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <TextField
                                        fullWidth
                                        label="Intensity"
                                        value={opticalSettings.intensity.toExponential(2)}
                                        onChange={(e) => {
                                            const val = parseFloat(e.target.value);
                                            if (!isNaN(val)) {
                                                setOpticalSettings(prev => ({ ...prev, intensity: val }));
                                            }
                                        }}
                                    />
                                </Grid>
                            </Grid>
                        </AccordionDetails>
                    </Accordion>

                    {/* Acquisition Settings */}
                    <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <CameraIcon />
                                Acquisition Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <TextField
                                        fullWidth
                                        label="Exposure (ms)"
                                        type="number"
                                        value={acquisitionSettings.exposure}
                                        onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, exposure: parseInt(e.target.value) }))}
                                    />
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Binning</InputLabel>
                                        <Select
                                            value={acquisitionSettings.binning}
                                            label="Binning"
                                            onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, binning: e.target.value as number }))}
                                        >
                                            <MenuItem value={1}>1x1</MenuItem>
                                            <MenuItem value={2}>2x2</MenuItem>
                                            <MenuItem value={4}>4x4</MenuItem>
                                            <MenuItem value={8}>8x8</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Mode</InputLabel>
                                        <Select
                                            value={acquisitionSettings.mode}
                                            label="Mode"
                                            onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, mode: e.target.value }))}
                                        >
                                            <MenuItem value="Integrating">Integrating</MenuItem>
                                            <MenuItem value="Counting">Counting</MenuItem>
                                            <MenuItem value="Super Resolution">Super Resolution</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <Stack direction="row" spacing={2}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={acquisitionSettings.electronCounting}
                                                    onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, electronCounting: e.target.checked }))}
                                                    size="small"
                                                />
                                            }
                                            label="Counting"
                                        />
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={acquisitionSettings.saveFrames}
                                                    onChange={(e) => setAcquisitionSettings(prev => ({ ...prev, saveFrames: e.target.checked }))}
                                                    size="small"
                                                />
                                            }
                                            label="Save Frames"
                                        />
                                    </Stack>
                                </Grid>
                            </Grid>
                        </AccordionDetails>
                    </Accordion>

                    {/* Camera Settings */}
                    <Accordion>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <MemoryIcon />
                                Camera Settings
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <TextField
                                        fullWidth
                                        label="Frame Time (ns)"
                                        type="number"
                                        value={cameraSettings.frameTime}
                                        onChange={(e) => setCameraSettings(prev => ({ ...prev, frameTime: parseInt(e.target.value) }))}
                                    />
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Processing Mode</InputLabel>
                                        <Select
                                            value={cameraSettings.processingMode}
                                            label="Processing Mode"
                                            onChange={(e) => setCameraSettings(prev => ({ ...prev, processingMode: e.target.value }))}
                                        >
                                            <MenuItem value="Integrating">Integrating</MenuItem>
                                            <MenuItem value="Counting">Counting</MenuItem>
                                            <MenuItem value="HDR Counting">HDR Counting</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Flatfield Correction</InputLabel>
                                        <Select
                                            value={cameraSettings.flatfieldCorrection}
                                            label="Flatfield Correction"
                                            onChange={(e) => setCameraSettings(prev => ({ ...prev, flatfieldCorrection: e.target.value }))}
                                        >
                                            <MenuItem value="None">None</MenuItem>
                                            <MenuItem value="Dark">Dark</MenuItem>
                                            <MenuItem value="Dark and Gain">Dark and Gain</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Binning Method</InputLabel>
                                        <Select
                                            value={cameraSettings.binningMethod}
                                            label="Binning Method"
                                            onChange={(e) => setCameraSettings(prev => ({ ...prev, binningMethod: e.target.value }))}
                                        >
                                            <MenuItem value="Average">Average</MenuItem>
                                            <MenuItem value="Fourier Crop">Fourier Crop</MenuItem>
                                            <MenuItem value="Sample">Sample</MenuItem>
                                            <MenuItem value="Sum">Sum</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                            </Grid>
                        </AccordionDetails>
                    </Accordion>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button
                    variant="contained"
                    startIcon={<SaveIcon />}
                    onClick={handleSave}
                    disabled={!presetName}
                >
                    Save Preset
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default PresetEditor;