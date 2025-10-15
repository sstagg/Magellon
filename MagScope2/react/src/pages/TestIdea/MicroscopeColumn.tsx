import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MICROSCOPE_CONFIGS } from "./MicroscopeComponentConfig";
import type { MicroscopeComponent, MicroscopeConfig } from "./MicroscopeComponentConfig";
import MicroscopeComponentRenderer from './MicroscopeComponentRenderer';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

// Property Editor Component
const PropertyEditor: React.FC<{
    component: MicroscopeComponent;
    onUpdate: (updatedComponent: MicroscopeComponent) => void;
}> = ({ component, onUpdate }) => {
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
        <Card className="shadow-sm">
            <CardContent className="pt-6">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">Properties</h3>
                    <span className="text-xs text-muted-foreground">{component.id}</span>
                </div>

                <div className="flex flex-col gap-4">
                    {/* Basic Properties */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label className="text-xs">Name</Label>
                            <Input
                                value={editedComponent.name}
                                onChange={(e) => handlePropertyChange('name', e.target.value)}
                                className="h-8"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Type</Label>
                            <Select
                                value={editedComponent.type}
                                onValueChange={(value) => handlePropertyChange('type', value)}
                            >
                                <SelectTrigger className="h-8">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="source">Source</SelectItem>
                                    <SelectItem value="lens">Lens</SelectItem>
                                    <SelectItem value="aperture">Aperture</SelectItem>
                                    <SelectItem value="detector">Detector</SelectItem>
                                    <SelectItem value="camera">Camera</SelectItem>
                                    <SelectItem value="sample">Sample</SelectItem>
                                    <SelectItem value="electrode">Electrode</SelectItem>
                                    <SelectItem value="coils">Coils</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Width</Label>
                            <Input
                                type="number"
                                value={editedComponent.width}
                                onChange={(e) => handlePropertyChange('width', parseInt(e.target.value))}
                                className="h-8"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Height</Label>
                            <Input
                                type="number"
                                value={editedComponent.height}
                                onChange={(e) => handlePropertyChange('height', parseInt(e.target.value))}
                                className="h-8"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Color</Label>
                            <input
                                type="color"
                                value={editedComponent.baseColor}
                                onChange={(e) => handlePropertyChange('baseColor', e.target.value)}
                                className="w-full h-8 border border-input rounded cursor-pointer"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Shape</Label>
                            <Select
                                value={editedComponent.shape}
                                onValueChange={(value) => handlePropertyChange('shape', value)}
                            >
                                <SelectTrigger className="h-8">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="cylinder">Cylinder</SelectItem>
                                    <SelectItem value="lens">Lens</SelectItem>
                                    <SelectItem value="aperture">Aperture</SelectItem>
                                    <SelectItem value="detector">Detector</SelectItem>
                                    <SelectItem value="source">Source</SelectItem>
                                    <SelectItem value="camera">Camera</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs">Description</Label>
                        <Textarea
                            value={editedComponent.description || ''}
                            onChange={(e) => handlePropertyChange('description', e.target.value)}
                            rows={2}
                            className="text-xs"
                        />
                    </div>

                    {/* Specifications */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <Label className="text-xs">Specifications</Label>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={addSpecification}
                                className="h-6 px-2 text-xs"
                            >
                                + Add
                            </Button>
                        </div>
                        <div className="max-h-32 overflow-y-auto space-y-2">
                            {editedComponent.specifications && Object.entries(editedComponent.specifications).map(([key, value]) => (
                                <div key={key} className="flex gap-2 items-center">
                                    <Input
                                        value={key}
                                        placeholder="Key"
                                        onChange={(e) => {
                                            const newSpecs = { ...editedComponent.specifications };
                                            delete newSpecs[key];
                                            newSpecs[e.target.value] = value;
                                            handlePropertyChange('specifications', newSpecs);
                                        }}
                                        className="h-7 text-xs flex-1"
                                    />
                                    <Input
                                        value={String(value)}
                                        placeholder="Value"
                                        onChange={(e) => handlePropertyChange(`specifications.${key}`, e.target.value)}
                                        className="h-7 text-xs flex-1"
                                    />
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => removeSpecification(key)}
                                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                    >
                                        ×
                                    </Button>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

// Main microscope column component
const MicroscopeColumn: React.FC = () => {
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
        <div className="container max-w-7xl mx-auto py-6">
            <h1 className="text-4xl font-bold mb-6 text-center bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                {currentConfig.name}
            </h1>

            <div className="grid grid-cols-12 gap-6 h-[calc(100vh-200px)]">
                {/* Left Panel - Configuration */}
                <div className="col-span-3 h-full overflow-y-auto flex flex-col gap-4">
                    {/* Configuration Selector */}
                    <Card>
                        <CardContent className="pt-6">
                            <h3 className="text-base font-semibold mb-4">Microscope Configuration</h3>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <Label className="text-xs">Select Configuration</Label>
                                    <Select value={selectedConfig} onValueChange={setSelectedConfig}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="cryo-em-setup">Titan Krios with Apollo</SelectItem>
                                            <SelectItem value="stem-setup">JEOL ARM300F STEM</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* Microscope Info */}
                                <div className="border rounded-lg p-3 bg-muted/50 space-y-1">
                                    <div className="text-xs">
                                        <span className="font-medium">Voltage:</span> {currentConfig.voltage}
                                    </div>
                                    <div className="text-xs">
                                        <span className="font-medium">Manufacturer:</span> {currentConfig.manufacturer}
                                    </div>
                                    <div className="text-xs">
                                        <span className="font-medium">Components:</span> {currentConfig.components.length}
                                    </div>
                                </div>

                                {/* JSON Configuration Area */}
                                <div className="space-y-2">
                                    <Label className="text-xs">Load JSON Configuration:</Label>
                                    <Textarea
                                        rows={4}
                                        placeholder="Paste JSON configuration here..."
                                        onChange={(e) => {
                                            if (e.target.value.trim()) {
                                                loadConfigFromJSON(e.target.value);
                                            }
                                        }}
                                        className="text-xs font-mono"
                                    />
                                </div>

                                {/* Export Configuration */}
                                <Button
                                    className="w-full"
                                    onClick={() => {
                                        const configJson = JSON.stringify(currentConfig, null, 2);
                                        navigator.clipboard.writeText(configJson);
                                        alert('Configuration copied to clipboard!');
                                    }}
                                >
                                    Copy Configuration JSON
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Component List */}
                    <Card className="flex-1 min-h-0">
                        <CardContent className="pt-6 h-full flex flex-col">
                            <h3 className="text-base font-semibold mb-3">Components</h3>
                            <div className="flex-1 overflow-y-auto space-y-2">
                                {currentConfig.components.map((component) => (
                                    <button
                                        key={component.id}
                                        onClick={() => setSelectedId(selectedId === component.id ? null : component.id)}
                                        className={cn(
                                            "w-full border rounded p-3 text-left transition-colors",
                                            selectedId === component.id
                                                ? "bg-primary text-primary-foreground border-primary"
                                                : "bg-background hover:bg-muted"
                                        )}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="text-sm font-medium">
                                                {component.name}
                                            </div>
                                            <Badge variant={selectedId === component.id ? "secondary" : "outline"} className="text-xs">
                                                {component.type}
                                            </Badge>
                                        </div>
                                        <div className={cn(
                                            "text-xs mt-1",
                                            selectedId === component.id ? "text-primary-foreground/80" : "text-muted-foreground"
                                        )}>
                                            {component.description}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Middle Panel - Microscope Column Visualization */}
                <div className="col-span-6 h-full">
                    <Card className="h-full relative">
                        <CardContent className="h-full p-6">
                            {/* Vacuum chamber background */}
                            <div className="absolute inset-3 bg-gradient-to-b from-primary/5 via-secondary/5 to-primary/5 rounded-lg border border-border" />

                            <div className="relative z-10 flex flex-col items-center py-6 h-full overflow-y-auto">
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
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Right Panel - Properties */}
                <div className="col-span-3 h-full min-h-0 overflow-y-auto">
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
                        <Card className="h-full flex items-center justify-center">
                            <CardContent>
                                <p className="text-sm text-muted-foreground text-center">
                                    Select a component from the list to view and edit its properties
                                </p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MicroscopeColumn;
