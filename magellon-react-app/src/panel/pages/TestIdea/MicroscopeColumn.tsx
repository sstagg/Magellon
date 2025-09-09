import React, {useEffect, useState} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {
    Box,
    Button,
    Container,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    TextField,
    Typography,
    useTheme,
    Chip,
    alpha
} from '@mui/material';
import {MICROSCOPE_CONFIGS, MicroscopeComponent, MicroscopeConfig} from "./MicroscopeComponentConfig.ts";
import MicroscopeComponentRenderer from './MicroscopeComponentRenderer';

// Property Editor Component
const PropertyEditor: React.FC<{
    component: MicroscopeComponent;
    onUpdate: (updatedComponent: MicroscopeComponent) => void;
}> = ({ component, onUpdate }) => {
    const theme = useTheme();
    const [editedComponent, setEditedComponent] = useState<MicroscopeComponent>(component);

    useEffect(() => {
        setEditedComponent(component);
    }, [component]);

    const handlePropertyChange = (path: string, value: any) => {
        const updated = { ...editedComponent };

        if (path.startsWith('specifications.')) {
            const specKey = path.replace('specifications.', '');
            if (!updated.specifications) updated.specifications = {};
            updated.specifications[specKey] = value;
        } else {
            (updated as any)[path] = value;
        }

        setEditedComponent(updated);
        onUpdate(updated);
    };

    const addSpecification = () => {
        const key = prompt('Enter specification key:');
        const value = prompt('Enter specification value:');
        if (key && value) {
            handlePropertyChange(`specifications.${key}`, value);
        }
    };

    const removeSpecification = (key: string) => {
        const updated = { ...editedComponent };
        if (updated.specifications) {
            delete updated.specifications[key];
        }
        setEditedComponent(updated);
        onUpdate(updated);
    };

    return (
        <Paper elevation={1} sx={{ p: 3, height: 'fit-content' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Properties
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    {component.id}
                </Typography>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Basic Properties */}
                <Grid container spacing={2}>
                    <Grid item xs={6}>
                        <TextField
                            label="Name"
                            size="small"
                            fullWidth
                            value={editedComponent.name}
                            onChange={(e) => handlePropertyChange('name', e.target.value)}
                        />
                    </Grid>
                    <Grid item xs={6}>
                        <FormControl size="small" fullWidth>
                            <InputLabel>Type</InputLabel>
                            <Select
                                value={editedComponent.type}
                                label="Type"
                                onChange={(e) => handlePropertyChange('type', e.target.value)}
                            >
                                <MenuItem value="source">Source</MenuItem>
                                <MenuItem value="lens">Lens</MenuItem>
                                <MenuItem value="aperture">Aperture</MenuItem>
                                <MenuItem value="detector">Detector</MenuItem>
                                <MenuItem value="camera">Camera</MenuItem>
                                <MenuItem value="sample">Sample</MenuItem>
                                <MenuItem value="electrode">Electrode</MenuItem>
                                <MenuItem value="coils">Coils</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid item xs={6}>
                        <TextField
                            label="Width"
                            type="number"
                            size="small"
                            fullWidth
                            value={editedComponent.width}
                            onChange={(e) => handlePropertyChange('width', parseInt(e.target.value))}
                        />
                    </Grid>
                    <Grid item xs={6}>
                        <TextField
                            label="Height"
                            type="number"
                            size="small"
                            fullWidth
                            value={editedComponent.height}
                            onChange={(e) => handlePropertyChange('height', parseInt(e.target.value))}
                        />
                    </Grid>
                    <Grid item xs={6}>
                        <Box>
                            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                                Color
                            </Typography>
                            <input
                                type="color"
                                value={editedComponent.baseColor}
                                onChange={(e) => handlePropertyChange('baseColor', e.target.value)}
                                style={{
                                    width: '100%',
                                    height: 32,
                                    border: `1px solid ${theme.palette.divider}`,
                                    borderRadius: theme.shape.borderRadius,
                                    cursor: 'pointer'
                                }}
                            />
                        </Box>
                    </Grid>
                    <Grid item xs={6}>
                        <FormControl size="small" fullWidth>
                            <InputLabel>Shape</InputLabel>
                            <Select
                                value={editedComponent.shape}
                                label="Shape"
                                onChange={(e) => handlePropertyChange('shape', e.target.value)}
                            >
                                <MenuItem value="cylinder">Cylinder</MenuItem>
                                <MenuItem value="lens">Lens</MenuItem>
                                <MenuItem value="aperture">Aperture</MenuItem>
                                <MenuItem value="detector">Detector</MenuItem>
                                <MenuItem value="source">Source</MenuItem>
                                <MenuItem value="camera">Camera</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                </Grid>

                <TextField
                    label="Description"
                    multiline
                    rows={2}
                    size="small"
                    fullWidth
                    value={editedComponent.description || ''}
                    onChange={(e) => handlePropertyChange('description', e.target.value)}
                />

                {/* Specifications */}
                <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                            Specifications
                        </Typography>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={addSpecification}
                            sx={{ minWidth: 'auto', px: 1 }}
                        >
                            + Add
                        </Button>
                    </Box>
                    <Box sx={{ maxHeight: 120, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {editedComponent.specifications && Object.entries(editedComponent.specifications).map(([key, value]) => (
                            <Box key={key} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                <TextField
                                    size="small"
                                    value={key}
                                    placeholder="Key"
                                    onChange={(e) => {
                                        const newSpecs = { ...editedComponent.specifications };
                                        delete newSpecs[key];
                                        newSpecs[e.target.value] = value;
                                        handlePropertyChange('specifications', newSpecs);
                                    }}
                                    sx={{ flex: 1 }}
                                />
                                <TextField
                                    size="small"
                                    value={String(value)}
                                    placeholder="Value"
                                    onChange={(e) => handlePropertyChange(`specifications.${key}`, e.target.value)}
                                    sx={{ flex: 1 }}
                                />
                                <Button
                                    size="small"
                                    color="error"
                                    onClick={() => removeSpecification(key)}
                                    sx={{ minWidth: 'auto', px: 1 }}
                                >
                                    ×
                                </Button>
                            </Box>
                        ))}
                    </Box>
                </Box>
            </Box>
        </Paper>
    );
};

// Main microscope column component
const MicroscopeColumn: React.FC = () => {
    const theme = useTheme();
    const [selectedConfig, setSelectedConfig] = useState<string>('cryo-em-setup');
    const [currentConfig, setCurrentConfig] = useState<MicroscopeConfig>(MICROSCOPE_CONFIGS[selectedConfig]);
    const [hoveredId, setHoveredId] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    useEffect(() => {
        setCurrentConfig(MICROSCOPE_CONFIGS[selectedConfig]);
        setSelectedId(null);
        setHoveredId(null);
    }, [selectedConfig]);

    const selectedComponent = selectedId ? currentConfig.components.find(c => c.id === selectedId) : null;

    const handleComponentUpdate = (updatedComponent: MicroscopeComponent) => {
        const updatedComponents = currentConfig.components.map(c =>
            c.id === updatedComponent.id ? updatedComponent : c
        );
        setCurrentConfig({
            ...currentConfig,
            components: updatedComponents
        });
    };

    const loadConfigFromJSON = (jsonString: string) => {
        try {
            const config: MicroscopeConfig = JSON.parse(jsonString);
            setCurrentConfig(config);
            setSelectedId(null);
            setHoveredId(null);
        } catch (error) {
            console.error('Invalid JSON configuration:', error);
        }
    };

    return (
        <Container maxWidth="xl" sx={{ py: 3 }}>
            <Typography
                variant="h4"
                component="h1"
                sx={{
                    fontWeight: 'bold',
                    mb: 3,
                    textAlign: 'center',
                    background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text'
                }}
            >
                {currentConfig.name}
            </Typography>

            <Grid container spacing={3} sx={{ height: 'calc(100vh - 200px)' }}>
                {/* Left Panel - Configuration */}
                <Grid item xs={12} lg={3} sx={{ height: '100%' }}>
                    <Box sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        height: '100%',
                        overflowY: 'auto'
                    }}>
                        {/* Configuration Selector */}
                        <Paper elevation={1} sx={{ p: 3, mb: 2 }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                                Microscope Configuration
                            </Typography>

                            <Box sx={{ mb: 2 }}>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Select Configuration</InputLabel>
                                    <Select
                                        value={selectedConfig}
                                        onChange={(e) => setSelectedConfig(e.target.value)}
                                        label="Select Configuration"
                                    >
                                        <MenuItem value="cryo-em-setup">Titan Krios with Apollo</MenuItem>
                                        <MenuItem value="stem-setup">JEOL ARM300F STEM</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box>

                            {/* Microscope Info */}
                            <Paper
                                variant="outlined"
                                sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}
                            >
                                <Typography variant="body2" sx={{ mb: 0.5 }}>
                                    <strong>Voltage:</strong> {currentConfig.voltage}
                                </Typography>
                                <Typography variant="body2" sx={{ mb: 0.5 }}>
                                    <strong>Manufacturer:</strong> {currentConfig.manufacturer}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Components:</strong> {currentConfig.components.length}
                                </Typography>
                            </Paper>

                            {/* JSON Configuration Area */}
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Load JSON Configuration:
                                </Typography>
                                <TextField
                                    multiline
                                    rows={4}
                                    fullWidth
                                    size="small"
                                    placeholder="Paste JSON configuration here..."
                                    onChange={(e) => {
                                        if (e.target.value.trim()) {
                                            loadConfigFromJSON(e.target.value);
                                        }
                                    }}
                                />
                            </Box>

                            {/* Export Configuration */}
                            <Button
                                fullWidth
                                variant="contained"
                                onClick={() => {
                                    const configJson = JSON.stringify(currentConfig, null, 2);
                                    navigator.clipboard.writeText(configJson);
                                    alert('Configuration copied to clipboard!');
                                }}
                            >
                                Copy Configuration JSON
                            </Button>
                        </Paper>

                        {/* Component List */}
                        <Paper elevation={1} sx={{ p: 2, mb: 2, flexGrow: 1 }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                                Components
                            </Typography>
                            <Box sx={{ height: 'calc(100% - 40px)', overflowY: 'auto' }}>
                                {currentConfig.components.map((component) => (
                                    <Paper
                                        key={component.id}
                                        variant="outlined"
                                        onClick={() => setSelectedId(selectedId === component.id ? null : component.id)}
                                        sx={{
                                            p: 1.5,
                                            mb: 1,
                                            cursor: 'pointer',
                                            bgcolor: selectedId === component.id ? 'primary.main' : 'background.paper',
                                            color: selectedId === component.id ? 'primary.contrastText' : 'text.primary',
                                            border: selectedId === component.id ? `1px solid ${theme.palette.primary.main}` : undefined,
                                            transition: theme.transitions.create(['background-color', 'color'], {
                                                duration: theme.transitions.duration.shorter,
                                            }),
                                            '&:hover': {
                                                bgcolor: selectedId === component.id ? 'primary.dark' : 'action.hover'
                                            }
                                        }}
                                    >
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                                {component.name}
                                            </Typography>
                                            <Typography variant="caption" sx={{
                                                color: selectedId === component.id ? 'primary.contrastText' : 'text.secondary'
                                            }}>
                                                {component.type}
                                            </Typography>
                                        </Box>
                                        <Typography variant="caption" sx={{
                                            color: selectedId === component.id ? 'primary.contrastText' : 'text.secondary',
                                            mt: 0.5,
                                            display: 'block'
                                        }}>
                                            {component.description}
                                        </Typography>
                                    </Paper>
                                ))}
                            </Box>
                        </Paper>
                    </Box>
                </Grid>

                {/* Middle Panel - Microscope Column Visualization */}
                <Grid item xs={12} lg={6} sx={{ height: '100%' }}>
                    <Paper
                        elevation={1}
                        sx={{
                            height: '100%',
                            p: 3,
                            position: 'relative',
                            bgcolor: 'background.paper'
                        }}
                    >
                        {/* Vacuum chamber background */}
                        <Box
                            sx={{
                                position: 'absolute',
                                inset: 12,
                                background: `linear-gradient(to bottom, ${theme.palette.primary.main}08, ${theme.palette.secondary.main}08, ${theme.palette.primary.main}08)`,
                                borderRadius: 2,
                                border: `1px solid ${theme.palette.divider}`,
                            }}
                        />

                        <Box
                            sx={{
                                position: 'relative',
                                zIndex: 10,
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                py: 3,
                                height: '100%',
                                overflowY: 'auto'
                            }}
                        >
                            <AnimatePresence>
                                {currentConfig.components.map((component, index) => (
                                    <MicroscopeComponentRenderer
                                        key={component.id}
                                        component={component}
                                        isHovered={hoveredId === component.id}
                                        isSelected={selectedId === component.id}
                                        onHover={() => setHoveredId(component.id)}
                                        onLeave={() => setHoveredId(null)}
                                        onSelect={() => setSelectedId(selectedId === component.id ? null : component.id)}
                                        index={index}
                                    />
                                ))}
                            </AnimatePresence>
                        </Box>
                    </Paper>
                </Grid>

                {/* Right Panel - Properties */}
                <Grid item xs={12} lg={3} sx={{ height: '100%', minHeight: 0 }}>
                    <Box sx={{
                        height: '100%',
                        overflowY: 'auto',
                        minHeight: 0
                    }}>
                        {/* Property Editor */}
                        {selectedComponent ? (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ duration: 0.2 }}
                            >
                                <PropertyEditor
                                    component={selectedComponent}
                                    onUpdate={handleComponentUpdate}
                                />
                            </motion.div>
                        ) : (
                            <Paper elevation={1} sx={{ p: 3, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Typography variant="body1" color="text.secondary" textAlign="center">
                                    Select a component from the list to view and edit its properties
                                </Typography>
                            </Paper>
                        )}
                    </Box>
                </Grid>
            </Grid>
        </Container>
    );
};

export default MicroscopeColumn;