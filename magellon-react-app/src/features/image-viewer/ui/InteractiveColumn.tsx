import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
    Box,
    Typography,
    Skeleton,
    Alert,
    Paper,
    CircularProgress,
    IconButton,
    Chip,
    Menu,
    MenuItem,
    ListItemIcon,
    ListItemText,
    TextField,
    Button,
    useTheme,
    alpha,
} from "@mui/material";
import {
    Clear,
    Refresh,
    ViewList,
    ViewModule,
    GridView,
    Folder,
} from "@mui/icons-material";
import {
    Search,
    ChevronRight,
    ChevronDown,
    ArrowDownAZ,
    ArrowUpAZ,
    AlertTriangle,
} from "lucide-react";
import type ImageInfoDto from "../../../entities/image/types.ts";
import { ImageColumn, withSelected } from "./ImageColumn.tsx";
import { ImageThumbnail } from "./ImageThumbnail.tsx";
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import { useDebouncedValue, useImageListQuery } from "../api/usePagedImagesHook.ts";
import { countActiveFilters, EMPTY_FILTER } from '../lib/imageFilter.ts';
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

/** The column's own name search. */
interface ColumnFilter {
    search?: string;
}

export const InteractiveColumn: React.FC<SlickImageColumnProps> = ({
                                                                       onImageClick,
                                                                       parentImage,
                                                                       sessionName,
                                                                       level,
                                                                       caption,
                                                                       width = 200,
                                                                       height = 700,
                                                                       showControls: _showControls = true,
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
    const [showSearch, setShowSearch] = useState(false);
    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

    const { imageColumns, imageFilter, setImageFilter } = useImageViewerStore();

    // Search, order and the session's filter are all applied by the server.
    const [filter, setFilter] = useState<ColumnFilter>({});
    const [order, setOrder] = useState<'asc' | 'desc'>('asc');
    const search = useDebouncedValue(filter.search?.trim() ?? '');
    const filtering = countActiveFilters(imageFilter) > 0;
    // What is selected in this column, also from outside it (an atlas tile).
    const columnSelection = imageColumns[level]?.selectedImage ?? null;

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
        isError,
        refetch,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
    } = useImageListQuery({
        sessionName,
        parentId,
        pageSize: DEFAULT_PAGE_SIZE,
        level,
        enabled: shouldLoad,
        // With a filter, the column keeps the images above a match so it can be reached.
        query: { filter: imageFilter, includeAncestors: true, search, order },
    });

    const allImages = useMemo(
        () => {
            const loaded = data?.pages?.flatMap(page => page.result ?? []) || [];
            return filtering || search ? loaded : withSelected(loaded, columnSelection);
        },
        [data, columnSelection, filtering, search]
    );

    const filteredImages = allImages;
    const total = data?.pages?.[0]?.total_count ?? allImages.length;

    useEffect(() => {
        setSelectedImageId(columnSelection?.oid || null);
    }, [columnSelection]);

    const activeFilterCount = filter.search ? 1 : 0;

    const handleImageClick = useCallback((image: ImageInfoDto) => {
        setSelectedImageId(image.oid || null);
        onImageClick(image, level);
    }, [onImageClick, level]);

    const handleRefresh = useCallback(() => {
        refetch();
    }, [refetch]);

    const handleFilterChange = useCallback((newFilter: Partial<ColumnFilter>) => {
        setFilter(prev => ({ ...prev, ...newFilter }));
    }, [setFilter]);

    const handleClearFilters = useCallback(() => {
        setFilter({});
        setImageFilter(EMPTY_FILTER);
    }, [setFilter, setImageFilter]);

    const handleMenuClose = useCallback(() => {
        setMenuAnchor(null);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = 0;
        }
    }, [search, order, imageFilter]);

    const getContentHeight = useCallback(() => {
        if (!isHorizontalMode) return '100%';
        const headerHeight = 36;
        const availableHeight = (height || 200) - headerHeight - 8;
        return Math.max(100, availableHeight);
    }, [isHorizontalMode, height]);

    const handleSortToggle = () => {
        setOrder(order === 'asc' ? 'desc' : 'asc');
    };

    const renderSlickHeader = () => (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            borderBottom: `1px solid ${theme.palette.divider}`,
            px: 1,
            py: 0.5,
            minHeight: 28,
            flexShrink: 0,
            backgroundColor: theme.palette.background.paper,
        }}>
            {showSearch ? (
                /* ── Search mode: inline input replaces label ── */
                (<>
                    <Box sx={{
                        position: 'relative',
                        flex: 1,
                        display: 'flex',
                        alignItems: 'center',
                    }}>
                        <Search size={12} style={{
                            position: 'absolute',
                            left: 6,
                            color: theme.palette.text.secondary,
                        }} />
                        <TextField
                            autoFocus
                            size="small"
                            placeholder="Filter..."
                            value={filter.search || ''}
                            onChange={(e) => handleFilterChange({ search: e.target.value })}
                            sx={{
                                flex: 1,
                                '& .MuiOutlinedInput-root': {
                                    height: 22,
                                    fontSize: '0.75rem',
                                    '& input': { py: 0, pl: 2.5, pr: 0.5 },
                                    '& fieldset': { borderColor: alpha(theme.palette.divider, 0.3) },
                                },
                            }}
                        />
                    </Box>
                    <IconButton
                        size="small"
                        onClick={() => { setShowSearch(false); handleFilterChange({ search: '' }); }}
                        sx={{ p: 0.25 }}
                    >
                        <Clear sx={{ fontSize: 12 }} />
                    </IconButton>
                </>)
            ) : (
                /* ── Normal mode: label + count + sort + search icons ── */
                (<>
                    {collapsible && (
                        <IconButton
                            size="small"
                            onClick={() => setIsCollapsed(!isCollapsed)}
                            sx={{ p: 0.15 }}
                        >
                            {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                        </IconButton>
                    )}
                    <Typography
                        variant="caption"
                        sx={{
                            fontWeight: 600,
                            fontSize: '0.75rem',
                            color: 'primary.main',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            minWidth: 0,
                        }}
                    >
                        {caption}
                    </Typography>
                    {total > 0 && (
                        <Chip
                            label={total}
                            size="small"
                            variant="outlined"
                            sx={{
                                height: 16,
                                fontSize: '0.6rem',
                                minWidth: 20,
                                '& .MuiChip-label': { px: 0.5 },
                                flexShrink: 0,
                            }}
                        />
                    )}
                    <Box sx={{ flex: 1 }} />
                    <IconButton
                        size="small"
                        onClick={handleSortToggle}
                        sx={{
                            p: 0.25,
                            color: theme.palette.text.secondary,
                            '&:hover': { color: theme.palette.text.primary },
                        }}
                        title={order === 'asc' ? 'Sort Z-A' : 'Sort A-Z'}
                    >
                        {order === 'desc'
                            ? <ArrowUpAZ size={14} />
                            : <ArrowDownAZ size={14} />
                        }
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => setShowSearch(true)}
                        sx={{
                            p: 0.25,
                            color: theme.palette.text.secondary,
                            '&:hover': { color: theme.palette.text.primary },
                        }}
                    >
                        <Search size={14} />
                    </IconButton>
                </>)
            )}
        </Box>
    );

    const renderImages = () => {
        if (isCollapsed) return null;

        if (allImages.length === 0 && (filtering || search)) {
            return (
                <Box sx={{ p: 2, textAlign: 'center' }} data-testid="column-no-match">
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
                        No images here match{search ? ` "${search}"` : ''}{filtering ? ' the filter' : ''}
                    </Typography>
                    <Button size="small" onClick={handleClearFilters}>Clear Filters</Button>
                </Box>
            );
        }

        if (displayMode === 'stack') {
            const contentHeight = getContentHeight();

            return (
                <ImageColumn
                    caption=""
                    images={data ?? null}
                    level={level}
                    direction={isHorizontalMode ? 'horizontal' : 'vertical'}
                    width={isHorizontalMode ? undefined : width}
                    height={isHorizontalMode ? (contentHeight as number) : undefined}
                    onImageClick={handleImageClick}
                    selected={columnSelection}
                    visibleImages={filteredImages}
                    onLoadMore={() => fetchNextPage()}
                    isLoadingMore={isFetchingNextPage}
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
                    <Folder sx={{ fontSize: 24, color: theme.palette.text.secondary }} />
                    <Typography
                        variant="caption"
                        sx={{
                            color: "text.secondary",
                            mt: 1,
                            textAlign: 'center'
                        }}>
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
                slotProps={{
                    paper: { sx: { minWidth: 160 } }
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
