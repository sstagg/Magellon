import React, { useRef, useEffect } from 'react';
import {
    Card,
    CardHeader,
    CardContent,
    Typography,
    Box,
    Paper,
    IconButton,
    Chip,
    alpha,
    useTheme
} from '@mui/material';
import {
    Navigation as NavigationIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon
} from '@mui/icons-material';
import { useMicroscopeStore } from './microscopeStore';

export const GridAtlas: React.FC = () => {
    const theme = useTheme();
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
        ctx.fillStyle = theme.palette.mode === 'dark' ? '#1a1a1a' : '#f5f5f5';
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
                ctx.strokeStyle = theme.palette.primary.main;
                ctx.lineWidth = 3;
                ctx.strokeRect(x-2, y-2, size+4, size+4);
                ctx.lineWidth = 1;
            }
        });

        // Draw current position
        if (atlasData.currentPosition) {
            const x = atlasData.currentPosition.x * scale + canvas.width/2 - 500*scale;
            const y = atlasData.currentPosition.y * scale + canvas.height/2 - 500*scale;

            ctx.strokeStyle = theme.palette.primary.main;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, 2 * Math.PI);
            ctx.stroke();
        }
    }, [atlasData, selectedSquare, atlasZoom, theme]);

    const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!atlasData) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (400 / rect.width);
        const y = (e.clientY - rect.top) * (400 / rect.height);

        // Find clicked square (simplified)
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
        <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardHeader
                title={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <NavigationIcon />
                        <Typography variant="h6">Grid Atlas</Typography>
                    </Box>
                }
                action={
                    <Chip
                        label={`${atlasData?.gridSquares?.length || 0} squares`}
                        size="small"
                        color="primary"
                        variant="outlined"
                    />
                }
                sx={{ pb: 1 }}
            />
            <CardContent sx={{ flex: 1, pt: 0 }}>
                {atlasData ? (
                    <Box sx={{ position: 'relative', height: '100%' }}>
                        <canvas
                            ref={canvasRef}
                            width={400}
                            height={400}
                            style={{
                                width: '100%',
                                height: '100%',
                                maxHeight: '400px',
                                backgroundColor: theme.palette.background.paper,
                                borderRadius: theme.shape.borderRadius,
                                cursor: 'crosshair',
                                border: `1px solid ${theme.palette.divider}`
                            }}
                            onClick={handleCanvasClick}
                        />

                        {/* Zoom Controls */}
                        <Box sx={{
                            position: 'absolute',
                            top: 8,
                            right: 8,
                            display: 'flex',
                            gap: 1
                        }}>
                            <IconButton
                                size="small"
                                onClick={() => setAtlasZoom(Math.min(atlasZoom * 1.2, 3))}
                                sx={{ backgroundColor: alpha(theme.palette.background.paper, 0.8) }}
                            >
                                <ZoomInIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                                size="small"
                                onClick={() => setAtlasZoom(Math.max(atlasZoom / 1.2, 0.5))}
                                sx={{ backgroundColor: alpha(theme.palette.background.paper, 0.8) }}
                            >
                                <ZoomOutIcon fontSize="small" />
                            </IconButton>
                        </Box>

                        {/* Square Info */}
                        {selectedSquare && (
                            <Paper
                                elevation={3}
                                sx={{
                                    position: 'absolute',
                                    bottom: 8,
                                    right: 8,
                                    p: 1,
                                    backgroundColor: alpha(theme.palette.background.paper, 0.9)
                                }}
                            >
                                <Typography variant="caption" display="block">
                                    Square: {selectedSquare.id}
                                </Typography>
                                <Typography variant="caption" display="block">
                                    Ice: {selectedSquare.iceThickness?.toFixed(0)} nm
                                </Typography>
                                <Typography variant="caption" display="block">
                                    Quality: {selectedSquare.quality}
                                </Typography>
                                <Typography variant="caption" display="block">
                                    Status: {selectedSquare.collected ? 'Collected' : 'Available'}
                                </Typography>
                            </Paper>
                        )}
                    </Box>
                ) : (
                    <Box sx={{
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        backgroundColor: 'action.hover',
                        borderRadius: 1,
                        minHeight: '300px'
                    }}>
                        <Typography color="text.secondary">
                            {isConnected ? 'Loading atlas...' : 'Connect to view atlas'}
                        </Typography>
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};