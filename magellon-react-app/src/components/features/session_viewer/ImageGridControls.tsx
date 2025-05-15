import React from 'react';
import { Box, Slider, Typography, IconButton, Paper, Badge, Divider, Tooltip } from '@mui/material';
import { ZoomIn, ZoomOut, FilterList, ViewModule, ViewComfy } from '@mui/icons-material';

interface ImageGridControlsProps {
    zoom: number;
    onZoomChange: (value: number) => void;
    onFilterClick?: () => void;
    filterCount?: number;
}

/**
 * Controls for the flat image grid view including zoom and filter options
 */
export const ImageGridControls: React.FC<ImageGridControlsProps> = ({
                                                                        zoom,
                                                                        onZoomChange,
                                                                        onFilterClick,
                                                                        filterCount = 0
                                                                    }) => {
    const handleZoomChange = (event: Event, newValue: number | number[]) => {
        onZoomChange(newValue as number);
    };

    const increaseZoom = () => {
        onZoomChange(Math.min(zoom + 10, 100));
    };

    const decreaseZoom = () => {
        onZoomChange(Math.max(zoom - 10, 10));
    };

    const getColumnsPerRow = (zoom: number) => {
        if (zoom < 25) return "6-12";
        if (zoom < 50) return "3-6";
        if (zoom < 75) return "2-4";
        return "1-2";
    };

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                mb: 2,
                display: 'flex',
                alignItems: 'center',
                borderRadius: 2,
                flexWrap: 'wrap',
                gap: 1
            }}
        >
            <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                <Typography variant="body2" sx={{ mr: 1 }}>View:</Typography>
                {zoom < 50 ?
                    <Tooltip title="Compact view">
                        <ViewComfy fontSize="small" color="primary" />
                    </Tooltip> :
                    <Tooltip title="Large view">
                        <ViewModule fontSize="small" color="primary" />
                    </Tooltip>
                }
            </Box>

            <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="body2" sx={{ mr: 2 }}>Zoom:</Typography>

                <IconButton
                    size="small"
                    onClick={decreaseZoom}
                    disabled={zoom <= 10}
                >
                    <ZoomOut fontSize="small" />
                </IconButton>

                <Box sx={{ width: 100, mx: 2 }}>
                    <Slider
                        value={zoom}
                        onChange={handleZoomChange}
                        min={10}
                        max={100}
                        aria-labelledby="zoom-slider"
                        size="small"
                    />
                </Box>

                <IconButton
                    size="small"
                    onClick={increaseZoom}
                    disabled={zoom >= 100}
                >
                    <ZoomIn fontSize="small" />
                </IconButton>

                <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
                    {getColumnsPerRow(zoom)} columns
                </Typography>
            </Box>

            {onFilterClick && (
                <>
                    <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                    <Box sx={{ ml: 'auto' }}>
                        <Tooltip title="Filter images">
                            <IconButton onClick={onFilterClick} size="small">
                                <Badge badgeContent={filterCount} color="primary">
                                    <FilterList />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                    </Box>
                </>
            )}
        </Paper>
    );
};

export default ImageGridControls;