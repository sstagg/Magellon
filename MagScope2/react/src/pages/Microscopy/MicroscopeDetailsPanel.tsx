import React from 'react';
import {
    Microscope,
    Zap,
    Gauge,
    Thermometer,
    Wind,
    Droplets,
    Eye,
    Focus,
    Aperture,
    CircleDot,
    Activity
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { useMicroscopeStore } from './MicroscopeStore';

export const MicroscopeDetailsPanel: React.FC = () => {
    const { microscopeStatus, opticalSettings, stagePosition } = useMicroscopeStore();

    // Mock detailed data
    const detailedStatus = {
        gun: {
            emission: 4.2,
            extractionVoltage: 4500,
            filamentCurrent: 2.45,
            temperature: 2850,
            status: 'ready'
        },
        column: {
            c1Aperture: 150,
            c2Aperture: 70,
            objectiveAperture: 100,
            vacuumLevel: 8.5e-7,
            columnValve: 'open'
        },
        stage: {
            tiltRange: [-70, 70],
            maxSpeed: 50,
            accuracy: 0.001,
            stability: 0.002
        },
        alignment: {
            gunAlignment: 98.5,
            beamAlignment: 97.2,
            stigmation: 95.8,
            coma: 94.3
        },
        detectors: [
            { name: 'HAADF', status: 'active', signal: 85 },
            { name: 'BF', status: 'active', signal: 72 },
            { name: 'EELS', status: 'standby', signal: 0 },
            { name: 'EDX', status: 'standby', signal: 0 }
        ]
    };

    return (
        <div className="space-y-4">
            <Tabs defaultValue="status" className="w-full">
                <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="status">Status</TabsTrigger>
                    <TabsTrigger value="gun">Gun</TabsTrigger>
                    <TabsTrigger value="optics">Optics</TabsTrigger>
                    <TabsTrigger value="alignment">Alignment</TabsTrigger>
                </TabsList>

                {/* Status Tab */}
                <TabsContent value="status" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Microscope className="w-5 h-5 text-primary" />
                                        <span className="font-semibold">Titan Krios G4</span>
                                    </div>
                                    <Badge variant="default">Ready</Badge>
                                </div>

                                <Separator />

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-sm">
                                            <Zap className="w-4 h-4 text-yellow-500" />
                                            <span className="text-muted-foreground">High Tension</span>
                                        </div>
                                        <div className="text-2xl font-bold">300 kV</div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-sm">
                                            <Gauge className="w-4 h-4 text-blue-500" />
                                            <span className="text-muted-foreground">Emission</span>
                                        </div>
                                        <div className="text-2xl font-bold">{detailedStatus.gun.emission} μA</div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-sm">
                                            <Thermometer className="w-4 h-4 text-cyan-500" />
                                            <span className="text-muted-foreground">Cryo Temperature</span>
                                        </div>
                                        <div className="text-2xl font-bold">-192.3 °C</div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-sm">
                                            <Wind className="w-4 h-4 text-gray-500" />
                                            <span className="text-muted-foreground">Vacuum</span>
                                        </div>
                                        <div className="text-2xl font-bold">{detailedStatus.column.vacuumLevel.toExponential(1)} mbar</div>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Column Status</div>
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Column Valve</span>
                                            <Badge variant="outline" className="bg-green-500/10">Open</Badge>
                                        </div>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Autoloader</span>
                                            <Badge variant="outline" className="bg-green-500/10">Ready</Badge>
                                        </div>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Refrigerant Level</span>
                                            <div className="flex items-center gap-2">
                                                <Progress value={85} className="w-24 h-2" />
                                                <span className="font-mono">85%</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Gun Tab */}
                <TabsContent value="gun" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Zap className="w-4 h-4" />
                                    Electron Gun Parameters
                                </div>

                                <div className="grid gap-3">
                                    <div className="flex items-center justify-between p-3 bg-muted/30 rounded">
                                        <span className="text-sm text-muted-foreground">Emission Current</span>
                                        <span className="font-mono font-semibold">{detailedStatus.gun.emission} μA</span>
                                    </div>
                                    <div className="flex items-center justify-between p-3 bg-muted/30 rounded">
                                        <span className="text-sm text-muted-foreground">Extraction Voltage</span>
                                        <span className="font-mono font-semibold">{detailedStatus.gun.extractionVoltage} V</span>
                                    </div>
                                    <div className="flex items-center justify-between p-3 bg-muted/30 rounded">
                                        <span className="text-sm text-muted-foreground">Filament Current</span>
                                        <span className="font-mono font-semibold">{detailedStatus.gun.filamentCurrent} A</span>
                                    </div>
                                    <div className="flex items-center justify-between p-3 bg-muted/30 rounded">
                                        <span className="text-sm text-muted-foreground">Filament Temperature</span>
                                        <span className="font-mono font-semibold">{detailedStatus.gun.temperature} K</span>
                                    </div>
                                </div>

                                <Separator />

                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium">Gun Status</span>
                                    <Badge variant="default">Ready</Badge>
                                </div>

                                <div className="grid grid-cols-2 gap-2">
                                    <Button variant="outline" size="sm">
                                        <Zap className="w-3 h-3 mr-1" />
                                        Flash Filament
                                    </Button>
                                    <Button variant="outline" size="sm">
                                        <Activity className="w-3 h-3 mr-1" />
                                        Reset Gun
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Optics Tab */}
                <TabsContent value="optics" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Eye className="w-4 h-4" />
                                    Optical Configuration
                                </div>

                                <div className="grid gap-3">
                                    <div className="p-3 bg-muted/30 rounded space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-muted-foreground">Magnification</span>
                                            <span className="font-mono font-semibold">{opticalSettings.magnification.toLocaleString()}x</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/30 rounded space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-muted-foreground">Defocus</span>
                                            <span className="font-mono font-semibold">{opticalSettings.defocus.toFixed(1)} μm</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/30 rounded space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-muted-foreground">Spot Size</span>
                                            <span className="font-mono font-semibold">{opticalSettings.spotSize}</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/30 rounded space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-muted-foreground">Intensity</span>
                                            <span className="font-mono font-semibold">{(opticalSettings.intensity * 100).toFixed(3)}%</span>
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Apertures</div>
                                    <div className="grid gap-2">
                                        <div className="flex items-center justify-between p-2 bg-muted/20 rounded">
                                            <span className="text-sm">C1 Aperture</span>
                                            <span className="font-mono text-sm">{detailedStatus.column.c1Aperture} μm</span>
                                        </div>
                                        <div className="flex items-center justify-between p-2 bg-muted/20 rounded">
                                            <span className="text-sm">C2 Aperture</span>
                                            <span className="font-mono text-sm">{detailedStatus.column.c2Aperture} μm</span>
                                        </div>
                                        <div className="flex items-center justify-between p-2 bg-muted/20 rounded">
                                            <span className="text-sm">Objective Aperture</span>
                                            <span className="font-mono text-sm">{detailedStatus.column.objectiveAperture} μm</span>
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                    <div className="text-sm font-medium">Detectors</div>
                                    <div className="grid gap-2">
                                        {detailedStatus.detectors.map((detector) => (
                                            <div key={detector.name} className="flex items-center justify-between p-2 bg-muted/20 rounded">
                                                <div className="flex items-center gap-2">
                                                    <CircleDot className={`w-3 h-3 ${detector.status === 'active' ? 'text-green-500' : 'text-gray-400'}`} />
                                                    <span className="text-sm">{detector.name}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant={detector.status === 'active' ? 'default' : 'secondary'} className="text-xs">
                                                        {detector.status}
                                                    </Badge>
                                                    {detector.status === 'active' && (
                                                        <span className="font-mono text-sm">{detector.signal}%</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Alignment Tab */}
                <TabsContent value="alignment" className="space-y-4">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <Focus className="w-4 h-4" />
                                    Alignment Quality
                                </div>

                                <div className="space-y-3">
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Gun Alignment</span>
                                            <span className="font-mono font-semibold">{detailedStatus.alignment.gunAlignment}%</span>
                                        </div>
                                        <Progress value={detailedStatus.alignment.gunAlignment} className="h-2" />
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Beam Alignment</span>
                                            <span className="font-mono font-semibold">{detailedStatus.alignment.beamAlignment}%</span>
                                        </div>
                                        <Progress value={detailedStatus.alignment.beamAlignment} className="h-2" />
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Stigmation</span>
                                            <span className="font-mono font-semibold">{detailedStatus.alignment.stigmation}%</span>
                                        </div>
                                        <Progress value={detailedStatus.alignment.stigmation} className="h-2" />
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Coma-free Alignment</span>
                                            <span className="font-mono font-semibold">{detailedStatus.alignment.coma}%</span>
                                        </div>
                                        <Progress value={detailedStatus.alignment.coma} className="h-2" />
                                    </div>
                                </div>

                                <Separator />

                                <div className="space-y-2">
                                    <div className="text-sm font-medium mb-2">Stage Position</div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="p-2 bg-muted/20 rounded">
                                            <div className="text-xs text-muted-foreground">X</div>
                                            <div className="font-mono text-sm">{stagePosition.x.toFixed(3)} μm</div>
                                        </div>
                                        <div className="p-2 bg-muted/20 rounded">
                                            <div className="text-xs text-muted-foreground">Y</div>
                                            <div className="font-mono text-sm">{stagePosition.y.toFixed(3)} μm</div>
                                        </div>
                                        <div className="p-2 bg-muted/20 rounded">
                                            <div className="text-xs text-muted-foreground">Z</div>
                                            <div className="font-mono text-sm">{stagePosition.z.toFixed(3)} μm</div>
                                        </div>
                                        <div className="p-2 bg-muted/20 rounded">
                                            <div className="text-xs text-muted-foreground">α</div>
                                            <div className="font-mono text-sm">{stagePosition.alpha.toFixed(1)}°</div>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-2 mt-4">
                                    <Button variant="outline" size="sm">
                                        <Aperture className="w-3 h-3 mr-1" />
                                        Auto Align
                                    </Button>
                                    <Button variant="outline" size="sm">
                                        <Activity className="w-3 h-3 mr-1" />
                                        Reset All
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};
