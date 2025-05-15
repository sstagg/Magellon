import React, { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Slider,
    Typography,
    Box,
    Divider,
    Chip,
    Stack
} from '@mui/material';
import { Close, FilterList } from '@mui/icons-material';
import ImageInfoDto from './ImageInfoDto';

export interface ImageFilter {
    name?: string;
    defocusMin?: number;
    defocusMax?: number;
    magnification?: number;
    pixelSizeMin?: number;
    pixelSizeMax?: number;
    hasChildren?: boolean;
}

interface ImageFilterDialogProps {
    open: boolean;
    onClose: () => void;
    onApplyFilter: (filter: ImageFilter) => void;
    currentFilter: ImageFilter;
    images: ImageInfoDto[] | null;
}

export const ImageFilterDialog: React.FC<ImageFilterDialogProps> = ({
                                                                        open,
                                                                        onClose,
                                                                        onApplyFilter,
                                                                        currentFilter,
                                                                        images = []
                                                                    }) => {
    const [filter, setFilter] = useState<ImageFilter>(currentFilter || {});

    // Calculate ranges for all numeric fields
    const ranges = images?.reduce((acc, image) => {
        // Update defocus range
        if (image.defocus !== undefined) {
            acc.defocusMin = Math.min(acc.defocusMin, image.defocus);
            acc.defocusMax = Math.max(acc.defocusMax, image.defocus);
        }

        // Update mag range
        if (image.mag !== undefined) {
            acc.magMin = Math.min(acc.magMin, image.mag);
            acc.magMax = Math.max(acc.magMax, image.mag);
        }

        // Update pixelSize range
        if (image.pixelSize !== undefined) {
            acc.pixelSizeMin = Math.min(acc.pixelSizeMin, image.pixelSize);
            acc.pixelSizeMax = Math.max(acc.pixelSizeMax, image.pixelSize);
        }

        return acc;
    }, {
        defocusMin: Infinity,
        defocusMax: -Infinity,
        magMin: Infinity,
        magMax: -Infinity,
        pixelSizeMin: Infinity,
        pixelSizeMax: -Infinity
    });

    // Handler for input changes
    const handleInputChange = (field: keyof ImageFilter, value: any) => {
        setFilter(prev => ({
            ...prev,
            [field]: value
        }));
    };

    // Handler for range changes
    const handleRangeChange = (field: string, newValue: number | number[]) => {
        const [min, max] = newValue as number[];
        setFilter(prev => ({
            ...prev,
            [`${field}Min`]: min,
            [`${field}Max`]: max
        }));
    };

    // Apply filter
    const applyFilter = () => {
        onApplyFilter(filter);
        onClose();
    };

    // Reset filter
    const resetFilter = () => {
        setFilter({});
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>
                <Box display="flex" alignItems="center">
                    <FilterList sx={{ mr: 1 }} />
                    Filter Images
                    <Box sx={{ ml: 'auto' }}>
                        <Button
                            onClick={onClose}
                            size="small"
                            color="inherit"
                            startIcon={<Close />}
                        >
                            Close
                        </Button>
                    </Box>
                </Box>
            </DialogTitle>

            <Divider />

            <DialogContent>
                <Stack spacing={3}>
                    {/* Name filter */}
                    <TextField
                        label="Name contains"
                        fullWidth
                        value={filter.name || ''}
                        onChange={(e) => handleInputChange('name', e.target.value)}
                        placeholder="Enter part of image name"
                    />

                    {/* Defocus range filter */}
                    {ranges && !isNaN(ranges.defocusMin) && !isNaN(ranges.defocusMax) && (
                        <Box>
                            <Typography gutterBottom>Defocus Range (μm)</Typography>
                            <Slider
                                value={[
                                    filter.defocusMin !== undefined ? filter.defocusMin : ranges.defocusMin,
                                    filter.defocusMax !== undefined ? filter.defocusMax : ranges.defocusMax
                                ]}
                                onChange={(_, newValue) => handleRangeChange('defocus', newValue)}
                                valueLabelDisplay="auto"
                                min={ranges.defocusMin}
                                max={ranges.defocusMax}
                                step={(ranges.defocusMax - ranges.defocusMin) / 100}
                            />
                            <Box display="flex" justifyContent="space-between">
                                <Typography variant="caption">{ranges.defocusMin.toFixed(2)}</Typography>
                                <Typography variant="caption">{ranges.defocusMax.toFixed(2)}</Typography>
                            </Box>
                        </Box>
                    )}

                    {/* Magnification filter */}
                    {ranges && !isNaN(ranges.magMin) && !isNaN(ranges.magMax) && (
                        <FormControl fullWidth>
                            <InputLabel>Magnification</InputLabel>
                            <Select
                                value={filter.magnification || ''}
                                onChange={(e) => handleInputChange('magnification', e.target.value)}
                                label="Magnification"
                            >
                                <MenuItem value="">Any</MenuItem>
                                {/* Create unique list of magnifications */}
                                {Array.from(new Set(images?.map(img => img.mag).filter(Boolean)))
                                    .sort((a, b) => a - b)
                                    .map(mag => (
                                        <MenuItem key={mag} value={mag}>{mag}x</MenuItem>
                                    ))
                                }
                            </Select>
                        </FormControl>
                    )}

                    {/* Pixel size range filter */}
                    {ranges && !isNaN(ranges.pixelSizeMin) && !isNaN(ranges.pixelSizeMax) && (
                        <Box>
                            <Typography gutterBottom>Pixel Size Range (Å/pixel)</Typography>
                            <Slider
                                value={[
                                    filter.pixelSizeMin !== undefined ? filter.pixelSizeMin : ranges.pixelSizeMin,
                                    filter.pixelSizeMax !== undefined ? filter.pixelSizeMax : ranges.pixelSizeMax
                                ]}
                                onChange={(_, newValue) => handleRangeChange('pixelSize', newValue)}
                                valueLabelDisplay="auto"
                                min={ranges.pixelSizeMin}
                                max={ranges.pixelSizeMax}
                                step={(ranges.pixelSizeMax - ranges.pixelSizeMin) / 100}
                            />
                            <Box display="flex" justifyContent="space-between">
                                <Typography variant="caption">{ranges.pixelSizeMin.toFixed(2)}</Typography>
                                <Typography variant="caption">{ranges.pixelSizeMax.toFixed(2)}</Typography>
                            </Box>
                        </Box>
                    )}

                    {/* Has children filter */}
                    <FormControl fullWidth>
                        <InputLabel>Has children</InputLabel>
                        <Select
                            value={filter.hasChildren === undefined ? '' : filter.hasChildren}
                            onChange={(e) => handleInputChange('hasChildren', e.target.value)}
                            label="Has children"
                        >
                            <MenuItem value="">Any</MenuItem>
                            <MenuItem value={true}>Yes</MenuItem>
                            <MenuItem value={false}>No</MenuItem>
                        </Select>
                    </FormControl>
                </Stack>

                {/* Active filters display */}
                {Object.keys(filter).length > 0 && (
                    <Box sx={{ mt: 3 }}>
                        <Typography variant="subtitle2" gutterBottom>Active Filters:</Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            {filter.name && (
                                <Chip
                                    label={`Name: ${filter.name}`}
                                    onDelete={() => handleInputChange('name', undefined)}
                                    size="small"
                                />
                            )}
                            {(filter.defocusMin !== undefined || filter.defocusMax !== undefined) && (
                                <Chip
                                    label={`Defocus: ${filter.defocusMin?.toFixed(2) || 'min'} - ${filter.defocusMax?.toFixed(2) || 'max'} μm`}
                                    onDelete={() => {
                                        handleInputChange('defocusMin', undefined);
                                        handleInputChange('defocusMax', undefined);
                                    }}
                                    size="small"
                                />
                            )}
                            {filter.magnification && (
                                <Chip
                                    label={`Mag: ${filter.magnification}x`}
                                    onDelete={() => handleInputChange('magnification', undefined)}
                                    size="small"
                                />
                            )}
                            {(filter.pixelSizeMin !== undefined || filter.pixelSizeMax !== undefined) && (
                                <Chip
                                    label={`Pixel Size: ${filter.pixelSizeMin?.toFixed(2) || 'min'} - ${filter.pixelSizeMax?.toFixed(2) || 'max'} Å`}
                                    onDelete={() => {
                                        handleInputChange('pixelSizeMin', undefined);
                                        handleInputChange('pixelSizeMax', undefined);
                                    }}
                                    size="small"
                                />
                            )}
                            {filter.hasChildren !== undefined && (
                                <Chip
                                    label={`Has Children: ${filter.hasChildren ? 'Yes' : 'No'}`}
                                    onDelete={() => handleInputChange('hasChildren', undefined)}
                                    size="small"
                                />
                            )}
                        </Stack>
                    </Box>
                )}
            </DialogContent>

            <Divider />

            <DialogActions>
                <Button onClick={resetFilter} color="inherit">
                    Reset All
                </Button>
                <Button onClick={applyFilter} variant="contained" color="primary">
                    Apply Filters
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ImageFilterDialog;