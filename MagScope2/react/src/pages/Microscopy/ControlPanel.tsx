import React, { useState } from 'react';
import {
    Settings,
    Move,
    Focus,
    Zap,
    Aperture,
    Target,
    Save,
    RotateCcw,
    Play,
    Pause
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { useMicroscopeStore } from './MicroscopeStore';

export const ControlPanel: React.FC = () => {
    const {
        stagePosition,
        opticalSettings,
        acquisitionSettings,
        presets,
        isAcquiring,
        updateStagePosition,
        updateOpticalSettings,
        updateAcquisitionSettings,
        applyPreset,
        setIsAcquiring
    } = useMicroscopeStore();

    const [activePreset, setActivePreset] = useState<number | null>(null);

    const handlePresetClick = (preset: any) => {
        applyPreset(preset);
        setActivePreset(preset.id);
        setTimeout(() => setActivePreset(null), 2000);
    };

    const handleAcquire = () => {
        setIsAcquiring(!isAcquiring);
    };

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Settings className="w-5 h-5" />
                        <h3 className="text-lg font-semibold">Control Panel</h3>
                    </div>
                    <Badge variant={isAcquiring ? "default" : "secondary"}>
                        {isAcquiring ? "Acquiring" : "Ready"}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
                <Tabs defaultValue="stage" className="w-full">
                    <TabsList className="grid w-full grid-cols-4">
                        <TabsTrigger value="stage">Stage</TabsTrigger>
                        <TabsTrigger value="optics">Optics</TabsTrigger>
                        <TabsTrigger value="camera">Camera</TabsTrigger>
                        <TabsTrigger value="presets">Presets</TabsTrigger>
                    </TabsList>

                    {/* Stage Control Tab */}
                    <TabsContent value="stage" className="space-y-4">
                        <div className="space-y-3">
                            <div className="flex items-center gap-2 text-sm font-medium">
                                <Move className="w-4 h-4" />
                                Stage Position
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs">X Position (μm)</Label>
                                    <Input
                                        type="number"
                                        value={stagePosition.x.toFixed(3)}
                                        onChange={(e) => updateStagePosition({ x: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Y Position (μm)</Label>
                                    <Input
                                        type="number"
                                        value={stagePosition.y.toFixed(3)}
                                        onChange={(e) => updateStagePosition({ y: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Z Position (μm)</Label>
                                    <Input
                                        type="number"
                                        value={stagePosition.z.toFixed(3)}
                                        onChange={(e) => updateStagePosition({ z: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Alpha (°)</Label>
                                    <Input
                                        type="number"
                                        value={stagePosition.alpha.toFixed(1)}
                                        onChange={(e) => updateStagePosition({ alpha: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                            </div>

                            <Separator />

                            <div className="grid grid-cols-3 gap-2">
                                <Button variant="outline" size="sm">
                                    <Target className="w-3 h-3 mr-1" />
                                    Go To
                                </Button>
                                <Button variant="outline" size="sm">
                                    <Save className="w-3 h-3 mr-1" />
                                    Save Pos
                                </Button>
                                <Button variant="outline" size="sm">
                                    <RotateCcw className="w-3 h-3 mr-1" />
                                    Reset
                                </Button>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Optics Tab */}
                    <TabsContent value="optics" className="space-y-4">
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 text-sm font-medium">
                                <Aperture className="w-4 h-4" />
                                Optical Settings
                            </div>

                            <div className="space-y-3">
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <Label className="text-xs">Magnification</Label>
                                        <span className="text-xs font-mono">{opticalSettings.magnification.toLocaleString()}x</span>
                                    </div>
                                    <Slider
                                        value={[Math.log10(opticalSettings.magnification)]}
                                        onValueChange={([value]) => updateOpticalSettings({ magnification: Math.round(Math.pow(10, value)) })}
                                        min={2}
                                        max={5.2}
                                        step={0.01}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <Label className="text-xs">Defocus (μm)</Label>
                                        <span className="text-xs font-mono">{opticalSettings.defocus.toFixed(1)}</span>
                                    </div>
                                    <Slider
                                        value={[opticalSettings.defocus]}
                                        onValueChange={([value]) => updateOpticalSettings({ defocus: value })}
                                        min={-10}
                                        max={0}
                                        step={0.1}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <Label className="text-xs">Spot Size</Label>
                                        <span className="text-xs font-mono">{opticalSettings.spotSize}</span>
                                    </div>
                                    <Slider
                                        value={[opticalSettings.spotSize]}
                                        onValueChange={([value]) => updateOpticalSettings({ spotSize: value })}
                                        min={1}
                                        max={11}
                                        step={1}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <Label className="text-xs">Intensity</Label>
                                        <span className="text-xs font-mono">{(opticalSettings.intensity * 100).toFixed(3)}%</span>
                                    </div>
                                    <Slider
                                        value={[opticalSettings.intensity * 100]}
                                        onValueChange={([value]) => updateOpticalSettings({ intensity: value / 100 })}
                                        min={0}
                                        max={0.1}
                                        step={0.001}
                                        className="w-full"
                                    />
                                </div>
                            </div>

                            <Separator />

                            <div className="flex gap-2">
                                <Button
                                    variant={opticalSettings.beamBlank ? "default" : "outline"}
                                    size="sm"
                                    className="flex-1"
                                    onClick={() => updateOpticalSettings({ beamBlank: !opticalSettings.beamBlank })}
                                >
                                    <Zap className="w-3 h-3 mr-1" />
                                    {opticalSettings.beamBlank ? "Unblank" : "Blank"} Beam
                                </Button>
                                <Button variant="outline" size="sm">
                                    <Focus className="w-3 h-3 mr-1" />
                                    Auto Focus
                                </Button>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Camera Tab */}
                    <TabsContent value="camera" className="space-y-4">
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 text-sm font-medium">
                                <Settings className="w-4 h-4" />
                                Acquisition Settings
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs">Exposure (ms)</Label>
                                    <Input
                                        type="number"
                                        value={acquisitionSettings.exposure}
                                        onChange={(e) => updateAcquisitionSettings({ exposure: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Binning</Label>
                                    <Input
                                        type="number"
                                        value={acquisitionSettings.binning}
                                        onChange={(e) => updateAcquisitionSettings({ binning: parseInt(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Frame Rate (fps)</Label>
                                    <Input
                                        type="number"
                                        value={acquisitionSettings.frameRate}
                                        onChange={(e) => updateAcquisitionSettings({ frameRate: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs">Frame Time (ms)</Label>
                                    <Input
                                        type="number"
                                        value={acquisitionSettings.frameTime}
                                        onChange={(e) => updateAcquisitionSettings({ frameTime: parseFloat(e.target.value) })}
                                        className="h-8"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label className="text-xs">Mode</Label>
                                <div className="flex gap-2">
                                    <Button
                                        variant={acquisitionSettings.mode === 'Counting' ? "default" : "outline"}
                                        size="sm"
                                        className="flex-1"
                                        onClick={() => updateAcquisitionSettings({ mode: 'Counting' })}
                                    >
                                        Counting
                                    </Button>
                                    <Button
                                        variant={acquisitionSettings.mode === 'Integrating' ? "default" : "outline"}
                                        size="sm"
                                        className="flex-1"
                                        onClick={() => updateAcquisitionSettings({ mode: 'Integrating' })}
                                    >
                                        Integrating
                                    </Button>
                                </div>
                            </div>

                            <Separator />

                            <Button
                                variant={isAcquiring ? "destructive" : "default"}
                                className="w-full"
                                onClick={handleAcquire}
                            >
                                {isAcquiring ? (
                                    <>
                                        <Pause className="w-4 h-4 mr-2" />
                                        Stop Acquisition
                                    </>
                                ) : (
                                    <>
                                        <Play className="w-4 h-4 mr-2" />
                                        Start Acquisition
                                    </>
                                )}
                            </Button>
                        </div>
                    </TabsContent>

                    {/* Presets Tab */}
                    <TabsContent value="presets" className="space-y-3">
                        <div className="text-sm font-medium">Quick Presets</div>
                        <div className="space-y-2">
                            {presets.map((preset) => (
                                <Button
                                    key={preset.id}
                                    variant={activePreset === preset.id ? "default" : "outline"}
                                    className="w-full justify-start"
                                    onClick={() => handlePresetClick(preset)}
                                >
                                    <div className="flex items-center justify-between w-full">
                                        <span className="font-medium">{preset.name}</span>
                                        <span className="text-xs text-muted-foreground">
                                            {preset.mag}x • {preset.defocus}μm
                                        </span>
                                    </div>
                                </Button>
                            ))}
                        </div>
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
};
