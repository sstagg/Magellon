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
import ImageInfoDto, { PagedImageResponse } from "../../../entities/image/types.ts";
import { ImageColumn } from "./ImageColumn.tsx";
import { ImageThumbnail } from "./ImageThumbnail.tsx";
import { InfiniteData } from "react-query";
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import { useImageListQuery } from "../api/usePagedImagesHook.ts";
import { useColumnFilter, type SortField } from '../lib/useColumnFilter.ts';
import { DEFAULT_PAGE_SIZE, TILE_WIDTH, COLUMN_HEIGHT_THRESHOLD } from '../constants';

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
        return height !== undefined && height !== COLUMN_HEIGHT_THRESHOLD;
    }, [height]);

    // Local state
    const [parentId, setParentId] = useState<string | null>(null);
    const [displayMode, setDisplayMode] = useState<DisplayMode>(initialDisplayMode);
    const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
    const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);
    const [isHeaderHovered, setIsHeaderHovered] = useState(false);
    const [showSearch, setShowSearch] = useState(false);
    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

    const { currentImage } = useImageViewerStore();

    const shouldLoad = useMemo(() => {
        if (level === 0) return sessionName !== '';
        return parentImage !== null && (parentImage.children_count || 0) > 0;
    }, [level, parentImage, sessionName]);

    useEffect(() => {
        const newParentId = level === 0 ? null : parentImage?.oid || null;

        if (newParentId !== parentId) {
            setParentId(newParentId);
            resetFilter();
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
        pageSize: DEFAULT_PAGE_SIZE,
        level,
        enabled: shouldLoad
    });

    const allImages = useMemo(
        () => data?.pages?.flatMap(page => page.result) || [],
        [data]
    );

    const { filter, setFilter, resetFilter, sortConfig, setSortConfig, filteredImages, totalCount } = useColumnFilter(allImages);

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
            ? Math.max(1, Math.floor((width || 800) / TILE_WIDTH))
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
                    gridTemplateRows: `repeat(${Math.ceil(filteredImages.length / gridCols)}, minmax(${TILE_WIDTH}px, 1fr))`
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