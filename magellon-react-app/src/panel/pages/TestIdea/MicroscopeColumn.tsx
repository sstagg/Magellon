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
    useTheme
} from '@mui/material';
import {MICROSCOPE_CONFIGS, MicroscopeComponent, MicroscopeConfig} from "./MicroscopeComponentConfig.ts";

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
        <Paper elevation={1} sx={{ p: 3, mt: 2 }}>
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

// Particle component for electron beam
const ElectronParticle: React.FC<{ delay: number }> = ({ delay }) => (
    <motion.div
        className="absolute w-0.5 h-0.5 bg-yellow-300 rounded-full opacity-60"
        initial={{ y: -10, opacity: 0 }}
        animate={{
            y: 15,
            opacity: [0, 0.8, 0.8, 0],
            scale: [0.5, 1, 1, 0.5]
        }}
        transition={{
            duration: 1.2,
            delay,
            repeat: Infinity,
            ease: "linear"
        }}
    />
);

// Compact component renderer with centered labels
const MicroscopeComponentRenderer: React.FC<{
    component: MicroscopeComponent;
    isHovered: boolean;
    isSelected: boolean;
    onHover: () => void;
    onLeave: () => void;
    onSelect: () => void;
    index: number;
}> = ({ component, isHovered, isSelected, onHover, onLeave, onSelect, index }) => {

    const renderShape = () => {
        const baseStyle = {
            background: `linear-gradient(135deg, ${component.baseColor}, ${component.baseColor}dd)`,
        };

        const labelStyle = "absolute inset-0 flex items-center justify-center text-white text-xs font-medium text-center px-1 pointer-events-none select-none";

        switch (component.shape) {
            case 'source':
                return (
                    <div
                        className="relative rounded-t-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 15px ${component.baseColor}60` : `0 0 8px ${component.baseColor}40`
                        }}
                    >
                        <div className="absolute inset-1 bg-gradient-to-br from-white/20 to-transparent rounded-t-full" />
                        <div className={labelStyle}>
                            {component.name}
                        </div>
                        <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-4 h-1 bg-gradient-to-b from-yellow-300 to-yellow-500" />
                    </div>
                );

            case 'lens':
                return (
                    <div className="flex flex-col items-center">
                        <div
                            className="relative rounded-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                            style={{
                                ...baseStyle,
                                width: component.width,
                                height: component.height,
                                boxShadow: isHovered ? `0 0 12px ${component.baseColor}50` : `0 0 6px ${component.baseColor}30`
                            }}
                        >
                            <div className="absolute inset-1 border border-white/10 rounded-full" />
                            <div className="absolute inset-0 bg-gradient-radial from-white/20 via-transparent to-transparent rounded-full" />
                            <div className={labelStyle}>
                                {component.name}
                            </div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="w-2 h-2 border border-white/40 rounded-full" />
                            </div>
                        </div>
                        <div
                            className="w-2 h-2 border-x border-white/20"
                            style={{ background: `linear-gradient(to bottom, ${component.baseColor}, ${component.baseColor}aa)` }}
                        />
                    </div>
                );

            case 'aperture':
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 10px ${component.baseColor}40` : `0 0 5px ${component.baseColor}20`
                        }}
                    >
                        <div className="absolute inset-2 bg-black/50 rounded border border-white/10" />
                        <div className={labelStyle}>
                            {component.name}
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-1.5 h-1.5 border border-white/60 rounded-full bg-black/20" />
                        </div>
                    </div>
                );

            case 'detector':
                return (
                    <div className="flex items-center">
                        <div
                            className="relative rounded-r-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                            style={{
                                ...baseStyle,
                                width: component.width,
                                height: component.height,
                                boxShadow: isHovered ? `0 0 12px ${component.baseColor}50` : `0 0 6px ${component.baseColor}30`
                            }}
                        >
                            <div className="absolute inset-1 bg-gradient-to-l from-white/20 to-transparent rounded-r-full" />
                            <div className={labelStyle}>
                                {component.name}
                            </div>
                            <div className="absolute right-1 top-1/2 transform -translate-y-1/2 w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                            <div className="absolute left-2 top-1/2 transform -translate-y-1/2 w-0.5 h-0.5 bg-red-400 rounded-full" />
                        </div>
                    </div>
                );

            case 'camera':
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 15px ${component.baseColor}60` : `0 0 8px ${component.baseColor}40`
                        }}
                    >
                        <div className="absolute inset-1 bg-gradient-to-br from-white/20 to-transparent rounded" />
                        <div className={labelStyle}>
                            {component.name}
                        </div>
                        {/* Camera sensor grid */}
                        <div className="absolute inset-2 grid grid-cols-4 grid-rows-4 gap-0.5 opacity-30">
                            {[...Array(16)].map((_, i) => (
                                <div
                                    key={i}
                                    className="bg-blue-400/30 rounded-sm"
                                    style={{
                                        animationDelay: `${i * 0.1}s`,
                                        animation: isHovered ? 'pulse 2s infinite' : 'none'
                                    }}
                                />
                            ))}
                        </div>
                        {/* Status indicator */}
                        <div className="absolute top-1 right-1 w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                    </div>
                );

            default:
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 10px ${component.baseColor}40` : `0 0 5px ${component.baseColor}20`
                        }}
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent rounded" />
                        <div className={labelStyle}>
                            {component.name}
                        </div>
                    </div>
                );
        }
    };

    return (
        <motion.div
            className="relative flex flex-col items-center mb-2 cursor-pointer"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={{ scale: 1.02 }}
            onMouseEnter={onHover}
            onMouseLeave={onLeave}
            onClick={onSelect}
        >
            <div className="relative">
                {renderShape()}

                {/* Selection indicator */}
                <AnimatePresence>
                    {isSelected && (
                        <motion.div
                            className="absolute inset-0 border-2 border-blue-400 rounded-full opacity-80"
                            style={{
                                width: component.width + 8,
                                height: component.height + 8,
                                left: -4,
                                top: -4
                            }}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 0.8 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        />
                    )}
                </AnimatePresence>
            </div>

            {/* Electron beam */}
            <div className="relative w-1 h-6 overflow-hidden">
                <div className="absolute left-1/2 transform -translate-x-1/2 w-px h-full bg-gradient-to-b from-yellow-300 via-yellow-400 to-yellow-500 opacity-50" />
                {[...Array(2)].map((_, i) => (
                    <ElectronParticle key={i} delay={i * 0.6} />
                ))}
            </div>
        </motion.div>
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
                <Grid item xs={12} md={4} sx={{ height: '100%' }}>
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
                        <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                                Components
                            </Typography>
                            <Box sx={{ maxHeight: 240, overflowY: 'auto' }}>
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

                        {/* Property Editor */}
                        {selectedComponent && (
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
                        )}
                    </Box>
                </Grid>

                {/* Right Panel - Microscope Column Visualization */}
                <Grid item xs={12} md={8} sx={{ height: '100%' }}>
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
            </Grid>

            {/* Custom CSS for gradient effects */}
            <style>
                {`
          .bg-gradient-radial {
            background: radial-gradient(circle, var(--tw-gradient-stops));
          }
        `}
            </style>
        </Container>
    );
};

export default MicroscopeColumn;