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
        style={{
            position: 'absolute',
            width: 2,
            height: 2,
            backgroundColor: '#FDE047',
            borderRadius: '50%',
            opacity: 0.6
        }}
        initial={{ y: -10, opacity: 0 }}
        animate={{
            y: 20,
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

// Enhanced component renderer with MUI styling
const MicroscopeComponentRenderer: React.FC<{
    component: MicroscopeComponent;
    isHovered: boolean;
    isSelected: boolean;
    onHover: () => void;
    onLeave: () => void;
    onSelect: () => void;
    index: number;
}> = ({ component, isHovered, isSelected, onHover, onLeave, onSelect, index }) => {
    const theme = useTheme();

    const getShapeStyles = () => {
        const baseWidth = 140; // Consistent base width
        const minHeight = 70;  // Increased minimum height for better text readability
        const maxHeight = 90;  // Increased maximum height

        // Calculate height based on component type for visual hierarchy
        const heightMap: Record<string, number> = {
            'source': maxHeight,
            'lens': 78,
            'aperture': minHeight,
            'detector': 80,
            'camera': maxHeight,
            'sample': minHeight + 4,
            'electrode': 76,
            'coils': 76
        };

        return {
            width: baseWidth,
            height: heightMap[component.type] || 78,
            borderRadius: component.shape === 'lens' || component.shape === 'source' ? '50%' : theme.shape.borderRadius
        };
    };

    const renderComponentIcon = () => {
        const iconStyle = {
            width: 24,
            height: 24,
            opacity: 0.7
        };

        switch (component.shape) {
            case 'source':
                return (
                    <Box sx={{ ...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Box
                            sx={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                bgcolor: '#FDE047',
                                boxShadow: `0 0 8px ${alpha('#FDE047', 0.6)}`
                            }}
                        />
                    </Box>
                );
            case 'lens':
                return (
                    <Box sx={{ ...iconStyle, border: `2px solid ${alpha(theme.palette.common.white, 0.6)}`, borderRadius: '50%' }} />
                );
            case 'aperture':
                return (
                    <Box sx={{
                        ...iconStyle,
                        border: `2px solid ${alpha(theme.palette.common.white, 0.6)}`,
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: alpha(theme.palette.common.black, 0.4) }} />
                    </Box>
                );
            case 'detector':
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha('#10B981', 0.2),
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{ width: 8, height: 8, bgcolor: '#10B981', borderRadius: '50%' }} />
                    </Box>
                );
            case 'camera':
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha('#3B82F6', 0.2),
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{
                            width: 12,
                            height: 8,
                            border: `1px solid ${alpha('#3B82F6', 0.8)}`,
                            borderRadius: 0.5
                        }} />
                    </Box>
                );
            default:
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha(component.baseColor, 0.3),
                        borderRadius: 1
                    }} />
                );
        }
    };

    const shapeStyles = getShapeStyles();

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.08 }}
            whileHover={{ scale: 1.02 }}
            style={{ marginBottom: theme.spacing(2) }}
            onMouseEnter={onHover}
            onMouseLeave={onLeave}
            onClick={onSelect}
        >
            <Paper
                elevation={isHovered ? 8 : isSelected ? 6 : 2}
                sx={{
                    ...shapeStyles,
                    position: 'relative',
                    cursor: 'pointer',
                    overflow: 'hidden',
                    background: `linear-gradient(135deg, ${component.baseColor}, ${alpha(component.baseColor, 0.8)})`,
                    border: isSelected ? `2px solid ${theme.palette.primary.main}` : `1px solid ${alpha(theme.palette.common.white, 0.2)}`,
                    transition: theme.transitions.create(['transform', 'box-shadow', 'border-color'], {
                        duration: theme.transitions.duration.short,
                    }),
                    '&::before': {
                        content: '""',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '30%',
                        background: `linear-gradient(to bottom, ${alpha(theme.palette.common.white, 0.3)}, transparent)`,
                        pointerEvents: 'none'
                    }
                }}
            >
                {/* Content Container */}
                <Box
                    sx={{
                        position: 'relative',
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        p: 2,
                        zIndex: 1
                    }}
                >
                    {/* Icon */}
                    <Box sx={{ mb: 1 }}>
                        {renderComponentIcon()}
                    </Box>

                    {/* Component Name */}
                    <Typography
                        variant="body2"
                        sx={{
                            color: theme.palette.common.white,
                            fontWeight: 600,
                            textAlign: 'center',
                            textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                            mb: 0.5,
                            lineHeight: 1.2
                        }}
                    >
                        {component.name}
                    </Typography>

                    {/* Type Chip */}
                    <Chip
                        label={component.type}
                        size="small"
                        sx={{
                            bgcolor: alpha(theme.palette.common.white, 0.2),
                            color: theme.palette.common.white,
                            fontSize: '0.7rem',
                            height: 20,
                            '& .MuiChip-label': {
                                px: 1
                            }
                        }}
                    />

                    {/* Status indicators for specific types */}
                    {(component.type === 'camera' || component.type === 'detector') && (
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 8,
                                right: 8,
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                bgcolor: '#10B981',
                                boxShadow: `0 0 8px ${alpha('#10B981', 0.6)}`,
                                '@keyframes pulse': {
                                    '0%': {
                                        opacity: 0.4,
                                        transform: 'scale(0.8)'
                                    },
                                    '50%': {
                                        opacity: 1,
                                        transform: 'scale(1.2)'
                                    },
                                    '100%': {
                                        opacity: 0.4,
                                        transform: 'scale(0.8)'
                                    }
                                },
                                animation: 'pulse 2s infinite'
                            }}
                        />
                    )}

                    {/* Voltage indicator for source */}
                    {component.type === 'source' && component.specifications?.voltage && (
                        <Typography
                            variant="caption"
                            sx={{
                                position: 'absolute',
                                bottom: 4,
                                right: 8,
                                color: alpha(theme.palette.common.white, 0.8),
                                fontSize: '0.6rem',
                                fontWeight: 500
                            }}
                        >
                            {component.specifications.voltage}
                        </Typography>
                    )}
                </Box>

                {/* Hover overlay */}
                <Box
                    sx={{
                        position: 'absolute',
                        inset: 0,
                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                        opacity: isHovered ? 1 : 0,
                        transition: theme.transitions.create('opacity', {
                            duration: theme.transitions.duration.shorter,
                        })
                    }}
                />

                {/* Selection indicator */}
                {isSelected && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        style={{
                            position: 'absolute',
                            inset: -2,
                            border: `2px solid ${theme.palette.primary.main}`,
                            borderRadius: shapeStyles.borderRadius,
                            boxShadow: `0 0 12px ${alpha(theme.palette.primary.main, 0.4)}`
                        }}
                    />
                )}
            </Paper>

            {/* Electron beam visualization */}
            <Box
                sx={{
                    position: 'relative',
                    width: 2,
                    height: 24,
                    mx: 'auto',
                    overflow: 'hidden',
                    mt: 1
                }}
            >
                {/* Beam path */}
                <Box
                    sx={{
                        position: 'absolute',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 1,
                        height: '100%',
                        background: `linear-gradient(to bottom, ${alpha('#FDE047', 0.8)}, ${alpha('#F59E0B', 0.6)}, ${alpha('#FDE047', 0.4)})`,
                    }}
                />

                {/* Animated particles */}
                {[...Array(3)].map((_, i) => (
                    <ElectronParticle key={i} delay={i * 0.4} />
                ))}
            </Box>
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

                {/* Right Panel - Properties */}
                <Grid item xs={12} md={3} sx={{ height: '100%' }}>
                    <Box sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        height: '100%',
                        overflowY: 'auto'
                    }}>
                        {/* Property Editor */}
                        {selectedComponent ? (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ duration: 0.2 }}
                                style={{ height: '100%' }}
                            >
                                <Paper elevation={1} sx={{ p: 2, height: '100%' }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                            Properties
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {selectedComponent.id}
                                        </Typography>
                                    </Box>

                                    <Box sx={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: 2,
                                        height: 'calc(100% - 50px)',
                                        overflowY: 'auto'
                                    }}>
                                        {/* Basic Properties */}
                                        <Grid container spacing={2}>
                                            <Grid item xs={12}>
                                                <TextField
                                                    label="Name"
                                                    size="small"
                                                    fullWidth
                                                    value={selectedComponent.name}
                                                    onChange={(e) => handleComponentUpdate({
                                                        ...selectedComponent,
                                                        name: e.target.value
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={12}>
                                                <FormControl size="small" fullWidth>
                                                    <InputLabel>Type</InputLabel>
                                                    <Select
                                                        value={selectedComponent.type}
                                                        label="Type"
                                                        onChange={(e) => handleComponentUpdate({
                                                            ...selectedComponent,
                                                            type: e.target.value
                                                        })}
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
                                                    value={selectedComponent.width}
                                                    onChange={(e) => handleComponentUpdate({
                                                        ...selectedComponent,
                                                        width: parseInt(e.target.value)
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <TextField
                                                    label="Height"
                                                    type="number"
                                                    size="small"
                                                    fullWidth
                                                    value={selectedComponent.height}
                                                    onChange={(e) => handleComponentUpdate({
                                                        ...selectedComponent,
                                                        height: parseInt(e.target.value)
                                                    })}
                                                />
                                            </Grid>
                                            <Grid item xs={6}>
                                                <Box>
                                                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                                                        Color
                                                    </Typography>
                                                    <input
                                                        type="color"
                                                        value={selectedComponent.baseColor}
                                                        onChange={(e) => handleComponentUpdate({
                                                            ...selectedComponent,
                                                            baseColor: e.target.value
                                                        })}
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
                                                        value={selectedComponent.shape}
                                                        label="Shape"
                                                        onChange={(e) => handleComponentUpdate({
                                                            ...selectedComponent,
                                                            shape: e.target.value as any
                                                        })}
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
                                            value={selectedComponent.description || ''}
                                            onChange={(e) => handleComponentUpdate({
                                                ...selectedComponent,
                                                description: e.target.value
                                            })}
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
                                                    onClick={() => {
                                                        const key = prompt('Enter specification key:');
                                                        const value = prompt('Enter specification value:');
                                                        if (key && value) {
                                                            handleComponentUpdate({
                                                                ...selectedComponent,
                                                                specifications: {
                                                                    ...selectedComponent.specifications,
                                                                    [key]: value
                                                                }
                                                            });
                                                        }
                                                    }}
                                                    sx={{ minWidth: 'auto', px: 1 }}
                                                >
                                                    + Add
                                                </Button>
                                            </Box>
                                            <Box sx={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
                                                {selectedComponent.specifications && Object.entries(selectedComponent.specifications).map(([key, value]) => (
                                                    <Box key={key} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                                        <TextField
                                                            size="small"
                                                            value={key}
                                                            placeholder="Key"
                                                            onChange={(e) => {
                                                                const newSpecs = { ...selectedComponent.specifications };
                                                                delete newSpecs[key];
                                                                newSpecs[e.target.value] = value;
                                                                handleComponentUpdate({
                                                                    ...selectedComponent,
                                                                    specifications: newSpecs
                                                                });
                                                            }}
                                                            sx={{ flex: 1 }}
                                                        />
                                                        <TextField
                                                            size="small"
                                                            value={String(value)}
                                                            placeholder="Value"
                                                            onChange={(e) => handleComponentUpdate({
                                                                ...selectedComponent,
                                                                specifications: {
                                                                    ...selectedComponent.specifications,
                                                                    [key]: e.target.value
                                                                }
                                                            })}
                                                            sx={{ flex: 1 }}
                                                        />
                                                        <Button
                                                            size="small"
                                                            color="error"
                                                            onClick={() => {
                                                                const newSpecs = { ...selectedComponent.specifications };
                                                                delete newSpecs[key];
                                                                handleComponentUpdate({
                                                                    ...selectedComponent,
                                                                    specifications: newSpecs
                                                                });
                                                            }}
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