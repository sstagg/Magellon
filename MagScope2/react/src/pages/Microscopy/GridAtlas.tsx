import React, { useRef, useEffect } from 'react';
import { Navigation, ZoomIn, ZoomOut } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useMicroscopeStore } from './MicroscopeStore';

export const GridAtlas: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    const {
        atlasData,
        selectedSquare,
        atlasZoom,
        setSelectedSquare,
        setAtlasZoom,
        isConnected
    } = useMicroscopeStore();

    useEffect(() => {
        if (!atlasData || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const scale = atlasZoom;

        // Clear canvas
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw grid squares
        atlasData.gridSquares.forEach(square => {
            const x = square.x * scale + canvas.width/2 - 500*scale;
            const y = square.y * scale + canvas.height/2 - 500*scale;
            const size = 90 * scale;

            // Set colors based on quality
            if (square.quality === 'good') {
                ctx.fillStyle = square.collected ? '#10b98144' : '#10b98122';
                ctx.strokeStyle = '#10b981';
            } else if (square.quality === 'medium') {
                ctx.fillStyle = square.collected ? '#f59e0b44' : '#f59e0b22';
                ctx.strokeStyle = '#f59e0b';
            } else {
                ctx.fillStyle = square.collected ? '#ef444444' : '#ef444422';
                ctx.strokeStyle = '#ef4444';
            }

            ctx.fillRect(x, y, size, size);
            ctx.strokeRect(x, y, size, size);

            // Highlight selected square
            if (selectedSquare?.id === square.id) {
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 3;
                ctx.strokeRect(x-2, y-2, size+4, size+4);
                ctx.lineWidth = 1;
            }
        });

        // Draw current position
        if (atlasData.currentPosition) {
            const x = atlasData.currentPosition.x * scale + canvas.width/2 - 500*scale;
            const y = atlasData.currentPosition.y * scale + canvas.height/2 - 500*scale;

            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, 2 * Math.PI);
            ctx.stroke();
        }
    }, [atlasData, selectedSquare, atlasZoom]);

    const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!atlasData) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (400 / rect.width);
        const y = (e.clientY - rect.top) * (400 / rect.height);

        const scale = atlasZoom;
        const clickedSquare = atlasData.gridSquares.find(square => {
            const squareX = square.x * scale + 400/2 - 500*scale;
            const squareY = square.y * scale + 400/2 - 500*scale;
            const size = 90 * scale;

            return x >= squareX && x <= squareX + size &&
                y >= squareY && y <= squareY + size;
        });

        if (clickedSquare) {
            setSelectedSquare(clickedSquare);
        }
    };

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Navigation className="w-5 h-5" />
                        <h3 className="text-lg font-semibold">Grid Atlas</h3>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline">{atlasData?.gridSquares?.length || 0} squares</Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col pt-0">
                <div className="flex-1 flex flex-col">
                    {atlasData ? (
                        <div className="relative flex-1">
                            <canvas
                                ref={canvasRef}
                                width={400}
                                height={400}
                                className="w-full h-full max-h-[400px] bg-background rounded border cursor-crosshair"
                                onClick={handleCanvasClick}
                            />

                            {/* Zoom Controls */}
                            <div className="absolute top-2 right-2 flex gap-1">
                                <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => setAtlasZoom(Math.min(atlasZoom * 1.2, 3))}
                                >
                                    <ZoomIn className="w-4 h-4" />
                                </Button>
                                <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => setAtlasZoom(Math.max(atlasZoom / 1.2, 0.5))}
                                >
                                    <ZoomOut className="w-4 h-4" />
                                </Button>
                            </div>

                            {/* Square Info */}
                            {selectedSquare && (
                                <div className="absolute bottom-2 right-2 bg-background/90 backdrop-blur border rounded p-2 text-xs">
                                    <div>Square: {selectedSquare.id}</div>
                                    <div>Ice: {selectedSquare.iceThickness?.toFixed(0)} nm</div>
                                    <div>Quality: {selectedSquare.quality}</div>
                                    <div>Status: {selectedSquare.collected ? 'Collected' : 'Available'}</div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex-1 flex items-center justify-center bg-muted/20 rounded min-h-[300px]">
                            <div className="text-muted-foreground">
                                {isConnected ? 'Loading atlas...' : 'Connect to view atlas'}
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};
