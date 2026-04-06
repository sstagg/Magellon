import React, { useState } from 'react';
import {
    Box,
    Slider,
    Typography,
    IconButton,
    Paper,
    Badge,
    Divider,
    Tooltip,
    ButtonGroup,
    Chip,
    Menu,
    MenuItem,
    FormControlLabel,
    Switch,
    useTheme,
    useMediaQuery,
    Collapse,
    alpha
} from '@mui/material';
import {
    ZoomIn,
    ZoomOut,
    FilterList,
    ViewModule,
    ViewComfy,
    ViewList,
    GridView,
    Sort,
    MoreVert,
    Refresh,
    Settings,
    ExpandMore,
    ExpandLess,
    Fullscreen,
    FullscreenExit
} from '@mui/icons-material';
import { Eye, Grid3X3, Layers, Maximize2, Minimize2 } from 'lucide-react';

interface ImageGridControlsProps {
    zoom: number;
    onZoomChange: (value: number) => void;
    onFilterClick?: () => void;
    filterCount?: number;
    onSortChange?: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
    onViewModeChange?: (mode: 'grid' | 'list' | 'compact') => void;
    onRefresh?: () => void;
    showMetadata?: boolean;
    onMetadataToggle?: (show: boolean) => void;
    totalImages?: number;
    selectedImages?: number;
    isFullscreen?: boolean;
    onFullscreenToggle?: () => void;
    viewMode?: 'grid' | 'list' | 'compact';
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
}

/**
 * Enhanced controls for the image grid view with advanced features
 */
export const ImageGridControls: React.FC<ImageGridControlsProps> = ({
                                                                        zoom,
                                                                        onZoomChange,
                                                                        onFilterClick,
                                                                        filterCount = 0,
                                                                        onSortChange,
                                                                        onViewModeChange,
                                                                        onRefresh,
                                                                        showMetadata = true,
                                                                        onMetadataToggle,
                                                                        totalImages = 0,
                                                                        selectedImages = 0,
                                                                        isFullscreen = false,
                                                                        onFullscreenToggle,
                                                                        viewMode = 'grid',
                                                                        sortBy = 'name',
                                                                        sortOrder = 'asc'
                                                                    }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Local state
    const [sortMenuAnchor, setSortMenuAnchor] = useState<null | HTMLElement>(null);
    const [moreMenuAnchor, setMoreMenuAnchor] = useState<null | HTMLElement>(null);
    const [isExpanded, setIsExpanded] = useState(!isMobile);

    // Event handlers
    const handleZoomChange = (event: Event, newValue: number | number[]) => {
        onZoomChange(newValue as number);
    };

    const increaseZoom = () => {
        onZoomChange(Math.min(zoom + 10, 100));
    };

    const decreaseZoom = () => {
        onZoomChange(Math.max(zoom - 10, 10));
    };

    const handleSortMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setSortMenuAnchor(event.currentTarget);
    };

    const handleSortMenuClose = () => {
        setSortMenuAnchor(null);
    };

    const handleMoreMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setMoreMenuAnchor(event.currentTarget);
    };

    const handleMoreMenuClose = () => {
        setMoreMenuAnchor(null);
    };

    const handleSortSelection = (newSortBy: string) => {
        const newOrder = sortBy === newSortBy && sortOrder === 'asc' ? 'desc' : 'asc';
        onSortChange?.(newSortBy, newOrder);
        handleSortMenuClose();
    };

    const handleViewModeChange = (mode: 'grid' | 'list' | 'compact') => {
        onViewModeChange?.(mode);
    };

    // Helper functions
    const getColumnsPerRow = (zoom: number) => {
        if (zoom < 25) return "12+ columns";
        if (zoom < 50) return "6-8 columns";
        if (zoom < 75) return "3-4 columns";
        return "1-2 columns";
    };

    const getViewIcon = () => {
        switch (viewMode) {
            case 'list':
                return <ViewList fontSize="small" />;
            case 'compact':
                return <ViewComfy fontSize="small" />;
            default:
                return <ViewModule fontSize="small" />;
        }
    };

    const sortOptions = [
        { key: 'name', label: 'Name' },
        { key: 'date', label: 'Date Created' },
        { key: 'size', label: 'File Size' },
        { key: 'defocus', label: 'Defocus' },
        { key: 'magnification', label: 'Magnification' }
    ];

    return (
        <Paper
            elevation={2}
            sx={{
                p: isMobile ? 1.5 : 2,
                mb: 2,
                borderRadius: 3,
                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.02)}, ${alpha(theme.palette.secondary.main, 0.02)})`,
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                backdropFilter: 'blur(8px)',
                transition: 'all 0.3s ease'
            }}
        >
            {/* Header Row */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                mb: isExpanded ? 2 : 0
            }}>
                {/* Left side - Statistics */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Chip
                        icon={<Grid3X3 size={16} />}
                        label={`${totalImages} images`}
                        size="small"
                        variant="outlined"
                        color="primary"
                        sx={{ fontWeight: 500 }}
                    />
                    {selectedImages > 0 && (
                        <Chip
                            icon={<Eye size={16} />}
                            label={`${selectedImages} selected`}
                            size="small"
                            variant="filled"
                            color="secondary"
                            sx={{ fontWeight: 500 }}
                        />
                    )}
                    {filterCount > 0 && (
                        <Chip
                            icon={<FilterList fontSize="small" />}
                            label={`${filterCount} filters`}
                            size="small"
                            variant="filled"
                            color="warning"
                            sx={{ fontWeight: 500 }}
                        />
                    )}
                </Box>

                {/* Right side - Action buttons */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {!isMobile && (
                        <>
                            {/* View mode toggles */}
                            <ButtonGroup size="small" variant="outlined">
                                <Tooltip title="Grid View">
                                    <IconButton
                                        onClick={() => handleViewModeChange('grid')}
                                        color={viewMode === 'grid' ? 'primary' : 'default'}
                                        size="small"
                                    >
                                        <ViewModule fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="List View">
                                    <IconButton
                                        onClick={() => handleViewModeChange('list')}
                                        color={viewMode === 'list' ? 'primary' : 'default'}
                                        size="small"
                                    >
                                        <ViewList fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="Compact View">
                                    <IconButton
                                        onClick={() => handleViewModeChange('compact')}
                                        color={viewMode === 'compact' ? 'primary' : 'default'}
                                        size="small"
                                    >
                                        <ViewComfy fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </ButtonGroup>

                            <Divider orientation="vertical" flexItem />
                        </>
                    )}

                    {/* Fullscreen toggle */}
                    {onFullscreenToggle && (
                        <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
                            <IconButton onClick={onFullscreenToggle} size="small">
                                {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                            </IconButton>
                        </Tooltip>
                    )}

                    {/* Expand/Collapse toggle */}
                    <Tooltip title={isExpanded ? "Collapse" : "Expand"}>
                        <IconButton
                            onClick={() => setIsExpanded(!isExpanded)}
                            size="small"
                            sx={{
                                transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                transition: 'transform 0.3s ease'
                            }}
                        >
                            <ExpandMore />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* Expandable Controls */}
            <Collapse in={isExpanded}>
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 2,
                    pt: 1
                }}>
                    {/* View Mode Indicator */}
                    <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 'auto' }}>
                        <Typography variant="body2" sx={{ mr: 1, fontWeight: 500 }}>
                            View:
                        </Typography>
                        <Chip
                            icon={getViewIcon()}
                            label={viewMode.charAt(0).toUpperCase() + viewMode.slice(1)}
                            size="small"
                            variant="outlined"
                            color="primary"
                        />
                    </Box>

                    <Divider orientation="vertical" flexItem />

                    {/* Zoom Controls */}
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        minWidth: isMobile ? '100%' : 'auto',
                        flex: isMobile ? 1 : 'none'
                    }}>
                        <Typography variant="body2" sx={{ mr: 2, fontWeight: 500 }}>
                            Zoom:
                        </Typography>

                        <IconButton
                            size="small"
                            onClick={decreaseZoom}
                            disabled={zoom <= 10}
                            sx={{
                                bgcolor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.2) }
                            }}
                        >
                            <ZoomOut fontSize="small" />
                        </IconButton>

                        <Box sx={{ width: isMobile ? '100%' : 120, mx: 2 }}>
                            <Slider
                                value={zoom}
                                onChange={handleZoomChange}
                                min={10}
                                max={100}
                                aria-labelledby="zoom-slider"
                                size="small"
                                sx={{
                                    '& .MuiSlider-thumb': {
                                        boxShadow: 2
                                    },
                                    '& .MuiSlider-track': {
                                        background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`
                                    }
                                }}
                            />
                        </Box>

                        <IconButton
                            size="small"
                            onClick={increaseZoom}
                            disabled={zoom >= 100}
                            sx={{
                                bgcolor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.2) }
                            }}
                        >
                            <ZoomIn fontSize="small" />
                        </IconButton>

                        <Typography variant="caption" sx={{ ml: 2, color: 'text.secondary', minWidth: 80 }}>
                            {getColumnsPerRow(zoom)}
                        </Typography>
                    </Box>

                    {!isMobile && <Divider orientation="vertical" flexItem />}

                    {/* Action Controls */}
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        ml: isMobile ? 0 : 'auto',
                        mt: isMobile ? 1 : 0,
                        width: isMobile ? '100%' : 'auto',
                        justifyContent: isMobile ? 'space-between' : 'flex-end'
                    }}>
                        {/* Sort Menu */}
                        {onSortChange && (
                            <>
                                <Tooltip title="Sort images">
                                    <IconButton onClick={handleSortMenuOpen} size="small">
                                        <Badge
                                            badgeContent={sortOrder === 'desc' ? '↓' : '↑'}
                                            color="primary"
                                            sx={{ '& .MuiBadge-badge': { fontSize: '0.6rem' } }}
                                        >
                                            <Sort />
                                        </Badge>
                                    </IconButton>
                                </Tooltip>

                                <Menu
                                    anchorEl={sortMenuAnchor}
                                    open={Boolean(sortMenuAnchor)}
                                    onClose={handleSortMenuClose}
                                    transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                                    anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                                >
                                    {sortOptions.map((option) => (
                                        <MenuItem
                                            key={option.key}
                                            onClick={() => handleSortSelection(option.key)}
                                            selected={sortBy === option.key}
                                        >
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                                                {option.label}
                                                {sortBy === option.key && (
                                                    <Typography variant="caption" sx={{ ml: 2 }}>
                                                        {sortOrder === 'asc' ? '↑' : '↓'}
                                                    </Typography>
                                                )}
                                            </Box>
                                        </MenuItem>
                                    ))}
                                </Menu>
                            </>
                        )}

                        {/* Filter Button */}
                        {onFilterClick && (
                            <Tooltip title="Filter images">
                                <IconButton onClick={onFilterClick} size="small">
                                    <Badge badgeContent={filterCount} color="primary">
                                        <FilterList />
                                    </Badge>
                                </IconButton>
                            </Tooltip>
                        )}

                        {/* Refresh Button */}
                        {onRefresh && (
                            <Tooltip title="Refresh">
                                <IconButton onClick={onRefresh} size="small">
                                    <Refresh />
                                </IconButton>
                            </Tooltip>
                        )}

                        {/* More Options Menu */}
                        <Tooltip title="More options">
                            <IconButton onClick={handleMoreMenuOpen} size="small">
                                <MoreVert />
                            </IconButton>
                        </Tooltip>

                        <Menu
                            anchorEl={moreMenuAnchor}
                            open={Boolean(moreMenuAnchor)}
                            onClose={handleMoreMenuClose}
                            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                        >
                            {onMetadataToggle && (
                                <MenuItem>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={showMetadata}
                                                onChange={(e) => onMetadataToggle(e.target.checked)}
                                                size="small"
                                            />
                                        }
                                        label="Show Metadata"
                                    />
                                </MenuItem>
                            )}
                            <MenuItem onClick={handleMoreMenuClose}>
                                <Settings fontSize="small" sx={{ mr: 1 }} />
                                Settings
                            </MenuItem>
                        </Menu>
                    </Box>
                </Box>
            </Collapse>
        </Paper>
    );
};

export default ImageGridControls;