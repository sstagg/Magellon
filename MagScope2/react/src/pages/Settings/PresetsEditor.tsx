import React, { useState, useMemo } from 'react';
import {
    ChevronDown,
    Microscope,
    Camera,
    BookmarkPlus,
    Plus,
    Trash2,
    Copy,
    Save,
    Download,
    Upload,
    Search,
    X,
    Lock,
    Unlock,
    Check,
    Edit
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import microscopePropertiesData from './microscope_properties.json';

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
    description?: string;
    values: Record<string, any>;
    createdAt: string;
    updatedAt: string;
}

interface PresetsEditorProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

// Import all properties from JSON
const allProperties: Property[] = microscopePropertiesData as Property[];

// Split properties by category
const microscopeProperties = allProperties.filter(p => p.category === 'microscope');
const cameraProperties = allProperties.filter(p => p.category === 'camera');

// Generate subcategory icons
const getSubcategoryIcon = (subcategory: string): React.ReactNode => {
    const iconClass = "w-4 h-4";
    const icons: Record<string, React.ReactNode> = {
        system: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>,
        optics: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>,
        beam: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
        alignment: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></svg>,
        focus: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2v4m0 12v4M2 12h4m12 0h4" /></svg>,
        stage: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5" /></svg>,
        vacuum: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" /></svg>,
        exposure: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6l4 2" /></svg>,
        sensor: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
        dose: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 1v6m0 6v6m6-11.5l-4.5 4.5m-3 3l-4.5 4.5M23 12h-6m-6 0H1m20.5-6l-4.5 4.5m-9 0L2.5 6m18 12l-4.5-4.5m-9 0l-4.5 4.5" /></svg>,
        filter: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>,
        geometry: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>,
        sampling: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5h16M4 12h16M4 19h16" /><circle cx="6" cy="5" r="1.5" /><circle cx="6" cy="12" r="1.5" /><circle cx="6" cy="19" r="1.5" /><circle cx="18" cy="5" r="1.5" /><circle cx="18" cy="12" r="1.5" /><circle cx="18" cy="19" r="1.5" /></svg>,
        frames: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" /></svg>,
        timing: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6l4 2" /></svg>,
        mode: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 16a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-3zM14 16a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1h-4a1 1 0 01-1-1v-3z" /></svg>,
        diffraction: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" /></svg>,
        stigmator: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>,
        holder: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>,
        lens: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35" /></svg>,
        screen: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 21h8m-4-4v4" /></svg>,
        correction: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>,
        identification: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2" /></svg>,
        control: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>,
        status: <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    };

    return icons[subcategory] || <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>;
};

const formatPropertyName = (name: string): string => {
    return name
        .replace(/^preset_/, '')
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
};

export const PresetsEditor: React.FC<PresetsEditorProps> = ({ open, onOpenChange }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [filterEditable, setFilterEditable] = useState<'all' | 'editable' | 'readonly'>('all');
    const [showKeptOnly, setShowKeptOnly] = useState(false);
    const [selectedMicroscopePreset, setSelectedMicroscopePreset] = useState<string | null>('microscope-preset-1');
    const [selectedCameraPreset, setSelectedCameraPreset] = useState<string | null>('camera-preset-1');

    // Mock preset data
    const [microscopePresets, setMicroscopePresets] = useState<Preset[]>([
        {
            id: 'microscope-preset-1',
            name: 'High Resolution',
            description: 'Optimized for high-resolution imaging',
            values: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        },
        {
            id: 'microscope-preset-2',
            name: 'Low Dose',
            description: 'Minimized electron dose for sensitive samples',
            values: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        }
    ]);

    const [cameraPresets, setCameraPresets] = useState<Preset[]>([
        {
            id: 'camera-preset-1',
            name: 'Fast Acquisition',
            description: 'Optimized for speed',
            values: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        },
        {
            id: 'camera-preset-2',
            name: 'High Quality',
            description: 'Maximum quality settings',
            values: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        }
    ]);

    // Group properties by subcategory
    const groupPropertiesBySubcategory = (properties: Property[]) => {
        let filteredProps = properties;

        // Apply filters
        if (searchQuery) {
            filteredProps = filteredProps.filter(p =>
                p.property_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                p.subcategory.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }

        if (filterEditable !== 'all') {
            filteredProps = filteredProps.filter(p =>
                filterEditable === 'editable' ? p.editable : !p.editable
            );
        }

        if (showKeptOnly) {
            filteredProps = filteredProps.filter(p => p.keep_in_magellon);
        }

        // Group by subcategory
        const grouped: Record<string, Property[]> = {};
        filteredProps.forEach(prop => {
            if (!grouped[prop.subcategory]) {
                grouped[prop.subcategory] = [];
            }
            grouped[prop.subcategory].push(prop);
        });

        return grouped;
    };

    const groupedMicroscopeProperties = useMemo(() => groupPropertiesBySubcategory(microscopeProperties), [searchQuery, filterEditable, showKeptOnly]);
    const groupedCameraProperties = useMemo(() => groupPropertiesBySubcategory(cameraProperties), [searchQuery, filterEditable, showKeptOnly]);

    const addNewPreset = (type: 'microscope' | 'camera') => {
        const newPreset: Preset = {
            id: `${type}-preset-${Date.now()}`,
            name: `New ${type === 'microscope' ? 'Microscope' : 'Camera'} Preset`,
            description: 'Custom preset configuration',
            values: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        if (type === 'microscope') {
            setMicroscopePresets([...microscopePresets, newPreset]);
            setSelectedMicroscopePreset(newPreset.id);
        } else {
            setCameraPresets([...cameraPresets, newPreset]);
            setSelectedCameraPreset(newPreset.id);
        }
    };

    const duplicatePreset = (preset: Preset, type: 'microscope' | 'camera') => {
        const newPreset: Preset = {
            ...preset,
            id: `${type}-preset-${Date.now()}`,
            name: `${preset.name} (Copy)`,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        if (type === 'microscope') {
            setMicroscopePresets([...microscopePresets, newPreset]);
            setSelectedMicroscopePreset(newPreset.id);
        } else {
            setCameraPresets([...cameraPresets, newPreset]);
            setSelectedCameraPreset(newPreset.id);
        }
    };

    const deletePreset = (presetId: string, type: 'microscope' | 'camera') => {
        if (type === 'microscope') {
            setMicroscopePresets(microscopePresets.filter(p => p.id !== presetId));
            if (selectedMicroscopePreset === presetId) {
                setSelectedMicroscopePreset(microscopePresets[0]?.id || null);
            }
        } else {
            setCameraPresets(cameraPresets.filter(p => p.id !== presetId));
            if (selectedCameraPreset === presetId) {
                setSelectedCameraPreset(cameraPresets[0]?.id || null);
            }
        }
    };

    const renderPropertiesList = (groupedProperties: Record<string, Property[]>) => {
        const totalCount = Object.values(groupedProperties).reduce((a, props) => a + props.length, 0);

        if (totalCount === 0) {
            return (
                <div className="flex items-center justify-center h-64 text-muted-foreground">
                    No properties match your filters
                </div>
            );
        }

        return (
            <div className="space-y-4">
                <Accordion type="multiple" className="w-full" defaultValue={Object.keys(groupedProperties)}>
                    {Object.entries(groupedProperties).map(([subcategory, properties]) => (
                        <AccordionItem key={subcategory} value={subcategory} className="border rounded-lg bg-card mb-2">
                            <AccordionTrigger className="px-4 py-3 hover:bg-muted/50 hover:no-underline rounded-t-lg">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 rounded-lg bg-primary/10">
                                        {getSubcategoryIcon(subcategory)}
                                    </div>
                                    <span className="font-medium capitalize">{subcategory.replace(/_/g, ' ')}</span>
                                    <Badge variant="outline" className="ml-2">
                                        {properties.length}
                                    </Badge>
                                </div>
                            </AccordionTrigger>
                            <AccordionContent>
                                <div className="px-4 pb-4 space-y-2">
                                    {properties.map((prop) => (
                                        <div
                                            key={prop.id}
                                            className="flex items-center justify-between p-3 rounded-lg border bg-background/50 hover:bg-muted/50 hover:border-primary/30 transition-all"
                                        >
                                            <div className="flex items-center gap-3 flex-1">
                                                <div className="flex items-center gap-2">
                                                    {prop.editable ? (
                                                        <Unlock className="w-4 h-4 text-green-600" />
                                                    ) : (
                                                        <Lock className="w-4 h-4 text-muted-foreground" />
                                                    )}
                                                    <span className={cn(
                                                        "text-sm font-medium",
                                                        prop.editable ? "text-foreground" : "text-muted-foreground"
                                                    )}>
                                                        {formatPropertyName(prop.property_name)}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                {prop.keep_in_magellon && (
                                                    <Badge variant="secondary" className="text-xs">
                                                        <Check className="w-3 h-3 mr-1" />
                                                        Magellon
                                                    </Badge>
                                                )}
                                                <Badge variant="outline" className="text-xs font-mono">
                                                    {prop.property_name}
                                                </Badge>
                                                <Badge
                                                    variant={prop.editable ? "default" : "secondary"}
                                                    className="text-xs"
                                                >
                                                    {prop.editable ? 'Editable' : 'Read-only'}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </AccordionContent>
                        </AccordionItem>
                    ))}
                </Accordion>
            </div>
        );
    };

    const renderPresetCards = (presets: Preset[], selectedPreset: string | null, setSelectedPreset: (id: string) => void, type: 'microscope' | 'camera') => {
        return (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6">
                {presets.map((preset) => (
                    <Card
                        key={preset.id}
                        className={cn(
                            "p-4 cursor-pointer transition-all hover:shadow-md",
                            selectedPreset === preset.id ? "border-2 border-primary bg-primary/5" : "border"
                        )}
                        onClick={() => setSelectedPreset(preset.id)}
                    >
                        <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <BookmarkPlus className="w-4 h-4 text-primary" />
                                <h4 className="font-semibold text-sm">{preset.name}</h4>
                            </div>
                            <div className="flex items-center gap-1">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        duplicatePreset(preset, type);
                                    }}
                                >
                                    <Copy className="w-3 h-3" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-destructive"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deletePreset(preset.id, type);
                                    }}
                                >
                                    <Trash2 className="w-3 h-3" />
                                </Button>
                            </div>
                        </div>

                        <p className="text-xs text-muted-foreground mb-3">
                            {preset.description}
                        </p>

                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>
                                Updated: {new Date(preset.updatedAt).toLocaleDateString()}
                            </span>
                            {selectedPreset === preset.id && (
                                <Badge variant="default" className="text-xs">
                                    Active
                                </Badge>
                            )}
                        </div>
                    </Card>
                ))}
            </div>
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[95vw] max-h-[95vh] h-[95vh] flex flex-col p-0">
                <DialogHeader className="px-6 pt-6 pb-4 border-b">
                    <div className="flex items-center justify-between">
                        <div>
                            <DialogTitle className="text-2xl font-bold">Presets Manager</DialogTitle>
                            <p className="text-sm text-muted-foreground mt-1">
                                Configure and manage microscope and camera presets
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm">
                                <Upload className="w-4 h-4 mr-2" />
                                Import
                            </Button>
                            <Button variant="outline" size="sm">
                                <Download className="w-4 h-4 mr-2" />
                                Export
                            </Button>
                            <Button size="sm">
                                <Save className="w-4 h-4 mr-2" />
                                Save All
                            </Button>
                        </div>
                    </div>

                    {/* Filters */}
                    <div className="flex items-center gap-3 flex-wrap mt-4">
                        <div className="relative flex-1 min-w-[200px] max-w-md">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Search properties..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9 pr-9"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => setSearchQuery('')}
                                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>

                        <div className="flex items-center gap-2">
                            <Badge
                                variant={filterEditable === 'all' ? 'default' : 'outline'}
                                className="cursor-pointer"
                                onClick={() => setFilterEditable('all')}
                            >
                                All States
                            </Badge>
                            <Badge
                                variant={filterEditable === 'editable' ? 'default' : 'outline'}
                                className="cursor-pointer"
                                onClick={() => setFilterEditable('editable')}
                            >
                                <Unlock className="w-3 h-3 mr-1" />
                                Editable
                            </Badge>
                            <Badge
                                variant={filterEditable === 'readonly' ? 'default' : 'outline'}
                                className="cursor-pointer"
                                onClick={() => setFilterEditable('readonly')}
                            >
                                <Lock className="w-3 h-3 mr-1" />
                                Read-only
                            </Badge>
                        </div>

                        <div className="flex items-center gap-2">
                            <Switch
                                checked={showKeptOnly}
                                onCheckedChange={setShowKeptOnly}
                                id="kept-only-modal"
                            />
                            <label htmlFor="kept-only-modal" className="text-sm font-medium cursor-pointer">
                                Show Magellon Only
                            </label>
                        </div>
                    </div>
                </DialogHeader>

                {/* Main Content */}
                <div className="flex-1 overflow-hidden px-6 pb-6">
                    <Tabs defaultValue="microscope" className="h-full flex flex-col">
                        <TabsList className="mb-4">
                            <TabsTrigger value="microscope">
                                <Microscope className="w-4 h-4 mr-2" />
                                Microscope Presets ({microscopePresets.length})
                            </TabsTrigger>
                            <TabsTrigger value="camera">
                                <Camera className="w-4 h-4 mr-2" />
                                Camera Presets ({cameraPresets.length})
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="microscope" className="flex-1 overflow-auto mt-0">
                            <div className="space-y-6">
                                {/* Presets Section */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold">Microscope Presets</h3>
                                        <Button onClick={() => addNewPreset('microscope')} size="sm">
                                            <Plus className="w-4 h-4 mr-2" />
                                            New Preset
                                        </Button>
                                    </div>
                                    {renderPresetCards(microscopePresets, selectedMicroscopePreset, setSelectedMicroscopePreset, 'microscope')}
                                </div>

                                {/* Properties Section */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold">Available Properties</h3>
                                        <Badge variant="secondary">
                                            {Object.values(groupedMicroscopeProperties).reduce((a, props) => a + props.length, 0)} of {microscopeProperties.length} properties
                                        </Badge>
                                    </div>
                                    {renderPropertiesList(groupedMicroscopeProperties)}
                                </div>
                            </div>
                        </TabsContent>

                        <TabsContent value="camera" className="flex-1 overflow-auto mt-0">
                            <div className="space-y-6">
                                {/* Presets Section */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold">Camera Presets</h3>
                                        <Button onClick={() => addNewPreset('camera')} size="sm">
                                            <Plus className="w-4 h-4 mr-2" />
                                            New Preset
                                        </Button>
                                    </div>
                                    {renderPresetCards(cameraPresets, selectedCameraPreset, setSelectedCameraPreset, 'camera')}
                                </div>

                                {/* Properties Section */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold">Available Properties</h3>
                                        <Badge variant="secondary">
                                            {Object.values(groupedCameraProperties).reduce((a, props) => a + props.length, 0)} of {cameraProperties.length} properties
                                        </Badge>
                                    </div>
                                    {renderPropertiesList(groupedCameraProperties)}
                                </div>
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default PresetsEditor;
