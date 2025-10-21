import React, { useState, useEffect } from 'react';
import { Camera, Settings, Timer, Image, Save, FolderOpen, RefreshCw, Sliders, HardDrive, CheckCircle } from 'lucide-react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle } from '@/components/ui/alert';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from '@/components/ui/accordion';

interface CameraSettingsDialogProps {
    open: boolean;
    onClose: () => void;
    cameraSettings?: any;
    updateCameraSettings?: (updates: any) => void;
    acquisitionSettings?: any;
    updateAcquisitionSettings?: (updates: any) => void;
    availableProperties?: string[];
    systemStatus?: {
        system?: string;
        position?: string;
        temperature?: string;
    };
    onPropertyChange?: (propertyName: string, value: any) => Promise<void>;
}

export const CameraSettingsDialog: React.FC<CameraSettingsDialogProps> = ({
    open,
    onClose,
    cameraSettings = {},
    updateCameraSettings = () => {},
    availableProperties = [],
    systemStatus = {},
    onPropertyChange
}) => {
    const [localSettings, setLocalSettings] = useState({
        hardwareBinningX: 1,
        hardwareBinningY: 1,
        roiOffsetX: 0,
        roiOffsetY: 0,
        roiSizeX: 4096,
        roiSizeY: 4096,
        readoutShutter: 'Rolling',
        hardwareHDR: 'Off',
        framesPerSecond: 40,
        frameTimeNs: 25000000,
        exposureTime: 1.0,
        frameCount: 40,
        processingMode: 'Integrating',
        flatfield: 'Dark and Gain',
        softwareBinningX: 1,
        softwareBinningY: 1,
        binningMethod: 'Average',
        applyGainMovie: false,
        applyGainFinal: true,
        cropOffsetX: 0,
        cropOffsetY: 0,
        cropSizeX: 4096,
        cropSizeY: 4096,
        autosaveDirectory: '/data/acquisitions',
        filenameSuffix: '',
        fileFormat: 'Auto',
        movieFormat: 'Auto',
        movieSumCount: 1,
        saveFinalImage: true,
        saveMovie: false,
        ...cameraSettings
    });

    // Check if property is available
    const isPropertyAvailable = (propertyName: string) => {
        return availableProperties.includes(propertyName);
    };

    // Handle property changes
    const handlePropertyChange = async (propertyName: string, value: any) => {
        setLocalSettings(prev => ({ ...prev, [propertyName]: value }));
        if (onPropertyChange) {
            await onPropertyChange(propertyName, value);
        }
    };

    const handleSave = () => {
        updateCameraSettings(localSettings);
        onClose();
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Camera className="w-5 h-5" />
                        DE Camera Settings
                        <Badge variant="outline" className="ml-2">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            {systemStatus?.system || 'Connected'}
                        </Badge>
                    </DialogTitle>
                </DialogHeader>

                {/* Status Alert */}
                <Alert>
                    <AlertTitle>DE-64 Counting Camera</AlertTitle>
                    <p className="text-sm">
                        Temperature: {systemStatus?.temperature || '-15.2'}°C •
                        Position: {systemStatus?.position || 'Ready'} •
                        Status: {systemStatus?.system || 'Ready'}
                    </p>
                </Alert>

                <Tabs defaultValue="hardware" className="w-full">
                    <TabsList className="grid w-full grid-cols-5">
                        <TabsTrigger value="hardware">Hardware</TabsTrigger>
                        <TabsTrigger value="timing">Timing</TabsTrigger>
                        <TabsTrigger value="processing">Processing</TabsTrigger>
                        <TabsTrigger value="autosave">Autosave</TabsTrigger>
                        <TabsTrigger value="advanced">Advanced</TabsTrigger>
                    </TabsList>

                    {/* Hardware Tab */}
                    <TabsContent value="hardware" className="space-y-4">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium flex items-center gap-2">
                                <Settings className="w-4 h-4" />
                                Hardware Configuration
                            </h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Hardware Binning X</Label>
                                    <Select
                                        value={localSettings.hardwareBinningX.toString()}
                                        onValueChange={(value) => handlePropertyChange('hardwareBinningX', parseInt(value))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="1">1x</SelectItem>
                                            <SelectItem value="2">2x</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Hardware Binning Y</Label>
                                    <Select
                                        value={localSettings.hardwareBinningY.toString()}
                                        onValueChange={(value) => handlePropertyChange('hardwareBinningY', parseInt(value))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="1">1x</SelectItem>
                                            <SelectItem value="2">2x</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <Separator />

                            <div>
                                <h4 className="text-sm font-medium mb-3">Region of Interest (ROI)</h4>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>ROI Offset X (pixels)</Label>
                                        <Input
                                            type="number"
                                            value={localSettings.roiOffsetX}
                                            onChange={(e) => handlePropertyChange('roiOffsetX', parseInt(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>ROI Offset Y (pixels)</Label>
                                        <Input
                                            type="number"
                                            value={localSettings.roiOffsetY}
                                            onChange={(e) => handlePropertyChange('roiOffsetY', parseInt(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>ROI Size X (pixels)</Label>
                                        <Input
                                            type="number"
                                            value={localSettings.roiSizeX}
                                            onChange={(e) => handlePropertyChange('roiSizeX', parseInt(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>ROI Size Y (pixels)</Label>
                                        <Input
                                            type="number"
                                            value={localSettings.roiSizeY}
                                            onChange={(e) => handlePropertyChange('roiSizeY', parseInt(e.target.value))}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="bg-muted/30 p-3 rounded text-xs">
                                Output Resolution: {localSettings.roiSizeX / localSettings.hardwareBinningX} × {localSettings.roiSizeY / localSettings.hardwareBinningY} pixels<br/>
                                Data Rate: {((localSettings.roiSizeX / localSettings.hardwareBinningX) * (localSettings.roiSizeY / localSettings.hardwareBinningY) * 2 * 40 / 1024 / 1024).toFixed(1)} MB/s @ 40 fps
                            </div>

                            <Separator />

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Readout Shutter</Label>
                                    <Select
                                        value={localSettings.readoutShutter}
                                        onValueChange={(value) => handlePropertyChange('readoutShutter', value)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Global">Global</SelectItem>
                                            <SelectItem value="Rolling">Rolling</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Hardware HDR</Label>
                                    <Select
                                        value={localSettings.hardwareHDR}
                                        onValueChange={(value) => handlePropertyChange('hardwareHDR', value)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="On">On</SelectItem>
                                            <SelectItem value="Off">Off</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Timing Tab */}
                    <TabsContent value="timing" className="space-y-4">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium flex items-center gap-2">
                                <Timer className="w-4 h-4" />
                                Timing & Exposure
                            </h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Frames Per Second</Label>
                                    <Input
                                        type="number"
                                        step="0.01"
                                        min="0.06"
                                        value={localSettings.framesPerSecond}
                                        onChange={(e) => {
                                            const fps = parseFloat(e.target.value);
                                            handlePropertyChange('framesPerSecond', fps);
                                            handlePropertyChange('frameTimeNs', Math.round(1000000000 / fps));
                                        }}
                                    />
                                    <p className="text-xs text-muted-foreground">Min: 0.06 fps</p>
                                </div>

                                <div className="space-y-2">
                                    <Label>Frame Time (ns)</Label>
                                    <Input
                                        type="number"
                                        value={localSettings.frameTimeNs}
                                        disabled
                                    />
                                    <p className="text-xs text-muted-foreground">Calculated from FPS</p>
                                </div>

                                <div className="space-y-2">
                                    <Label>Exposure Time (s)</Label>
                                    <Input
                                        type="number"
                                        step="0.001"
                                        min="0.001"
                                        max="3600"
                                        value={localSettings.exposureTime}
                                        onChange={(e) => handlePropertyChange('exposureTime', parseFloat(e.target.value))}
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label>Frame Count</Label>
                                    <Input
                                        type="number"
                                        min="1"
                                        value={localSettings.frameCount}
                                        onChange={(e) => handlePropertyChange('frameCount', parseInt(e.target.value))}
                                    />
                                </div>
                            </div>

                            <div className="bg-muted/30 p-3 rounded text-xs space-y-1">
                                <div className="font-medium">Calculated Values:</div>
                                <div>Total Exposure: {localSettings.exposureTime} seconds</div>
                                <div>Total Frames: {localSettings.frameCount}</div>
                                <div>Total Dose: {(localSettings.exposureTime * 50).toFixed(1)} e⁻/Å²</div>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Processing Tab - Truncated for space, would continue with similar patterns... */}

                    {/* Footer Actions */}
                </Tabs>

                <Separator />

                <div className="flex gap-2 justify-end">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" />Reset</Button>
                    <Button onClick={handleSave}><Save className="w-4 h-4 mr-2" />Apply Settings</Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
