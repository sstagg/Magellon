import React, { useRef, useEffect, useState } from 'react';
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
    useTheme,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Button
} from '@mui/material';
import {
    Navigation as NavigationIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    PhotoCamera as PhotoCameraIcon
} from '@mui/icons-material';
import { useMicroscopeStore } from './microscopeStore';

export const GridAtlas: React.FC = () => {
    const theme = useTheme();
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [selectedPoints, setSelectedPoints] = useState<Array<{x: number, y: number, id: string}>>([]);

    const {
        atlasData,
        selectedSquare,
        atlasZoom,
        availableAtlases, // Add this to your store
        selectedAtlas,    // Add this to your store
        setSelectedSquare,
        setAtlasZoom,
        setSelectedAtlas, // Add this to your store
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

        // Draw selected points (particle picking circles)
        selectedPoints.forEach(point => {
            ctx.strokeStyle = theme.palette.secondary.main;
            ctx.fillStyle = alpha(theme.palette.secondary.main, 0.2);
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(point.x, point.y, 8, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
        });
    }, [atlasData, selectedSquare, atlasZoom, selectedPoints, theme]);

    const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!atlasData) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (400 / rect.width);
        const y = (e.clientY - rect.top) * (400 / rect.height);

        // Check if holding Ctrl/Cmd for particle picking mode
        if (e.ctrlKey || e.metaKey) {
            // Add a new point for particle picking
            const newPoint = {
                x,
                y,
                id: `point_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
            };
            setSelectedPoints(prev => [...prev, newPoint]);
            return;
        }

        // Original square selection logic
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

    const handleAtlasChange = (event: React.ChangeEvent<{ value: unknown }>) => {
        const atlasName = event.target.value as string;
        const atlas = availableAtlases?.find(a => a.name === atlasName) || null;
        setSelectedAtlas(atlas);
        // Clear selected points when changing atlas
        setSelectedPoints([]);
    };

    const handleAcquireImages = () => {
        if (selectedPoints.length === 0) {
            alert('Please select points by Ctrl+clicking on the atlas');
            return;
        }

        // Convert canvas coordinates to real coordinates
        const realCoordinates = selectedPoints.map(point => ({
            id: point.id,
            x: (point.x - 200) / atlasZoom + 500, // Convert back to real coordinates
            y: (point.y - 200) / atlasZoom + 500,
            atlasId: selectedAtlas?.id
        }));

        console.log('Acquiring images at points:', realCoordinates);
        // Here you would call your actual acquire function
        // acquireImages(realCoordinates);

        // Optionally clear points after acquisition
        setSelectedPoints([]);
    };

    const handleClearPoints = () => {
        setSelectedPoints([]);
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
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                            label={`${selectedPoints.length} points`}
                            size="small"
                            color="secondary"
                            variant="outlined"
                        />
                        <Chip
                            label={`${atlasData?.gridSquares?.length || 0} squares`}
                            size="small"
                            color="primary"
                            variant="outlined"
                        />
                    </Box>
                }
                sx={{ pb: 1 }}
            />
            <CardContent sx={{ flex: 1, pt: 0, display: 'flex', flexDirection: 'column' }}>
                {/* Atlas Selector */}
                <Paper elevation={0} variant="outlined" sx={{ p: 2, borderRadius: 1, mb: 2 }}>
                    <FormControl fullWidth size="small" variant="outlined">
                        <InputLabel id="atlas-select-label">Atlas</InputLabel>
                        <Select
                            labelId="atlas-select-label"
                            id="atlas-select"
                            value={selectedAtlas?.name || ""}
                            label="Atlas"
                            onChange={handleAtlasChange}
                        >
                            <MenuItem value="">
                                <em>None</em>
                            </MenuItem>
                            {availableAtlases?.map((atlas) => (
                                <MenuItem key={atlas.id} value={atlas.name}>
                                    {atlas.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Paper>

                {/* Canvas Container - takes remaining space */}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    {atlasData ? (
                        <Box sx={{ position: 'relative', flex: 1 }}>
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
                            flex: 1,
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
                </Box>

                {/* Controls Section - Always visible at bottom */}
                <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                    {/* Instructions */}
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Hold Ctrl/Cmd + click to select acquisition points
                    </Typography>

                    {/* Action Buttons */}
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={handleClearPoints}
                            disabled={selectedPoints.length === 0}
                        >
                            Reset Points
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={<PhotoCameraIcon />}
                            onClick={handleAcquireImages}
                            disabled={selectedPoints.length === 0}
                        >
                            Acquire Images ({selectedPoints.length})
                        </Button>
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
};