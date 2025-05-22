import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
    Box,
    Typography,
    Skeleton,
    Alert,
    Paper,
    CircularProgress,
    IconButton,
    Tooltip,
    Badge,
    Chip,
    Stack,
    Menu,
    MenuItem,
    ListItemIcon,
    ListItemText,
    TextField,
    InputAdornment,
    Divider,
    Button,
    useTheme,
    alpha
} from "@mui/material";
import {
    Clear,
    ExpandMore,
    GridView,
    MoreVert,
    Refresh,
    ViewList,
    ViewModule
} from "@mui/icons-material";
import {
    Folder,
    AlertTriangle,
    Search,
    SortAsc,
    SortDesc,
    List as ListIcon,
    Download,
    Info,
    ChevronRight,
    ChevronDown
} from "lucide-react";
import ImageInfoDto, { PagedImageResponse } from "./ImageInfoDto.ts";
import { ImagesStackComponent } from "./ImagesStackComponent.tsx";
import { ThumbImage } from "./ThumbImage.tsx";
import { InfiniteData } from "react-query";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import { usePagedImages } from "../../../services/api/usePagedImagesHook.ts";

// Enhanced filter options for the column
interface ColumnFilter {
    search?: string;
    defocusMin?: number;
    defocusMax?: number;
    hasChildren?: boolean;
    magnification?: number;
}

// Sort options
type SortField = 'name' | 'defocus' | 'children_count' | 'mag' | 'pixelSize';
type SortDirection = 'asc' | 'desc';

interface SortConfig {
    field: SortField;
    direction: SortDirection;
}

// Display modes for the column
type DisplayMode = 'stack' | 'grid' | 'list';

interface ImageColumnProps {
    /**
     * Callback when an image is clicked
     */
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    /**
     * Parent image that serves as filter for this column's images
     */
    parentImage: ImageInfoDto | null;
    /**
     * Current session name
     */
    sessionName: string;
    /**
     * Column caption/title
     */
    caption: string;
    /**
     * Hierarchical level of images in this column
     */
    level: number;
    /**
     * Width of the column
     */
    width?: number;
    /**
     * Height of the column
     */
    height?: number;
    /**
     * Whether to show column controls
     */
    showControls?: boolean;
    /**
     * Initial display mode
     */
    initialDisplayMode?: DisplayMode;
    /**
     * Whether the column can be collapsed
     */
    collapsible?: boolean;
    /**
     * Initial collapsed state
     */
    initialCollapsed?: boolean;
    /**
     * Custom styling
     */
    sx?: object;
}

/**
 * Enhanced ImageColumnComponent with filtering, sorting, search, and multiple display modes
 */
export const ImageColumnComponent: React.FC<ImageColumnProps> = ({
                                                                     onImageClick,
                                                                     parentImage,
                                                                     sessionName,
                                                                     level,
                                                                     caption,
                                                                     width = 200,
                                                                     height = 700,
                                                                     showControls = true,
                                                                     initialDisplayMode = 'stack',
                                                                     collapsible = false,
                                                                     initialCollapsed = false,
                                                                     sx = {}
                                                                 }) => {
    const theme = useTheme();
    const scrollRef = useRef<HTMLDivElement>(null);

    // Local state
    const [parentId, setParentId] = useState<string | null>(null);
    const [displayMode, setDisplayMode] = useState<DisplayMode>(initialDisplayMode);
    const [filter, setFilter] = useState<ColumnFilter>({});
    const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'name', direction: 'asc' });
    const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
    const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);

    // Menu states
    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
    const [sortMenuAnchor, setSortMenuAnchor] = useState<null | HTMLElement>(null);

    // Store integration
    const { currentImage } = useImageViewerStore();

    // Configuration
    const pageSize = 50;

    // Determine if loading should occur
    const shouldLoad = useMemo(() => {
        if (level === 0) return sessionName !== '';
        return parentImage !== null && (parentImage.children_count || 0) > 0;
    }, [level, parentImage, sessionName]);

    // Update parent ID when parent image changes
    useEffect(() => {
        const newParentId = level === 0 ? null : parentImage?.oid || null;

        if (newParentId !== parentId) {
            setParentId(newParentId);
            setFilter({}); // Reset filters when parent changes
            setSelectedImageId(null);
        }
    }, [parentImage, level, parentId]);

    // Fetch paged images from API
    const {
        data,
        error,
        isLoading,
        isSuccess,
        isError,
        refetch,
        fetchNextPage,
        hasNextPage,
        isFetching,
        isFetchingNextPage,
    } = usePagedImages({
        sessionName,
        parentId,
        pageSize,
        level,
        enabled: shouldLoad
    });

    // Get all images and apply filtering and sorting
    const { filteredImages, totalCount } = useMemo(() => {
        const allImages = data?.pages?.flatMap(page => page.result) || [];

        // Apply filters
        let filtered = allImages.filter(image => {
            // Search filter
            if (filter.search && image.name &&
                !image.name.toLowerCase().includes(filter.search.toLowerCase())) {
                return false;
            }

            // Defocus filter
            if (filter.defocusMin !== undefined &&
                (image.defocus === undefined || image.defocus < filter.defocusMin)) {
                return false;
            }

            if (filter.defocusMax !== undefined &&
                (image.defocus === undefined || image.defocus > filter.defocusMax)) {
                return false;
            }

            // Has children filter
            if (filter.hasChildren !== undefined &&
                ((image.children_count || 0) > 0) !== filter.hasChildren) {
                return false;
            }

            // Magnification filter
            if (filter.magnification !== undefined &&
                image.mag !== filter.magnification) {
                return false;
            }

            return true;
        });

        // Apply sorting
        filtered.sort((a, b) => {
            let aValue: any = a[sortConfig.field];
            let bValue: any = b[sortConfig.field];

            // Handle undefined values
            if (aValue === undefined && bValue === undefined) return 0;
            if (aValue === undefined) return 1;
            if (bValue === undefined) return -1;

            // Convert to strings for name comparison
            if (sortConfig.field === 'name') {
                aValue = aValue?.toString().toLowerCase() || '';
                bValue = bValue?.toString().toLowerCase() || '';
            }

            let comparison = 0;
            if (aValue < bValue) comparison = -1;
            if (aValue > bValue) comparison = 1;

            return sortConfig.direction === 'desc' ? -comparison : comparison;
        });

        return {
            filteredImages: filtered,
            totalCount: allImages.length
        };
    }, [data, filter, sortConfig]);

    // Update selected image based on store
    useEffect(() => {
        if (currentImage && currentImage.level === level) {
            setSelectedImageId(currentImage.oid || null);
        }
    }, [currentImage, level]);

    // Event handlers
    const handleImageClick = useCallback((image: ImageInfoDto) => {
        setSelectedImageId(image.oid || null);
        onImageClick(image, level);
    }, [onImageClick, level]);

    const handleRefresh = useCallback(() => {
        refetch();
    }, [refetch]);

    const handleFilterChange = useCallback((newFilter: Partial<ColumnFilter>) => {
        setFilter(prev => ({ ...prev, ...newFilter }));
    }, []);

    const handleSortChange = useCallback((field: SortField) => {
        setSortConfig(prev => ({
            field,
            direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc'
        }));
    }, []);

    const handleClearFilters = useCallback(() => {
        setFilter({});
    }, []);

    const handleMenuOpen = useCallback((event: React.MouseEvent<HTMLElement>) => {
        setMenuAnchor(event.currentTarget);
    }, []);

    const handleMenuClose = useCallback(() => {
        setMenuAnchor(null);
        setSortMenuAnchor(null);
    }, []);

    const handleSortMenuOpen = useCallback((event: React.MouseEvent<HTMLElement>) => {
        setSortMenuAnchor(event.currentTarget);
        setMenuAnchor(null);
    }, []);

    // Scroll to top when filters change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = 0;
        }
    }, [filter, sortConfig]);

    // Active filter count
    const activeFilterCount = Object.values(filter).filter(val =>
        val !== undefined && val !== '' && val !== null
    ).length;

    // Render header with controls
    const renderHeader = () => (
        <Paper
            elevation={0}
            variant="outlined"
            sx={{
                p: 1.5,
                borderRadius: 1,
                position: 'sticky',
                top: 0,
                zIndex: 2,
                backgroundColor: theme.palette.background.paper
            }}
        >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    {caption}
                </Typography>

                {showControls && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {collapsible && (
                            <IconButton
                                size="small"
                                onClick={() => setIsCollapsed(!isCollapsed)}
                            >
                                {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                            </IconButton>
                        )}

                        <Tooltip title="Refresh">
                            <IconButton size="small" onClick={handleRefresh} disabled={isFetching}>
                                <Refresh fontSize="small" />
                            </IconButton>
                        </Tooltip>

                        <Badge badgeContent={activeFilterCount} color="primary">
                            <IconButton size="small" onClick={handleMenuOpen}>
                                <MoreVert fontSize="small" />
                            </IconButton>
                        </Badge>
                    </Box>
                )}
            </Box>

            {/* Statistics */}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                    label={`${filteredImages.length} shown`}
                    size="small"
                    variant="outlined"
                    color="primary"
                />
                {totalCount !== filteredImages.length && (
                    <Chip
                        label={`of ${totalCount} total`}
                        size="small"
                        variant="outlined"
                        color="secondary"
                    />
                )}
                {sortConfig && (
                    <Chip
                        label={`Sort: ${sortConfig.field} ${sortConfig.direction}`}
                        size="small"
                        variant="filled"
                        color="info"
                        onDelete={() => setSortConfig({ field: 'name', direction: 'asc' })}
                    />
                )}
            </Box>

            {/* Search bar */}
            {showControls && !isCollapsed && (
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search images..."
                    value={filter.search || ''}
                    onChange={(e) => handleFilterChange({ search: e.target.value })}
                    sx={{ mt: 1 }}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <Search size={16} />
                            </InputAdornment>
                        ),
                        endAdornment: filter.search && (
                            <InputAdornment position="end">
                                <IconButton
                                    size="small"
                                    onClick={() => handleFilterChange({ search: '' })}
                                >
                                    <Clear fontSize="small" />
                                </IconButton>
                            </InputAdornment>
                        )
                    }}
                />
            )}
        </Paper>
    );

    // Render images based on display mode
    const renderImages = () => {
        if (isCollapsed) return null;

        if (displayMode === 'stack') {
            return (
                <ImagesStackComponent
                    caption=""
                    images={data} // Use original data for stack component
                    level={level}
                    onImageClick={handleImageClick}
                />
            );
        }

        // Grid or list mode
        const gridCols = displayMode === 'grid' ? 2 : 1;
        const imageSize = displayMode === 'grid' ? 'small' : 'medium';

        return (
            <Box sx={{
                display: 'grid',
                gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
                gap: 1,
                p: 1
            }}>
                {filteredImages.map((image, index) => (
                    <ThumbImage
                        key={image.oid || index}
                        image={image}
                        onImageClick={handleImageClick}
                        level={level}
                        isSelected={selectedImageId === image.oid}
                        size={imageSize}
                        showMetadata={displayMode === 'list'}
                    />
                ))}

                {/* Load more button */}
                {hasNextPage && (
                    <Box sx={{ gridColumn: '1 / -1', textAlign: 'center', mt: 1 }}>
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={() => fetchNextPage()}
                            disabled={isFetchingNextPage}
                            startIcon={isFetchingNextPage ? <CircularProgress size={16} /> : null}
                        >
                            {isFetchingNextPage ? 'Loading...' : 'Load More'}
                        </Button>
                    </Box>
                )}
            </Box>
        );
    };

    // Render loading state
    if (isLoading) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    width,
                    height,
                    p: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    ...sx
                }}
            >
                {renderHeader()}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                    {Array.from({ length: 3 }).map((_, index) => (
                        <Skeleton
                            key={index}
                            variant="rectangular"
                            height={60}
                            sx={{ borderRadius: 1 }}
                        />
                    ))}
                </Box>
            </Paper>
        );
    }

    // Render error state
    if (isError && error) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    width,
                    height: 'auto',
                    p: 1,
                    ...sx
                }}
            >
                {renderHeader()}
                <Alert
                    severity="error"
                    icon={<AlertTriangle size={24} />}
                    action={
                        <IconButton size="small" onClick={handleRefresh}>
                            <Refresh fontSize="small" />
                        </IconButton>
                    }
                >
                    Error loading images: {error.message}
                </Alert>
            </Paper>
        );
    }

    // Render empty state
    if (level > 0 && (!parentImage || (parentImage.children_count || 0) === 0)) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    width,
                    height: 'auto',
                    p: 1,
                    ...sx
                }}
            >
                {renderHeader()}
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: 200,
                    backgroundColor: alpha(theme.palette.primary.main, 0.05),
                    borderRadius: 1,
                    mt: 1
                }}>
                    <Folder size={32} color={theme.palette.text.secondary} />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                        {level === 0 ? "No images available" :
                            parentImage ? "No child images" : "Select an image"}
                    </Typography>
                </Box>
            </Paper>
        );
    }

    return (
        <Paper
            elevation={0}
            variant="outlined"
            sx={{
                width,
                height,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                ...sx
            }}
        >
            {renderHeader()}

            <Box
                ref={scrollRef}
                sx={{
                    flex: 1,
                    overflow: 'auto',
                    '&::-webkit-scrollbar': {
                        width: '6px',
                    },
                    '&::-webkit-scrollbar-track': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.05),
                    },
                    '&::-webkit-scrollbar-thumb': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                        borderRadius: '3px',
                    },
                }}
            >
                {renderImages()}
            </Box>

            {/* Context menu */}
            <Menu
                anchorEl={menuAnchor}
                open={Boolean(menuAnchor)}
                onClose={handleMenuClose}
                dense
            >
                <MenuItem onClick={() => {
                    setDisplayMode('stack');
                    handleMenuClose();
                }}>
                    <ListItemIcon>
                        <ViewList fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Stack View</ListItemText>
                </MenuItem>

                <MenuItem onClick={() => {
                    setDisplayMode('grid');
                    handleMenuClose();
                }}>
                    <ListItemIcon>
                        <GridView fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Grid View</ListItemText>
                </MenuItem>

                <MenuItem onClick={() => {
                    setDisplayMode('list');
                    handleMenuClose();
                }}>
                    <ListItemIcon>
                        <ViewModule fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>List View</ListItemText>
                </MenuItem>

                <Divider />

                <MenuItem onClick={handleSortMenuOpen}>
                    <ListItemIcon>
                        <SortAsc size={16} />
                    </ListItemIcon>
                    <ListItemText>Sort Options</ListItemText>
                </MenuItem>

                <MenuItem onClick={() => {
                    handleClearFilters();
                    handleMenuClose();
                }} disabled={activeFilterCount === 0}>
                    <ListItemIcon>
                        <Clear fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Clear Filters</ListItemText>
                </MenuItem>
            </Menu>

            {/* Sort menu */}
            <Menu
                anchorEl={sortMenuAnchor}
                open={Boolean(sortMenuAnchor)}
                onClose={handleMenuClose}
                dense
            >
                {[
                    { field: 'name' as SortField, label: 'Name' },
                    { field: 'defocus' as SortField, label: 'Defocus' },
                    { field: 'children_count' as SortField, label: 'Children Count' },
                    { field: 'mag' as SortField, label: 'Magnification' },
                    { field: 'pixelSize' as SortField, label: 'Pixel Size' }
                ].map(({ field, label }) => (
                    <MenuItem
                        key={field}
                        onClick={() => {
                            handleSortChange(field);
                            handleMenuClose();
                        }}
                    >
                        <ListItemIcon>
                            {sortConfig.field === field ? (
                                sortConfig.direction === 'asc' ?
                                    <SortAsc size={16} /> :
                                    <SortDesc size={16} />
                            ) : (
                                <Box sx={{ width: 16 }} />
                            )}
                        </ListItemIcon>
                        <ListItemText>{label}</ListItemText>
                    </MenuItem>
                ))}
            </Menu>
        </Paper>
    );
};

export default ImageColumnComponent;