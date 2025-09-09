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
    Box,
    Plus,
    Trash2,
    Copy,
    BookmarkPlus
} from 'lucide-react';

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
                <span className="text-gray-600 text-sm font-mono">
          {String(value ?? '')}
        </span>
            );
        }

        if (isEditing) {
            return (
                <input
                    type="text"
                    value={String(value ?? '')}
                    onChange={(e) => onChange(e.target.value)}
                    onBlur={() => setEditingProperty(null)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            setEditingProperty(null);
                        } else if (e.key === 'Escape') {
                            setEditingProperty(null);
                        }
                    }}
                    className="w-full px-1 py-0.5 text-sm font-mono border border-blue-400 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    autoFocus
                />
            );
        }

        return (
            <button
                onClick={() => setEditingProperty(editKey)}
                className="text-left w-full text-sm font-mono text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-1 py-0.5 rounded"
            >
                {String(value ?? '')}
            </button>
        );
    };

    return (
        <div className="w-80 bg-white border border-gray-300 rounded-lg shadow-lg overflow-hidden">
            <div className="bg-gray-100 border-b border-gray-300 px-3 py-2">
                <h3 className="text-sm font-semibold text-gray-700">Properties</h3>
            </div>

            <div className="h-96 overflow-y-auto">
                {/* Microscope and Camera Properties */}
                {Object.entries(groupedMicroscopeCameraProperties).map(([category, subcategories]) => (
                    <div key={category} className="border-b border-gray-200">
                        <button
                            onClick={() => toggleCategory(category)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 focus:outline-none focus:bg-gray-100"
                        >
                            {expandedCategories.has(category) ? (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                            ) : (
                                <ChevronRight className="w-4 h-4 text-gray-500" />
                            )}
                            {getCategoryIcon(category)}
                            <span className="text-sm font-medium text-gray-700 capitalize">
                {category}
              </span>
                        </button>

                        {expandedCategories.has(category) && (
                            <div className="bg-gray-50">
                                {Object.entries(subcategories).map(([subcategory, props]) => {
                                    const subcategoryKey = `${category}-${subcategory}`;
                                    return (
                                        <div key={subcategoryKey}>
                                            <button
                                                onClick={() => toggleSubcategory(subcategoryKey)}
                                                className="w-full flex items-center gap-2 px-6 py-1.5 text-left hover:bg-gray-100 focus:outline-none focus:bg-gray-150"
                                            >
                                                {expandedSubcategories.has(subcategoryKey) ? (
                                                    <ChevronDown className="w-3 h-3 text-gray-400" />
                                                ) : (
                                                    <ChevronRight className="w-3 h-3 text-gray-400" />
                                                )}
                                                {getSubcategoryIcon(subcategory)}
                                                <span className="text-xs font-medium text-gray-600 capitalize">
                          {subcategory.replace(/_/g, ' ')}
                        </span>
                                            </button>

                                            {expandedSubcategories.has(subcategoryKey) && (
                                                <div className="bg-white">
                                                    {props.map((prop) => (
                                                        <div
                                                            key={prop.id}
                                                            className="flex items-center justify-between px-8 py-1.5 hover:bg-blue-50 border-l-2 border-transparent hover:border-blue-300"
                                                        >
                                                            <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span
                                    className={`text-xs ${prop.editable ? 'text-gray-700' : 'text-gray-500'}`}
                                    title={prop.property_name}
                                >
                                  {formatPropertyName(prop.property_name)}
                                </span>
                                                                {!prop.editable && (
                                                                    <span className="text-xs text-gray-400">🔒</span>
                                                                )}
                                                            </div>
                                                            <div className="min-w-0 flex-1 text-right">
                                                                {renderPropertyValue(
                                                                    prop,
                                                                    microscopeCameraValues[prop.property_name],
                                                                    (newValue) => handleMicroscopeCameraPropertyChange(prop.property_name, newValue),
                                                                    prop.property_name
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                ))}

                {/* Presets */}
                <div className="border-b border-gray-200">
                    <div className="flex items-center justify-between px-3 py-2 bg-gray-50">
                        <div className="flex items-center gap-2">
                            <BookmarkPlus className="w-4 h-4 text-gray-600" />
                            <span className="text-sm font-medium text-gray-700">Presets</span>
                        </div>
                        <button
                            onClick={addNewPreset}
                            className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded"
                            title="Add New Preset"
                        >
                            <Plus className="w-3 h-3" />
                        </button>
                    </div>

                    {presets.map((preset) => (
                        <div key={preset.id} className="bg-gray-50">
                            <div className="flex items-center justify-between px-6 py-2">
                                <button
                                    onClick={() => togglePreset(preset.id)}
                                    className="flex items-center gap-2 flex-1 text-left hover:bg-gray-100 focus:outline-none focus:bg-gray-150 px-2 py-1 rounded"
                                >
                                    {expandedPresets.has(preset.id) ? (
                                        <ChevronDown className="w-3 h-3 text-gray-400" />
                                    ) : (
                                        <ChevronRight className="w-3 h-3 text-gray-400" />
                                    )}
                                    <Settings className="w-3 h-3 text-gray-500" />
                                    <span className="text-xs font-medium text-gray-600">
                    {preset.name}
                  </span>
                                </button>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={() => duplicatePreset(preset)}
                                        className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
                                        title="Duplicate Preset"
                                    >
                                        <Copy className="w-3 h-3" />
                                    </button>
                                    <button
                                        onClick={() => deletePreset(preset.id)}
                                        className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-100 rounded"
                                        title="Delete Preset"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>

                            {expandedPresets.has(preset.id) && (
                                <div className="bg-white ml-4">
                                    {Object.entries(groupedPresetProperties).map(([subcategory, props]) => (
                                        <div key={`${preset.id}-${subcategory}`}>
                                            <div className="flex items-center gap-2 px-6 py-1.5 bg-gray-50">
                                                {getSubcategoryIcon(subcategory)}
                                                <span className="text-xs font-medium text-gray-600 capitalize">
                          {subcategory.replace(/_/g, ' ')}
                        </span>
                                            </div>

                                            <div className="bg-white">
                                                {props.map((prop) => (
                                                    <div
                                                        key={`${preset.id}-${prop.id}`}
                                                        className="flex items-center justify-between px-8 py-1.5 hover:bg-blue-50 border-l-2 border-transparent hover:border-blue-300"
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0 flex-1">
                              <span
                                  className={`text-xs ${prop.editable ? 'text-gray-700' : 'text-gray-500'}`}
                                  title={prop.property_name}
                              >
                                {formatPropertyName(prop.property_name)}
                              </span>
                                                            {!prop.editable && (
                                                                <span className="text-xs text-gray-400">🔒</span>
                                                            )}
                                                        </div>
                                                        <div className="min-w-0 flex-1 text-right">
                                                            {renderPropertyValue(
                                                                prop,
                                                                preset.values[prop.property_name],
                                                                (newValue) => handlePresetPropertyChange(preset.id, prop.property_name, newValue),
                                                                `${preset.id}-${prop.property_name}`
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            <div className="bg-gray-100 border-t border-gray-300 px-3 py-2 text-xs text-gray-500">
                {microscopeCameraProperties.length} system properties • {presets.length} presets
            </div>
        </div>
    );
};

export default PropertyExplorer;