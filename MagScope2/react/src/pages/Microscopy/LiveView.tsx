import React, { useState, useEffect } from 'react';
import { Camera, BarChart3, Maximize2, Download, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { useMicroscopeStore } from './MicroscopeStore';

export const LiveView: React.FC = () => {
    const { lastImage, lastFFT, showFFT, isAcquiring, setShowFFT } = useMicroscopeStore();
    const [imageStats, setImageStats] = useState({
        mean: 2456.3,
        std: 234.5,
        min: 0,
        max: 4095,
        snr: 10.47
    });

    // Simulate live update
    useEffect(() => {
        if (isAcquiring) {
            const interval = setInterval(() => {
                setImageStats({
                    mean: 2400 + Math.random() * 200,
                    std: 220 + Math.random() * 30,
                    min: 0,
                    max: 4095,
                    snr: 10 + Math.random() * 2
                });
            }, 1000);
            return () => clearInterval(interval);
        }
    }, [isAcquiring]);

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Camera className="w-5 h-5" />
                        <h3 className="text-lg font-semibold">Live View</h3>
                    </div>
                    <div className="flex items-center gap-2">
                        {isAcquiring && (
                            <Badge variant="default" className="animate-pulse">
                                <div className="flex items-center gap-1">
                                    <div className="w-2 h-2 rounded-full bg-white" />
                                    Live
                                </div>
                            </Badge>
                        )}
                        <Button variant="ghost" size="icon" title="Maximize">
                            <Maximize2 className="w-4 h-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col pt-0 gap-3">
                {/* Image Display Area */}
                <div className="flex-1 min-h-0 relative">
                    <Tabs value={showFFT ? "fft" : "image"} onValueChange={(v) => setShowFFT(v === "fft")} className="h-full flex flex-col">
                        <TabsList className="grid w-full grid-cols-2">
                            <TabsTrigger value="image">Image</TabsTrigger>
                            <TabsTrigger value="fft">FFT</TabsTrigger>
                        </TabsList>

                        <TabsContent value="image" className="flex-1 mt-2">
                            <div className="w-full h-full bg-gradient-to-br from-gray-900 to-gray-800 rounded-lg border flex items-center justify-center relative overflow-hidden">
                                {lastImage ? (
                                    <img src={lastImage} alt="Live view" className="max-w-full max-h-full object-contain" />
                                ) : (
                                    <div className="text-center text-muted-foreground">
                                        <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                        <p>{isAcquiring ? 'Acquiring image...' : 'No image available'}</p>
                                        <p className="text-xs mt-1">Start acquisition to view live feed</p>
                                    </div>
                                )}

                                {/* Overlay Info */}
                                {isAcquiring && (
                                    <div className="absolute top-2 left-2 bg-background/80 backdrop-blur px-2 py-1 rounded text-xs space-y-0.5">
                                        <div className="font-mono">Frame: {Math.floor(Math.random() * 100)}/100</div>
                                        <div className="font-mono">Time: {(Math.random() * 10).toFixed(1)}s</div>
                                    </div>
                                )}

                                {/* Scale Bar */}
                                {lastImage && (
                                    <div className="absolute bottom-2 left-2 bg-background/80 backdrop-blur px-2 py-1 rounded text-xs">
                                        <div className="w-20 h-1 bg-white mb-1"></div>
                                        <div className="font-mono text-center">100 nm</div>
                                    </div>
                                )}
                            </div>
                        </TabsContent>

                        <TabsContent value="fft" className="flex-1 mt-2">
                            <div className="w-full h-full bg-gradient-to-br from-gray-900 to-gray-800 rounded-lg border flex items-center justify-center relative">
                                {lastFFT ? (
                                    <img src={lastFFT} alt="FFT" className="max-w-full max-h-full object-contain" />
                                ) : (
                                    <div className="text-center text-muted-foreground">
                                        <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                        <p>No FFT available</p>
                                        <p className="text-xs mt-1">Acquire an image to view FFT</p>
                                    </div>
                                )}

                                {/* Resolution Rings */}
                                {lastFFT && (
                                    <div className="absolute top-2 right-2 bg-background/80 backdrop-blur px-2 py-1 rounded text-xs space-y-0.5">
                                        <div className="font-mono">Resolution:</div>
                                        <div className="font-mono text-green-500">3.2 Å</div>
                                        <div className="font-mono text-yellow-500">5.0 Å</div>
                                        <div className="font-mono text-red-500">10.0 Å</div>
                                    </div>
                                )}
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>

                <Separator />

                {/* Statistics Panel */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium flex items-center gap-2">
                            <BarChart3 className="w-4 h-4" />
                            Image Statistics
                        </span>
                        <Button variant="ghost" size="sm">
                            <RefreshCw className="w-3 h-3" />
                        </Button>
                    </div>

                    <div className="grid grid-cols-5 gap-2">
                        <div className="bg-muted/50 rounded p-2 text-center">
                            <div className="text-xs text-muted-foreground">Mean</div>
                            <div className="text-sm font-mono font-semibold">{imageStats.mean.toFixed(1)}</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2 text-center">
                            <div className="text-xs text-muted-foreground">Std Dev</div>
                            <div className="text-sm font-mono font-semibold">{imageStats.std.toFixed(1)}</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2 text-center">
                            <div className="text-xs text-muted-foreground">Min</div>
                            <div className="text-sm font-mono font-semibold">{imageStats.min}</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2 text-center">
                            <div className="text-xs text-muted-foreground">Max</div>
                            <div className="text-sm font-mono font-semibold">{imageStats.max}</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2 text-center">
                            <div className="text-xs text-muted-foreground">SNR</div>
                            <div className="text-sm font-mono font-semibold">{imageStats.snr.toFixed(2)}</div>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" className="flex-1">
                            <Download className="w-3 h-3 mr-1" />
                            Save Image
                        </Button>
                        <Button variant="outline" size="sm" className="flex-1">
                            <Download className="w-3 h-3 mr-1" />
                            Save FFT
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
