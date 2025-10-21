import React from 'react';
import {
    Settings,
    Zap,
    Shield,
    Target,
    Sliders,
    RefreshCw,
    Camera,
    Save
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { useMicroscopeStore } from './MicroscopeStore';

interface AdvancedSettingsPanelProps {
    cameraConnected?: boolean;
    cameraLoading?: boolean;
    availableProperties?: string[];
    onRefreshCamera?: () => void;
    onOpenCameraSettings?: () => void;
}

export const AdvancedSettingsPanel: React.FC<AdvancedSettingsPanelProps> = ({
    cameraConnected = false,
    cameraLoading = false,
    availableProperties = [],
    onRefreshCamera,
    onOpenCameraSettings
}) => {
    const { advancedSettings, updateAdvancedSettings } = useMicroscopeStore();

    return (
        <div className="space-y-4">
            <Tabs defaultValue="acquisition" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="acquisition">Acquisition</TabsTrigger>
                    <TabsTrigger value="calibration">Calibration</TabsTrigger>
                    <TabsTrigger value="camera">Camera</TabsTrigger>
                </TabsList>

                {/* Acquisition Settings Tab */}
                <TabsContent value="acquisition" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Target className="w-4 h-4" />
                                    Advanced Acquisition Settings
                                </div>

                                <Separator />

                                {/* Drift Correction */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Drift Correction</Label>
                                        <Button
                                            variant={advancedSettings.driftCorrection ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => updateAdvancedSettings({ driftCorrection: !advancedSettings.driftCorrection })}
                                        >
                                            {advancedSettings.driftCorrection ? 'Enabled' : 'Disabled'}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Automatically correct for sample drift during acquisition
                                    </p>
                                </div>

                                <Separator />

                                {/* Auto Focus */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Auto Focus</Label>
                                        <Button
                                            variant={advancedSettings.autoFocus ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => updateAdvancedSettings({ autoFocus: !advancedSettings.autoFocus })}
                                        >
                                            {advancedSettings.autoFocus ? 'Enabled' : 'Disabled'}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Automatically adjust focus before each acquisition
                                    </p>
                                </div>

                                <Separator />

                                {/* Auto Stigmation */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Auto Stigmation</Label>
                                        <Button
                                            variant={advancedSettings.autoStigmation ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => updateAdvancedSettings({ autoStigmation: !advancedSettings.autoStigmation })}
                                        >
                                            {advancedSettings.autoStigmation ? 'Enabled' : 'Disabled'}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Automatically correct stigmation before acquisition
                                    </p>
                                </div>

                                <Separator />

                                {/* Dose Protection */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Dose Protection</Label>
                                        <Button
                                            variant={advancedSettings.doseProtection ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => updateAdvancedSettings({ doseProtection: !advancedSettings.doseProtection })}
                                        >
                                            {advancedSettings.doseProtection ? 'Enabled' : 'Disabled'}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Minimize electron dose exposure during targeting
                                    </p>
                                </div>

                                <Separator />

                                {/* Target Defocus */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Target Defocus</Label>
                                        <Badge variant="outline">{advancedSettings.targetDefocus.toFixed(1)} μm</Badge>
                                    </div>
                                    <Slider
                                        value={[advancedSettings.targetDefocus]}
                                        onValueChange={([value]) => updateAdvancedSettings({ targetDefocus: value })}
                                        min={-10}
                                        max={0}
                                        step={0.1}
                                        className="w-full"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Target defocus value for data acquisition
                                    </p>
                                </div>

                                <Separator />

                                {/* Defocus Range */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Defocus Range</Label>
                                        <Badge variant="outline">±{advancedSettings.defocusRange.toFixed(1)} μm</Badge>
                                    </div>
                                    <Slider
                                        value={[advancedSettings.defocusRange]}
                                        onValueChange={([value]) => updateAdvancedSettings({ defocusRange: value })}
                                        min={0}
                                        max={2}
                                        step={0.1}
                                        className="w-full"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Range for defocus variation during acquisition series
                                    </p>
                                </div>

                                <Separator />

                                {/* Beam Tilt Compensation */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Beam Tilt Compensation</Label>
                                        <Button
                                            variant={advancedSettings.beamTiltCompensation ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => updateAdvancedSettings({ beamTiltCompensation: !advancedSettings.beamTiltCompensation })}
                                        >
                                            {advancedSettings.beamTiltCompensation ? 'Enabled' : 'Disabled'}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Compensate for beam tilt during tomography
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Calibration Tab */}
                <TabsContent value="calibration" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Sliders className="w-4 h-4" />
                                    Calibration & Maintenance
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Image Calibrations</div>
                                    <div className="grid gap-2">
                                        <Button variant="outline" className="justify-start">
                                            <Target className="w-4 h-4 mr-2" />
                                            Pixel Size Calibration
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Zap className="w-4 h-4 mr-2" />
                                            Beam Intensity Calibration
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Camera className="w-4 h-4 mr-2" />
                                            Camera Gain Reference
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Shield className="w-4 h-4 mr-2" />
                                            Dark Reference
                                        </Button>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Alignment Calibrations</div>
                                    <div className="grid gap-2">
                                        <Button variant="outline" className="justify-start">
                                            <Target className="w-4 h-4 mr-2" />
                                            Gun Alignment
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Sliders className="w-4 h-4 mr-2" />
                                            Beam Alignment
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Settings className="w-4 h-4 mr-2" />
                                            Stigmation Calibration
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <RefreshCw className="w-4 h-4 mr-2" />
                                            Coma-free Alignment
                                        </Button>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Maintenance</div>
                                    <div className="grid gap-2">
                                        <Button variant="outline" className="justify-start">
                                            <Zap className="w-4 h-4 mr-2" />
                                            Flash Filament
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <RefreshCw className="w-4 h-4 mr-2" />
                                            Bake Column
                                        </Button>
                                        <Button variant="outline" className="justify-start">
                                            <Shield className="w-4 h-4 mr-2" />
                                            Vent/Pump Cycle
                                        </Button>
                                    </div>
                                </div>

                                <Separator />

                                <div className="bg-muted/30 p-3 rounded">
                                    <div className="text-xs text-muted-foreground space-y-1">
                                        <div className="font-medium">Last Calibration:</div>
                                        <div>Pixel Size: 2 hours ago</div>
                                        <div>Gain Reference: 1 day ago</div>
                                        <div>Dark Reference: 1 day ago</div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Camera Integration Tab */}
                <TabsContent value="camera" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Camera className="w-4 h-4" />
                                    Camera Integration
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <div className="text-sm font-medium">Camera Status</div>
                                            <div className="text-xs text-muted-foreground">
                                                {cameraConnected ? 'Connected and ready' : 'Not connected'}
                                            </div>
                                        </div>
                                        <Badge variant={cameraConnected ? 'default' : 'secondary'}>
                                            {cameraConnected ? 'Connected' : 'Disconnected'}
                                        </Badge>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Available Properties</div>
                                    <div className="p-3 bg-muted/30 rounded">
                                        <div className="text-sm font-mono">
                                            {availableProperties.length} properties available
                                        </div>
                                        {availableProperties.length > 0 && (
                                            <div className="text-xs text-muted-foreground mt-2">
                                                Includes hardware settings, acquisition parameters, and image processing options
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-2">
                                    <div className="text-sm font-medium mb-2">Camera Controls</div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <Button
                                            variant="outline"
                                            onClick={onRefreshCamera}
                                            disabled={cameraLoading}
                                        >
                                            <RefreshCw className={`w-4 h-4 mr-2 ${cameraLoading ? 'animate-spin' : ''}`} />
                                            Refresh Properties
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={onOpenCameraSettings}
                                            disabled={!cameraConnected}
                                        >
                                            <Settings className="w-4 h-4 mr-2" />
                                            Camera Settings
                                        </Button>
                                        <Button variant="outline" disabled={!cameraConnected}>
                                            <Camera className="w-4 h-4 mr-2" />
                                            Test Acquisition
                                        </Button>
                                        <Button variant="outline" disabled={!cameraConnected}>
                                            <Save className="w-4 h-4 mr-2" />
                                            Save Preset
                                        </Button>
                                    </div>
                                </div>

                                <Separator />

                                <div className="bg-muted/30 p-3 rounded space-y-2">
                                    <div className="text-xs font-medium">Camera Information</div>
                                    <div className="space-y-1 text-xs text-muted-foreground">
                                        <div>Model: DE-64 Direct Electron Detector</div>
                                        <div>Resolution: 4096 × 4096 pixels</div>
                                        <div>Pixel Size: 6.4 μm</div>
                                        <div>Max Frame Rate: 400 fps</div>
                                        <div>Bit Depth: 12-bit (Integrating) / 1-bit (Counting)</div>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-2">
                                    <div className="text-sm font-medium">Quick Presets</div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <Button variant="outline" size="sm" disabled={!cameraConnected}>
                                            High Speed Mode
                                        </Button>
                                        <Button variant="outline" size="sm" disabled={!cameraConnected}>
                                            High Quality Mode
                                        </Button>
                                        <Button variant="outline" size="sm" disabled={!cameraConnected}>
                                            Counting Mode
                                        </Button>
                                        <Button variant="outline" size="sm" disabled={!cameraConnected}>
                                            Cryo-EM Standard
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};
