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
    Button,
    useTheme,
    alpha,
    Fade
} from "@mui/material";
import {
    Clear,
    MoreVert,
    Refresh,
    ViewList,
    ViewModule,
    GridView,
    Search,
    SortAsc,
    SortDesc,
    FilterList
} from "@mui/icons-material";
import {
    Folder,
    AlertTriangle,
    List as ListIcon,
    ChevronRight,
    ChevronDown
} from "lucide-react";
import ImageInfoDto, { PagedImageResponse } from "./ImageInfoDto.ts";
import { ImageColumn } from "./ImageColumn.tsx";
import { ImageThumbnail } from "./ImageThumbnail.tsx";
import { InfiniteData } from "react-query";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import { useImageListQuery } from "../../../services/api/usePagedImagesHook.ts";

interface ColumnFilter {
    search?: string;
    defocusMin?: number;
    defocusMax?: number;
    hasChildren?: boolean;
    magnification?: number;
}

type SortField = 'name' | 'defocus' | 'children_count' | 'mag' | 'pixelSize';
type SortDirection = 'asc' | 'desc';

interface SortConfig {
    field: SortField;
    direction: SortDirection;
}

type DisplayMode = 'stack' | 'grid' | 'list';

interface SlickImageColumnProps {
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    parentImage: ImageInfoDto | null;
    sessionName: string;
    caption: string;
    level: number;
    width?: number;
    height?: number;
    showControls?: boolean;
    initialDisplayMode?: DisplayMode;
    collapsible?: boolean;
    initialCollapsed?: boolean;
    sx?: object;
}

export const InteractiveColumn: React.FC<SlickImageColumnProps> = ({
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

    const isHorizontalMode = useMemo(() => {
        return height !== undefined && height !== 700;
    }, [height]);

    // Local state
    const [parentId, setParentId] = useState<string | null>(null);
    const [displayMode, setDisplayMode] = useState<DisplayMode>(initialDisplayMode);
    const [filter, setFilter] = useState<ColumnFilter>({});
    const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'name', direction: 'asc' });
    const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
    const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);
    const [isHeaderHovered, setIsHeaderHovered] = useState(false);
    const [showSearch, setShowSearch] = useState(false);

    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

    const { currentImage } = useImageViewerStore();

    const pageSize = 50;

    const shouldLoad = useMemo(() => {
        if (level === 0) return sessionName !== '';
        return parentImage !== null && (parentImage.children_count || 0) > 0;
    }, [level, parentImage, sessionName]);

    useEffect(() => {
        const newParentId = level === 0 ? null : parentImage?.oid || null;

        if (newParentId !== parentId) {
            setParentId(newParentId);
            setFilter({});
            setSelectedImageId(null);
        }
    }, [parentImage, level, parentId]);

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
    } = useImageListQuery({
        sessionName,
        parentId,
        pageSize,
        level,
        enabled: shouldLoad
    });

    const { filteredImages, totalCount } = useMemo(() => {
        const allImages = data?.pages?.flatMap(page => page.result) || [];

        let filtered = allImages.filter(image => {
            if (filter.search && image.name &&
                !image.name.toLowerCase().includes(filter.search.toLowerCase())) {
                return false;
            }

            if (filter.defocusMin !== undefined &&
                (image.defocus === undefined || image.defocus < filter.defocusMin)) {
                return false;
            }

            if (filter.defocusMax !== undefined &&
                (image.defocus === undefined || image.defocus > filter.defocusMax)) {
                return false;
            }

            if (filter.hasChildren !== undefined &&
                ((image.children_count || 0) > 0) !== filter.hasChildren) {
                return false;
            }

            if (filter.magnification !== undefined &&
                image.mag !== filter.magnification) {
                return false;
            }

            return true;
        });

        filtered.sort((a, b) => {
            let aValue: any = a[sortConfig.field];
            let bValue: any = b[sortConfig.field];

            if (aValue === undefined && bValue === undefined) return 0;
            if (aValue === undefined) return 1;
            if (bValue === undefined) return -1;

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

    useEffect(() => {
        if (currentImage && currentImage.level === level) {
            setSelectedImageId(currentImage.oid || null);
        }
    }, [currentImage, level]);

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
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = 0;
        }
    }, [filter, sortConfig]);

    const activeFilterCount = Object.values(filter).filter(val =>
        val !== undefined && val !== '' && val !== null
    ).length;

    const getContentHeight = useCallback(() => {
        if (!isHorizontalMode) return '100%';
        const headerHeight = 36;
        const availableHeight = (height || 200) - headerHeight - 8;
        return Math.max(100, availableHeight);
    }, [isHorizontalMode, height]);

    const renderSlickHeader = () => (
        <Box
            onMouseEnter={() => setIsHeaderHovered(true)}
            onMouseLeave={() => setIsHeaderHovered(false)}
            sx={{
                position: 'sticky',
                top: 0,
                zIndex: 2,
                backgroundColor: alpha(theme.palette.background.paper, 0.95),
                backdropFilter: 'blur(8px)',
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                transition: 'all 0.2s ease'
            }}
        >
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 1.5,
                py: 0.75,
                minHeight: 36,
                gap: 1
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, minWidth: 0 }}>
                    {collapsible && (
                        <IconButton
                            size="small"
                            onClick={() => setIsCollapsed(!isCollapsed)}
                            sx={{ p: 0.25 }}
                        >
                            {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                        </IconButton>
                    )}

                    <Typography
                        variant="subtitle2"
                        sx={{
                            fontWeight: 600,
                            fontSize: '0.8rem',
                            color: 'primary.main',
                            minWidth: 0,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            flexShrink: 0
                        }}
                    >
                        {caption}
                    </Typography>

                    <Chip
                        label={filteredImages.length}
                        size="small"
                        variant="outlined"
                        sx={{
                            height: 20,
                            fontSize: '0.65rem',
                            minWidth: 28,
                            '& .MuiChip-label': { px: 0.5 }
                        }}
                    />

                    {isHorizontalMode && !isCollapsed && (
                        <Fade in={showSearch || !!filter.search}>
                            <TextField
                                size="small"
                                placeholder="Search..."
                                value={filter.search || ''}
                                onChange={(e) => handleFilterChange({ search: e.target.value })}
                                sx={{
                                    ml: 1,
                                    flex: 1,
                                    maxWidth: 200,
                                    '& .MuiOutlinedInput-root': {
                                        height: 24,
                                        fontSize: '0.75rem',
                                        '& input': {
                                            py: 0.25,
                                            px: 1
                                        }
                                    }
                                }}
                                InputProps={{
                                    startAdornment: (
                                        <InputAdornment position="start" sx={{ ml: -0.5, mr: 0 }}>
                                            <Search size={12} />
                                        </InputAdornment>
                                    ),
                                    endAdornment: filter.search && (
                                        <InputAdornment position="end" sx={{ mr: -0.5 }}>
                                            <IconButton
                                                size="small"
                                                onClick={() => handleFilterChange({ search: '' })}
                                                sx={{ p: 0.15 }}
                                            >
                                                <Clear sx={{ fontSize: 14 }} />
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }}
                            />
                        </Fade>
                    )}
                </Box>

                <Fade in={isHeaderHovered || !!activeFilterCount}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {isHorizontalMode && (
                            <IconButton
                                size="small"
                                onClick={() => setShowSearch(!showSearch)}
                                sx={{ p: 0.25 }}
                            >
                                <Search fontSize="small" />
                            </IconButton>
                        )}

                        {activeFilterCount > 0 && (
                            <Badge badgeContent={activeFilterCount} color="primary">
                                <IconButton size="small" sx={{ p: 0.25 }}>
                                    <FilterList fontSize="small" />
                                </IconButton>
                            </Badge>
                        )}

                        <IconButton
                            size="small"
                            onClick={handleRefresh}
                            disabled={isFetching}
                            sx={{ p: 0.25 }}
                        >
                            <Refresh fontSize="small" />
                        </IconButton>

                        <IconButton size="small" onClick={handleMenuOpen} sx={{ p: 0.25 }}>
                            <MoreVert fontSize="small" />
                        </IconButton>
                    </Box>
                </Fade>
            </Box>

            {!isHorizontalMode && (
                <Fade in={!isCollapsed && (isHeaderHovered || !!filter.search)}>
                    <Box sx={{ px: 1.5, pb: 0.75 }}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search..."
                            value={filter.search || ''}
                            onChange={(e) => handleFilterChange({ search: e.target.value })}
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    height: 28,
                                    fontSize: '0.75rem'
                                }
                            }}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <Search size={14} />
                                    </InputAdornment>
                                ),
                                endAdornment: filter.search && (
                                    <InputAdornment position="end">
                                        <IconButton
                                            size="small"
                                            onClick={() => handleFilterChange({ search: '' })}
                                            sx={{ p: 0.25 }}
                                        >
                                            <Clear fontSize="small" />
                                        </IconButton>
                                    </InputAdornment>
                                )
                            }}
                        />
                    </Box>
                </Fade>
            )}
        </Box>
    );

    const renderImages = () => {
        if (isCollapsed) return null;

        if (displayMode === 'stack') {
            const contentHeight = getContentHeight();

            return (
                <ImageColumn
                    caption=""
                    images={data}
                    level={level}
                    direction={isHorizontalMode ? 'horizontal' : 'vertical'}
                    width={isHorizontalMode ? '100%' : width}
                    height={isHorizontalMode ? contentHeight : undefined}
                    onImageClick={handleImageClick}
                />
            );
        }

        const gridCols = isHorizontalMode
            ? Math.max(1, Math.floor((width || 800) / 120))
            : (displayMode === 'grid' ? 2 : 1);

        const imageSize = displayMode === 'grid' ? 'small' : 'medium';

        return (
            <Box sx={{
                display: 'grid',
                gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
                gridAutoFlow: isHorizontalMode ? 'column' : 'row',
                gap: 1,
                p: 1,
                ...(isHorizontalMode && {
                    overflowX: 'auto',
                    overflowY: 'hidden',
                    gridTemplateRows: `repeat(${Math.ceil(filteredImages.length / gridCols)}, minmax(120px, 1fr))`
                })
            }}>
                {filteredImages.map((image, index) => (
                    <ImageThumbnail
                        key={image.oid || index}
                        image={image}
                        onImageClick={handleImageClick}
                        level={level}
                        isSelected={selectedImageId === image.oid}
                        size={imageSize}
                        showMetadata={displayMode === 'list'}
                    />
                ))}

                {hasNextPage && (
                    <Box sx={{
                        ...(isHorizontalMode
                                ? {
                                    gridColumn: 'span 1',
                                    gridRow: 'span 1'
                                }
                                : { gridColumn: '1 / -1' }
                        ),
                        textAlign: 'center',
                        mt: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={() => fetchNextPage()}
                            disabled={isFetchingNextPage}
                            startIcon={isFetchingNextPage ? <CircularProgress size={16} /> : null}
                            sx={{ height: 28, fontSize: '0.75rem' }}
                        >
                            {isFetchingNextPage ? 'Loading...' : 'Load More'}
                        </Button>
                    </Box>
                )}
            </Box>
        );
    };

    const containerStyle = useMemo(() => {
        const baseStyle = {
            display: 'flex',
            flexDirection: 'column' as const,
            overflow: 'hidden',
        };

        if (isHorizontalMode) {
            return {
                ...baseStyle,
                width: '100%',
                minWidth: 0,
                maxWidth: '100%',
                height: height || 200,
            };
        } else {
            return {
                ...baseStyle,
                width: width || 200,
                height: height || 700,
            };
        }
    }, [isHorizontalMode, width, height]);

    if (isLoading) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    ...containerStyle,
                    ...sx
                }}
            >
                {renderSlickHeader()}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: isHorizontalMode ? 'row' : 'column', gap: 1, p: 1 }}>
                    {Array.from({ length: 5 }).map((_, index) => (
                        <Skeleton
                            key={index}
                            variant="rectangular"
                            width={isHorizontalMode ? 120 : undefined}
                            height={isHorizontalMode ? undefined : 48}
                            sx={{
                                borderRadius: 1,
                                ...(isHorizontalMode ? { flexShrink: 0 } : {})
                            }}
                        />
                    ))}
                </Box>
            </Paper>
        );
    }

    if (isError && error) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    ...containerStyle,
                    height: 'auto',
                    ...sx
                }}
            >
                {renderSlickHeader()}
                <Alert
                    severity="error"
                    icon={<AlertTriangle size={20} />}
                    action={
                        <IconButton size="small" onClick={handleRefresh}>
                            <Refresh fontSize="small" />
                        </IconButton>
                    }
                    sx={{ m: 1 }}
                >
                    Error loading images
                </Alert>
            </Paper>
        );
    }

    if (level > 0 && (!parentImage || (parentImage.children_count || 0) === 0)) {
        return (
            <Paper
                elevation={0}
                variant="outlined"
                sx={{
                    ...containerStyle,
                    height: 'auto',
                    ...sx
                }}
            >
                {renderSlickHeader()}
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: 120,
                    backgroundColor: alpha(theme.palette.primary.main, 0.02),
                    m: 1,
                    borderRadius: 1
                }}>
                    <Folder size={24} color={theme.palette.text.secondary} />
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                        {level === 0 ? "No images" : "Select parent"}
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
                ...containerStyle,
                border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                borderRadius: 2,
                backgroundColor: 'background.paper',
                ...sx
            }}
        >
            {renderSlickHeader()}

            <Box
                ref={scrollRef}
                sx={{
                    flex: 1,
                    height: isHorizontalMode ? getContentHeight() : '100%',
                    overflow: 'auto',
                    position: 'relative',
                    '&::-webkit-scrollbar': {
                        width: isHorizontalMode ? '8px' : '4px',
                        height: isHorizontalMode ? '8px' : '4px',
                    },
                    '&::-webkit-scrollbar-track': {
                        backgroundColor: alpha(theme.palette.divider, 0.1),
                        borderRadius: '4px',
                    },
                    '&::-webkit-scrollbar-thumb': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.3),
                        borderRadius: '4px',
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.5),
                        },
                    },
                    ...(isHorizontalMode && {
                        scrollbarGutter: 'stable',
                        '&::-webkit-scrollbar': {
                            display: 'block !important',
                        }
                    })
                }}
            >
                {renderImages()}
            </Box>

            <Menu
                anchorEl={menuAnchor}
                open={Boolean(menuAnchor)}
                onClose={handleMenuClose}
                dense
                PaperProps={{
                    sx: { minWidth: 160 }
                }}
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

                {activeFilterCount > 0 && (
                    <>
                        <MenuItem onClick={() => {
                            handleClearFilters();
                            handleMenuClose();
                        }}>
                            <ListItemIcon>
                                <Clear fontSize="small" />
                            </ListItemIcon>
                            <ListItemText>Clear Filters</ListItemText>
                        </MenuItem>
                    </>
                )}
            </Menu>
        </Paper>
    );
};

export default InteractiveColumn;