import React, { useState, useMemo } from 'react';
import {
    ChevronDown,
    ChevronRight,
    Microscope,
    Camera,
    Settings,
    Clock,
    Zap,
    Move,
    Focus,
    Filter,
    Monitor,
    Gauge,
    Target,
    RotateCw,
    Eye,
    Sun,
    Layers,
    Grid,
    Play,
    Thermometer,
    Film,
    Sliders,
    Plus,
    Trash2,
    Copy,
    BookmarkPlus
} from 'lucide-react';
import { Box, Typography, Paper, IconButton } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';

interface Property {
    id: number;
    type: string;
    property_name: string;
    keep_in_magellon: boolean;
    editable: boolean;
    category: string;
    subcategory: string;
}

interface Preset {
    id: string;
    name: string;
    values: Record<string, any>;
}

// Mock data with separate microscope/camera properties and multiple presets
const microscopeCameraProperties: Property[] = [
    {
        id: 1,
        type: "microscope_property",
        property_name: "system_time",
        keep_in_magellon: true,
        editable: false,
        category: "microscope",
        subcategory: "system"
    },
    {
        id: 2,
        type: "microscope_property",
        property_name: "magnification",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "optics"
    },
    {
        id: 3,
        type: "microscope_property",
        property_name: "spot_size",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "beam"
    },
    {
        id: 4,
        type: "microscope_property",
        property_name: "intensity",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "beam"
    },
    {
        id: 5,
        type: "microscope_property",
        property_name: "image_shift_x",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "alignment"
    },
    {
        id: 6,
        type: "microscope_property",
        property_name: "image_shift_y",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "alignment"
    },
    {
        id: 9,
        type: "microscope_property",
        property_name: "defocus",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "focus"
    },
    {
        id: 21,
        type: "microscope_property",
        property_name: "stage_position_x",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "stage"
    },
    {
        id: 22,
        type: "microscope_property",
        property_name: "stage_position_y",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "stage"
    },
    {
        id: 23,
        type: "microscope_property",
        property_name: "stage_position_z",
        keep_in_magellon: true,
        editable: true,
        category: "microscope",
        subcategory: "stage"
    },
    {
        id: 29,
        type: "microscope_property",
        property_name: "vacuum_status",
        keep_in_magellon: true,
        editable: false,
        category: "microscope",
        subcategory: "system"
    },
    {
        id: 31,
        type: "microscope_property",
        property_name: "column_pressure",
        keep_in_magellon: true,
        editable: false,
        category: "microscope",
        subcategory: "vacuum"
    },
    {
        id: 52,
        type: "camera_property",
        property_name: "exposure_time",
        keep_in_magellon: true,
        editable: true,
        category: "camera",
        subcategory: "exposure"
    },
    {
        id: 61,
        type: "camera_property",
        property_name: "temperature",
        keep_in_magellon: true,
        editable: false,
        category: "camera",
        subcategory: "sensor"
    },
    {
        id: 48,
        type: "camera_property",
        property_name: "subd_binning_x",
        keep_in_magellon: true,
        editable: true,
        category: "camera",
        subcategory: "sampling"
    },
    {
        id: 49,
        type: "camera_property",
        property_name: "subd_binning_y",
        keep_in_magellon: true,
        editable: true,
        category: "camera",
        subcategory: "sampling"
    }
];

const presetProperties: Property[] = [
    {
        id: 64,
        type: "preset_property",
        property_name: "preset_name",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "identification"
    },
    {
        id: 65,
        type: "preset_property",
        property_name: "preset_magnification",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "optics"
    },
    {
        id: 66,
        type: "preset_property",
        property_name: "preset_spot_size",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "beam"
    },
    {
        id: 67,
        type: "preset_property",
        property_name: "preset_intensity",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "beam"
    },
    {
        id: 72,
        type: "preset_property",
        property_name: "preset_defocus",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "focus"
    },
    {
        id: 79,
        type: "preset_property",
        property_name: "preset_exposure_time",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "exposure"
    },
    {
        id: 80,
        type: "preset_property",
        property_name: "preset_dose",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "dose"
    },
    {
        id: 75,
        type: "preset_property",
        property_name: "preset_binning_x",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "sampling"
    },
    {
        id: 76,
        type: "preset_property",
        property_name: "preset_binning_y",
        keep_in_magellon: true,
        editable: true,
        category: "preset",
        subcategory: "sampling"
    }
];

// Mock microscope/camera values
const mockMicroscopeCameraValues: Record<string, any> = {
    system_time: "2025-01-09 14:30:22",
    magnification: 50000,
    spot_size: 3,
    intensity: 0.75,
    image_shift_x: 0.0,
    image_shift_y: 0.0,
    defocus: -2.5,
    stage_position_x: 125.4,
    stage_position_y: 87.2,
    stage_position_z: 15.0,
    vacuum_status: "Good",
    column_pressure: "1.2e-7",
    exposure_time: 1.0,
    temperature: -196.5,
    subd_binning_x: 1,
    subd_binning_y: 1
};

// Mock presets
const mockPresets: Preset[] = [
    {
        id: "preset-1",
        name: "High Resolution",
        values: {
            preset_name: "High Resolution",
            preset_magnification: 100000,
            preset_spot_size: 1,
            preset_intensity: 0.8,
            preset_defocus: -1.5,
            preset_exposure_time: 2.0,
            preset_dose: 25.0,
            preset_binning_x: 1,
            preset_binning_y: 1
        }
    },
    {
        id: "preset-2",
        name: "Low Dose",
        values: {
            preset_name: "Low Dose",
            preset_magnification: 50000,
            preset_spot_size: 5,
            preset_intensity: 0.3,
            preset_defocus: -2.0,
            preset_exposure_time: 0.5,
            preset_dose: 5.0,
            preset_binning_x: 2,
            preset_binning_y: 2
        }
    },
    {
        id: "preset-3",
        name: "Fast Survey",
        values: {
            preset_name: "Fast Survey",
            preset_magnification: 10000,
            preset_spot_size: 7,
            preset_intensity: 0.6,
            preset_defocus: -3.0,
            preset_exposure_time: 0.2,
            preset_dose: 2.0,
            preset_binning_x: 4,
            preset_binning_y: 4
        }
    }
];

const getCategoryIcon = (category: string) => {
    switch (category) {
        case 'microscope': return <Microscope className="w-4 h-4" />;
        case 'camera': return <Camera className="w-4 h-4" />;
        case 'preset': return <BookmarkPlus className="w-4 h-4" />;
        default: return <Box className="w-4 h-4" />;
    }
};

const getSubcategoryIcon = (subcategory: string) => {
    const iconMap: Record<string, React.ReactNode> = {
        system: <Monitor className="w-3 h-3" />,
        optics: <Eye className="w-3 h-3" />,
        beam: <Zap className="w-3 h-3" />,
        alignment: <Target className="w-3 h-3" />,
        focus: <Focus className="w-3 h-3" />,
        stage: <Move className="w-3 h-3" />,
        vacuum: <Gauge className="w-3 h-3" />,
        exposure: <Clock className="w-3 h-3" />,
        sensor: <Thermometer className="w-3 h-3" />,
        identification: <Settings className="w-3 h-3" />,
        timing: <Clock className="w-3 h-3" />,
        filter: <Filter className="w-3 h-3" />,
        screen: <Monitor className="w-3 h-3" />,
        dose: <Sun className="w-3 h-3" />,
        lens: <Eye className="w-3 h-3" />,
        mode: <Layers className="w-3 h-3" />,
        diffraction: <Grid className="w-3 h-3" />,
        geometry: <Box className="w-3 h-3" />,
        sampling: <Grid className="w-3 h-3" />,
        status: <Monitor className="w-3 h-3" />,
        frames: <Film className="w-3 h-3" />,
        correction: <Sliders className="w-3 h-3" />,
        control: <Play className="w-3 h-3" />,
        stigmator: <Target className="w-3 h-3" />,
        holder: <Box className="w-3 h-3" />
    };

    return iconMap[subcategory] || <Settings className="w-3 h-3" />;
};

const PropertyExplorer: React.FC = () => {
    const theme = useTheme();
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['microscope']));
    const [expandedSubcategories, setExpandedSubcategories] = useState<Set<string>>(new Set());
    const [expandedPresets, setExpandedPresets] = useState<Set<string>>(new Set(['preset-1']));
    const [microscopeCameraValues, setMicroscopeCameraValues] = useState<Record<string, any>>(mockMicroscopeCameraValues);
    const [presets, setPresets] = useState<Preset[]>(mockPresets);
    const [editingProperty, setEditingProperty] = useState<string | null>(null);
    const [editingPreset, setEditingPreset] = useState<string | null>(null);

    // Group microscope/camera properties by category and subcategory
    const groupedMicroscopeCameraProperties = useMemo(() => {
        const grouped: Record<string, Record<string, Property[]>> = {};

        microscopeCameraProperties.forEach(prop => {
            if (!grouped[prop.category]) {
                grouped[prop.category] = {};
            }
            if (!grouped[prop.category][prop.subcategory]) {
                grouped[prop.category][prop.subcategory] = [];
            }
            grouped[prop.category][prop.subcategory].push(prop);
        });

        return grouped;
    }, []);

    // Group preset properties by subcategory
    const groupedPresetProperties = useMemo(() => {
        const grouped: Record<string, Property[]> = {};

        presetProperties.forEach(prop => {
            if (!grouped[prop.subcategory]) {
                grouped[prop.subcategory] = [];
            }
            grouped[prop.subcategory].push(prop);
        });

        return grouped;
    }, []);

    const toggleCategory = (category: string) => {
        const newExpanded = new Set(expandedCategories);
        if (newExpanded.has(category)) {
            newExpanded.delete(category);
        } else {
            newExpanded.add(category);
        }
        setExpandedCategories(newExpanded);
    };

    const toggleSubcategory = (key: string) => {
        const newExpanded = new Set(expandedSubcategories);
        if (newExpanded.has(key)) {
            newExpanded.delete(key);
        } else {
            newExpanded.add(key);
        }
        setExpandedSubcategories(newExpanded);
    };

    const togglePreset = (presetId: string) => {
        const newExpanded = new Set(expandedPresets);
        if (newExpanded.has(presetId)) {
            newExpanded.delete(presetId);
        } else {
            newExpanded.add(presetId);
        }
        setExpandedPresets(newExpanded);
    };

    const handleMicroscopeCameraPropertyChange = (propertyName: string, newValue: any) => {
        setMicroscopeCameraValues(prev => ({
            ...prev,
            [propertyName]: newValue
        }));
    };

    const handlePresetPropertyChange = (presetId: string, propertyName: string, newValue: any) => {
        setPresets(prev => prev.map(preset =>
            preset.id === presetId
                ? { ...preset, values: { ...preset.values, [propertyName]: newValue } }
                : preset
        ));
    };

    const addNewPreset = () => {
        const newPreset: Preset = {
            id: `preset-${Date.now()}`,
            name: `New Preset ${presets.length + 1}`,
            values: {
                preset_name: `New Preset ${presets.length + 1}`,
                preset_magnification: 50000,
                preset_spot_size: 3,
                preset_intensity: 0.5,
                preset_defocus: -2.0,
                preset_exposure_time: 1.0,
                preset_dose: 10.0,
                preset_binning_x: 1,
                preset_binning_y: 1
            }
        };
        setPresets(prev => [...prev, newPreset]);
        setExpandedPresets(prev => new Set([...prev, newPreset.id]));
    };

    const deletePreset = (presetId: string) => {
        setPresets(prev => prev.filter(preset => preset.id !== presetId));
        setExpandedPresets(prev => {
            const newSet = new Set(prev);
            newSet.delete(presetId);
            return newSet;
        });
    };

    const duplicatePreset = (preset: Preset) => {
        const newPreset: Preset = {
            id: `preset-${Date.now()}`,
            name: `${preset.name} Copy`,
            values: {
                ...preset.values,
                preset_name: `${preset.name} Copy`
            }
        };
        setPresets(prev => [...prev, newPreset]);
        setExpandedPresets(prev => new Set([...prev, newPreset.id]));
    };

    const formatPropertyName = (name: string) => {
        return name
            .replace(/^preset_/, '')
            .replace(/_/g, ' ')
            .replace(/([a-z])([A-Z])/g, '$1 $2')
            .replace(/\b\w/g, l => l.toUpperCase());
    };

    const renderPropertyValue = (prop: Property, value: any, onChange: (newValue: any) => void, editKey: string) => {
        const isEditing = editingProperty === editKey;

        if (!prop.editable) {
            return (
                <Typography
                    variant="body2"
                    sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        color: 'text.secondary'
                    }}
                >
                    {String(value ?? '')}
                </Typography>
            );
        }

        if (isEditing) {
            return (
                <Box
                    component="input"
                    type="text"
                    value={String(value ?? '')}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
                    onBlur={() => setEditingProperty(null)}
                    onKeyDown={(e: React.KeyboardEvent) => {
                        if (e.key === 'Enter') {
                            setEditingProperty(null);
                        } else if (e.key === 'Escape') {
                            setEditingProperty(null);
                        }
                    }}
                    sx={{
                        width: '100%',
                        px: 0.5,
                        py: 0.25,
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                        border: `1px solid ${theme.palette.primary.main}`,
                        borderRadius: 1,
                        outline: 'none',
                        backgroundColor: 'background.paper',
                        '&:focus': {
                            borderColor: theme.palette.primary.main,
                            boxShadow: `0 0 0 1px ${alpha(theme.palette.primary.main, 0.25)}`
                        }
                    }}
                    autoFocus
                />
            );
        }

        return (
            <Box
                component="button"
                onClick={() => setEditingProperty(editKey)}
                sx={{
                    textAlign: 'left',
                    width: '100%',
                    fontSize: '0.75rem',
                    fontFamily: 'monospace',
                    color: 'primary.main',
                    backgroundColor: 'transparent',
                    border: 'none',
                    borderRadius: 1,
                    px: 0.5,
                    py: 0.25,
                    cursor: 'pointer',
                    '&:hover': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.08),
                        color: 'primary.dark'
                    }
                }}
            >
                {String(value ?? '')}
            </Box>
        );
    };

    return (
        <Paper
            elevation={2}
            sx={{
                width: 320,
                borderRadius: 2,
                overflow: 'hidden'
            }}
        >
            <Box
                sx={{
                    backgroundColor: alpha(theme.palette.grey[100], 0.8),
                    borderBottom: `1px solid ${theme.palette.divider}`,
                    px: 1.5,
                    py: 1
                }}
            >
                <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    Properties
                </Typography>
            </Box>

            <Box sx={{ height: 384, overflowY: 'auto' }}>
                {/* Microscope and Camera Properties */}
                {Object.entries(groupedMicroscopeCameraProperties).map(([category, subcategories]) => (
                    <Box key={category} sx={{ borderBottom: `1px solid ${theme.palette.divider}` }}>
                        <Box
                            component="button"
                            onClick={() => toggleCategory(category)}
                            sx={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                px: 1.5,
                                py: 1,
                                textAlign: 'left',
                                backgroundColor: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.grey[100], 0.5)
                                },
                                '&:focus': {
                                    outline: 'none',
                                    backgroundColor: alpha(theme.palette.grey[200], 0.5)
                                }
                            }}
                        >
                            {expandedCategories.has(category) ? (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                            ) : (
                                <ChevronRight className="w-4 h-4 text-gray-500" />
                            )}
                            {getCategoryIcon(category)}
                            <Typography
                                variant="body2"
                                sx={{
                                    fontWeight: 500,
                                    color: 'text.primary',
                                    textTransform: 'capitalize'
                                }}
                            >
                                {category}
                            </Typography>
                        </Box>

                        {expandedCategories.has(category) && (
                            <Box sx={{ backgroundColor: alpha(theme.palette.grey[50], 0.5) }}>
                                {Object.entries(subcategories).map(([subcategory, props]) => {
                                    const subcategoryKey = `${category}-${subcategory}`;
                                    return (
                                        <Box key={subcategoryKey}>
                                            <Box
                                                component="button"
                                                onClick={() => toggleSubcategory(subcategoryKey)}
                                                sx={{
                                                    width: '100%',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: 1,
                                                    px: 3,
                                                    py: 0.75,
                                                    textAlign: 'left',
                                                    backgroundColor: 'transparent',
                                                    border: 'none',
                                                    cursor: 'pointer',
                                                    '&:hover': {
                                                        backgroundColor: alpha(theme.palette.grey[100], 0.8)
                                                    },
                                                    '&:focus': {
                                                        outline: 'none',
                                                        backgroundColor: alpha(theme.palette.grey[200], 0.5)
                                                    }
                                                }}
                                            >
                                                {expandedSubcategories.has(subcategoryKey) ? (
                                                    <ChevronDown className="w-3 h-3 text-gray-400" />
                                                ) : (
                                                    <ChevronRight className="w-3 h-3 text-gray-400" />
                                                )}
                                                {getSubcategoryIcon(subcategory)}
                                                <Typography
                                                    variant="caption"
                                                    sx={{
                                                        fontWeight: 500,
                                                        color: 'text.secondary',
                                                        textTransform: 'capitalize'
                                                    }}
                                                >
                                                    {subcategory.replace(/_/g, ' ')}
                                                </Typography>
                                            </Box>

                                            {expandedSubcategories.has(subcategoryKey) && (
                                                <Box sx={{ backgroundColor: 'background.paper' }}>
                                                    {props.map((prop) => (
                                                        <Box
                                                            key={prop.id}
                                                            sx={{
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                justifyContent: 'space-between',
                                                                px: 4,
                                                                py: 0.75,
                                                                borderLeft: `2px solid transparent`,
                                                                '&:hover': {
                                                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                                                    borderLeftColor: alpha(theme.palette.primary.main, 0.3)
                                                                }
                                                            }}
                                                        >
                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flex: 1 }}>
                                                                <Typography
                                                                    variant="caption"
                                                                    sx={{
                                                                        color: prop.editable ? 'text.primary' : 'text.disabled',
                                                                        fontSize: '0.7rem'
                                                                    }}
                                                                    title={prop.property_name}
                                                                >
                                                                    {formatPropertyName(prop.property_name)}
                                                                </Typography>
                                                                {!prop.editable && (
                                                                    <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.7rem' }}>
                                                                        🔒
                                                                    </Typography>
                                                                )}
                                                            </Box>
                                                            <Box sx={{ minWidth: 0, flex: 1, textAlign: 'right' }}>
                                                                {renderPropertyValue(
                                                                    prop,
                                                                    microscopeCameraValues[prop.property_name],
                                                                    (newValue) => handleMicroscopeCameraPropertyChange(prop.property_name, newValue),
                                                                    prop.property_name
                                                                )}
                                                            </Box>
                                                        </Box>
                                                    ))}
                                                </Box>
                                            )}
                                        </Box>
                                    );
                                })}
                            </Box>
                        )}
                    </Box>
                ))}

                {/* Presets */}
                <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}` }}>
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            px: 1.5,
                            py: 1,
                            backgroundColor: alpha(theme.palette.grey[50], 0.5)
                        }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <BookmarkPlus className="w-4 h-4 text-gray-600" />
                            <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                                Presets
                            </Typography>
                        </Box>
                        <IconButton
                            size="small"
                            onClick={addNewPreset}
                            sx={{
                                color: 'text.secondary',
                                '&:hover': {
                                    color: 'text.primary',
                                    backgroundColor: alpha(theme.palette.grey[200], 0.5)
                                }
                            }}
                            title="Add New Preset"
                        >
                            <Plus className="w-3 h-3" />
                        </IconButton>
                    </Box>

                    {presets.map((preset) => (
                        <Box key={preset.id} sx={{ backgroundColor: alpha(theme.palette.grey[50], 0.5) }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 3, py: 1 }}>
                                <Box
                                    component="button"
                                    onClick={() => togglePreset(preset.id)}
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 1,
                                        flex: 1,
                                        textAlign: 'left',
                                        backgroundColor: 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        px: 1,
                                        py: 0.5,
                                        borderRadius: 1,
                                        '&:hover': {
                                            backgroundColor: alpha(theme.palette.grey[100], 0.8)
                                        },
                                        '&:focus': {
                                            outline: 'none',
                                            backgroundColor: alpha(theme.palette.grey[200], 0.5)
                                        }
                                    }}
                                >
                                    {expandedPresets.has(preset.id) ? (
                                        <ChevronDown className="w-3 h-3 text-gray-400" />
                                    ) : (
                                        <ChevronRight className="w-3 h-3 text-gray-400" />
                                    )}
                                    <Settings className="w-3 h-3 text-gray-500" />
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            fontWeight: 500,
                                            color: 'text.secondary',
                                            fontSize: '0.7rem'
                                        }}
                                    >
                                        {preset.name}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <IconButton
                                        size="small"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            duplicatePreset(preset);
                                        }}
                                        sx={{
                                            color: 'text.disabled',
                                            '&:hover': {
                                                color: 'text.secondary',
                                                backgroundColor: alpha(theme.palette.grey[200], 0.5)
                                            }
                                        }}
                                        title="Duplicate Preset"
                                    >
                                        <Copy className="w-3 h-3" />
                                    </IconButton>
                                    <IconButton
                                        size="small"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            deletePreset(preset.id);
                                        }}
                                        sx={{
                                            color: 'text.disabled',
                                            '&:hover': {
                                                color: 'error.main',
                                                backgroundColor: alpha(theme.palette.error.main, 0.1)
                                            }
                                        }}
                                        title="Delete Preset"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </IconButton>
                                </Box>
                            </Box>

                            {expandedPresets.has(preset.id) && (
                                <Box sx={{ backgroundColor: 'background.paper', ml: 2 }}>
                                    {Object.entries(groupedPresetProperties).map(([subcategory, props]) => (
                                        <Box key={`${preset.id}-${subcategory}`}>
                                            <Box
                                                sx={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: 1,
                                                    px: 3,
                                                    py: 0.75,
                                                    backgroundColor: alpha(theme.palette.grey[50], 0.5)
                                                }}
                                            >
                                                {getSubcategoryIcon(subcategory)}
                                                <Typography
                                                    variant="caption"
                                                    sx={{
                                                        fontWeight: 500,
                                                        color: 'text.secondary',
                                                        textTransform: 'capitalize',
                                                        fontSize: '0.7rem'
                                                    }}
                                                >
                                                    {subcategory.replace(/_/g, ' ')}
                                                </Typography>
                                            </Box>

                                            <Box sx={{ backgroundColor: 'background.paper' }}>
                                                {props.map((prop) => (
                                                    <Box
                                                        key={`${preset.id}-${prop.id}`}
                                                        sx={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'space-between',
                                                            px: 4,
                                                            py: 0.75,
                                                            borderLeft: `2px solid transparent`,
                                                            '&:hover': {
                                                                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                                                borderLeftColor: alpha(theme.palette.primary.main, 0.3)
                                                            }
                                                        }}
                                                    >
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flex: 1 }}>
                                                            <Typography
                                                                variant="caption"
                                                                sx={{
                                                                    color: prop.editable ? 'text.primary' : 'text.disabled',
                                                                    fontSize: '0.7rem'
                                                                }}
                                                                title={prop.property_name}
                                                            >
                                                                {formatPropertyName(prop.property_name)}
                                                            </Typography>
                                                            {!prop.editable && (
                                                                <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.7rem' }}>
                                                                    🔒
                                                                </Typography>
                                                            )}
                                                        </Box>
                                                        <Box sx={{ minWidth: 0, flex: 1, textAlign: 'right' }}>
                                                            {renderPropertyValue(
                                                                prop,
                                                                preset.values[prop.property_name],
                                                                (newValue) => handlePresetPropertyChange(preset.id, prop.property_name, newValue),
                                                                `${preset.id}-${prop.property_name}`
                                                            )}
                                                        </Box>
                                                    </Box>
                                                ))}
                                            </Box>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </Box>
                    ))}
                </Box>
            </Box>

            <Box
                sx={{
                    backgroundColor: alpha(theme.palette.grey[100], 0.8),
                    borderTop: `1px solid ${theme.palette.divider}`,
                    px: 1.5,
                    py: 1
                }}
            >
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                    {microscopeCameraProperties.length} system properties • {presets.length} presets
                </Typography>
            </Box>
        </Paper>
    );
};

export default PropertyExplorer;