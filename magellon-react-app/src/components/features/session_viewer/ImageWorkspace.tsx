import {
    Box,
    ButtonGroup,
    FormControl,
    ImageList,
    ImageListItem,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    SelectChangeEvent,
    Tooltip,
    Typography,
    useTheme,
    Chip,
    Fab,
    IconButton,
    Collapse,
    Divider,
    Badge,
    alpha,
    Grid,
    Skeleton,
    useMediaQuery,
    Fade
} from "@mui/material";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "./ImageInfoDto.ts";
import {
    AccountTreeRounded,
    GridOnRounded,
    ViewColumn,
    Visibility,
    VisibilityOff,
    ExpandMore,
    ExpandLess,
    ZoomIn,
    ZoomOut,
    CenterFocusStrong,
    Fullscreen,
    FullscreenExit
} from "@mui/icons-material";
import {
    Map,
    Layers,
    Eye,
    Maximize2,
    Minimize2,
    ChevronLeft,
    ChevronRight, ChevronUp, ChevronDown
} from "lucide-react";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import AtlasViewer from "./AtlasViewer.tsx";
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import ColumnBrowser from "./ColumnBrowser.tsx";
import { ImageColumnState } from "../../panel/pages/ImagesPageView.tsx";
import { settings } from "../../../core/settings.ts";
import {useState, useEffect, useCallback, useRef} from "react";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface ImageNavigatorProps {
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void,
    selectedImage: ImageInfoDto | null,
    selectedSession: SessionDto | null,
    ImageColumns: ImageColumnState[],
    Atlases: AtlasImageDto[],
    Sessions: SessionDto[],
    OnSessionSelected: (event: SelectChangeEvent) => void
}

export const ImageWorkspace: React.FC<ImageNavigatorProps> = ({
                                                                  onImageClick,
                                                                  selectedImage,
                                                                  selectedSession,
                                                                  ImageColumns,
                                                                  Atlases,
                                                                  Sessions,
                                                                  OnSessionSelected
                                                              }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Get store state and actions
    const {
        isAtlasVisible,
        viewMode,
        currentAtlas,
        currentSession,
        toggleAtlasVisibility,
        setViewMode,
        setCurrentAtlas
    } = useImageViewerStore();

    // Local state for enhanced atlas viewer
    const [atlasZoom, setAtlasZoom] = useState(1);
    const [isAtlasFullscreen, setIsAtlasFullscreen] = useState(false);
    const [atlasExpanded, setAtlasExpanded] = useState(true);
    const [hoveredAtlas, setHoveredAtlas] = useState<string | null>(null);
    const [atlasLoading, setAtlasLoading] = useState<string | null>(null);

    // Get session name from store or props
    const sessionName = currentSession?.name || selectedSession?.name || '';

    // Initialize atlas on component mount
    useEffect(() => {
        if (Atlases && Atlases.length > 0 && !currentAtlas) {
            setCurrentAtlas(Atlases[0]);
        }
    }, [Atlases, currentAtlas, setCurrentAtlas]);

    const handleAtlasClick = (atlas: AtlasImageDto) => {
        setAtlasLoading(atlas.oid);
        setCurrentAtlas(atlas);
        // Simulate loading
        setTimeout(() => setAtlasLoading(null), 300);
    };

    // Navigate between atlases
    const navigateAtlas = (direction: 'prev' | 'next') => {
        if (!Atlases || Atlases.length === 0) return;

        const currentIndex = Atlases.findIndex(a => a.oid === currentAtlas?.oid);
        let newIndex = currentIndex;

        if (direction === 'next') {
            newIndex = (currentIndex + 1) % Atlases.length;
        } else {
            newIndex = currentIndex === 0 ? Atlases.length - 1 : currentIndex - 1;
        }

        handleAtlasClick(Atlases[newIndex]);
    };

    // Session selector component
    const renderSessionSelector = () => {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
                <FormControl fullWidth size="small" variant="outlined">
                    <InputLabel id="session-select-label">Session</InputLabel>
                    <Select
                        labelId="session-select-label"
                        id="session-select"
                        value={selectedSession?.name || ""}
                        label="Session"
                        onChange={OnSessionSelected}
                    >
                        <MenuItem value="">
                            <em>None</em>
                        </MenuItem>
                        {Sessions?.map((session) => (
                            <MenuItem key={session.Oid} value={session.name}>
                                {session.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Paper>
        );
    };

    // Enhanced view mode selector component
    const renderViewModeSelector = () => {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <ButtonGroup size="small">
                        <Tooltip title="Column View">
                            <IconButton
                                onClick={() => setViewMode('grid')}
                                color={viewMode === 'grid' ? 'primary' : 'default'}
                            >
                                <ViewColumn />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Tree View">
                            <IconButton
                                onClick={() => setViewMode('tree')}
                                color={viewMode === 'tree' ? 'primary' : 'default'}
                            >
                                <AccountTreeRounded />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Flat View">
                            <IconButton
                                onClick={() => setViewMode('flat')}
                                color={viewMode === 'flat' ? 'primary' : 'default'}
                            >
                                <GridOnRounded />
                            </IconButton>
                        </Tooltip>
                    </ButtonGroup>

                    <Chip
                        label={viewMode === 'grid' ? 'Columns' : viewMode === 'tree' ? 'Tree' : 'Flat'}
                        size="small"
                        color="primary"
                        variant="outlined"
                    />
                </Box>
            </Paper>
        );
    };

    // Enhanced Atlas viewer section
    // Enhanced Atlas viewer section - Replace the existing renderEnhancedAtlasSection function in ImageWorkspace.tsx
    const renderEnhancedAtlasSection = () => {
        // Additional state for vertical layout
        const [showZoomControls, setShowZoomControls] = useState(false);
        const [canScrollUp, setCanScrollUp] = useState(false);
        const [canScrollDown, setCanScrollDown] = useState(false);
        const thumbnailContainerRef = useRef<HTMLDivElement>(null);

        const THUMBNAIL_SIZE = isMobile ? 60 : 80;
        const VISIBLE_THUMBNAILS = isMobile ? 3 : 4;
        const SCROLL_AMOUNT = THUMBNAIL_SIZE + 8; // thumbnail size + gap

        // Check scroll availability
        const checkScrollAvailability = useCallback(() => {
            if (thumbnailContainerRef.current) {
                const { scrollTop, scrollHeight, clientHeight } = thumbnailContainerRef.current;
                setCanScrollUp(scrollTop > 0);
                setCanScrollDown(scrollTop + clientHeight < scrollHeight - 1);
            }
        }, []);

        useEffect(() => {
            checkScrollAvailability();
            const container = thumbnailContainerRef.current;
            if (container) {
                container.addEventListener('scroll', checkScrollAvailability);
                return () => container.removeEventListener('scroll', checkScrollAvailability);
            }
        }, [Atlases, atlasExpanded, checkScrollAvailability]);

        const scrollThumbnails = (direction: 'up' | 'down') => {
            if (thumbnailContainerRef.current) {
                const scrollAmount = direction === 'up' ? -SCROLL_AMOUNT : SCROLL_AMOUNT;
                thumbnailContainerRef.current.scrollBy({
                    top: scrollAmount,
                    behavior: 'smooth'
                });
            }
        };

        if (!isAtlasVisible || !Atlases || Atlases.length === 0) {
            return null;
        }

        const mainAtlasWidth = isMobile ? '100%' : 'calc(100% - 120px)';
        const thumbnailColumnWidth = isMobile ? '100%' : '100px';

        return (
            <Paper
                elevation={2}
                sx={{
                    mb: 2,
                    borderRadius: 2,
                    overflow: 'hidden',
                    background: `linear-gradient(135deg, ${alpha(theme.palette.background.paper, 0.95)} 0%, ${alpha(theme.palette.background.paper, 0.98)} 100%)`,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
            >
                {/* Compact Atlas Header */}
                <Box
                    sx={{
                        px: 2,
                        py: 1,
                        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        background: `linear-gradient(to right, ${alpha(theme.palette.primary.main, 0.03)} 0%, transparent 50%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        minHeight: 40
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Box
                            sx={{
                                width: 28,
                                height: 28,
                                borderRadius: 1.5,
                                background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: `0 2px 6px ${alpha(theme.palette.primary.main, 0.3)}`
                            }}
                        >
                            <Map size={14} color="white" />
                        </Box>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            Atlas Navigator
                        </Typography>
                        <Chip
                            icon={<Layers size={10} />}
                            label={`${Atlases.length}`}
                            size="small"
                            sx={{ height: 18, fontSize: '0.65rem', '& .MuiChip-icon': { marginLeft: '3px' } }}
                        />
                        {currentAtlas && (
                            <Chip
                                label={currentAtlas.name}
                                size="small"
                                color="primary"
                                variant="outlined"
                                sx={{ height: 18, fontSize: '0.65rem' }}
                            />
                        )}
                    </Box>

                    <IconButton
                        onClick={() => setAtlasExpanded(!atlasExpanded)}
                        size="small"
                        sx={{ p: 0.5 }}
                    >
                        {atlasExpanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                    </IconButton>
                </Box>

                {/* Atlas Content */}
                <Collapse in={atlasExpanded}>
                    <Box sx={{
                        p: 2,
                        display: 'flex',
                        flexDirection: isMobile ? 'column' : 'row',
                        gap: 2,
                        height: isMobile ? 'auto' : 320
                    }}>
                        {/* Vertical Atlas Thumbnails */}
                        <Box
                            sx={{
                                width: thumbnailColumnWidth,
                                height: isMobile ? 100 : '100%',
                                position: 'relative',
                                display: 'flex',
                                flexDirection: isMobile ? 'row' : 'column',
                                order: isMobile ? 2 : 1
                            }}
                        >
                            {/* Up Arrow - only show when scrollable */}
                            {!isMobile && Atlases.length > VISIBLE_THUMBNAILS && (
                                <Fade in={canScrollUp}>
                                    <IconButton
                                        size="small"
                                        onClick={() => scrollThumbnails('up')}
                                        sx={{
                                            position: 'absolute',
                                            top: -8,
                                            left: '50%',
                                            transform: 'translateX(-50%)',
                                            zIndex: 2,
                                            backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                            boxShadow: 2,
                                            '&:hover': {
                                                backgroundColor: theme.palette.background.paper,
                                            }
                                        }}
                                    >
                                        <ChevronUp />
                                    </IconButton>
                                </Fade>
                            )}

                            {/* Thumbnails Container */}
                            <Box
                                ref={thumbnailContainerRef}
                                sx={{
                                    flex: 1,
                                    display: 'flex',
                                    flexDirection: isMobile ? 'row' : 'column',
                                    gap: 1,
                                    overflowY: isMobile ? 'hidden' : 'auto',
                                    overflowX: isMobile ? 'auto' : 'hidden',
                                    scrollbarWidth: 'none',
                                    '&::-webkit-scrollbar': {
                                        display: 'none'
                                    },
                                    py: isMobile ? 0 : 1,
                                    px: isMobile ? 1 : 0,
                                    maxHeight: isMobile ? '100%' : `${THUMBNAIL_SIZE * VISIBLE_THUMBNAILS + (VISIBLE_THUMBNAILS - 1) * 8}px`
                                }}
                            >
                                {Atlases.map((atlas) => (
                                    <Paper
                                        key={atlas.oid}
                                        elevation={atlas.oid === currentAtlas?.oid ? 6 : 1}
                                        onClick={() => handleAtlasClick(atlas)}
                                        onMouseEnter={() => setHoveredAtlas(atlas.oid)}
                                        onMouseLeave={() => setHoveredAtlas(null)}
                                        sx={{
                                            position: 'relative',
                                            cursor: 'pointer',
                                            width: THUMBNAIL_SIZE,
                                            height: THUMBNAIL_SIZE,
                                            minWidth: THUMBNAIL_SIZE,
                                            minHeight: THUMBNAIL_SIZE,
                                            overflow: 'hidden',
                                            borderRadius: 1.5,
                                            border: atlas.oid === currentAtlas?.oid
                                                ? `2px solid ${theme.palette.primary.main}`
                                                : '2px solid transparent',
                                            transition: 'all 0.2s ease',
                                            transform: hoveredAtlas === atlas.oid ? 'scale(1.05)' : 'scale(1)',
                                            '&:hover': {
                                                boxShadow: `0 4px 12px ${alpha(theme.palette.common.black, 0.15)}`,
                                            }
                                        }}
                                    >
                                        {atlasLoading === atlas.oid ? (
                                            <Skeleton variant="rectangular" width="100%" height="100%" />
                                        ) : (
                                            <img
                                                src={`${BASE_URL}/atlas-image?name=${atlas?.name}&sessionName=${sessionName}`}
                                                alt={atlas.name}
                                                style={{
                                                    width: '100%',
                                                    height: '100%',
                                                    objectFit: 'cover'
                                                }}
                                                onError={(e) => {
                                                    e.currentTarget.style.display = 'none';
                                                }}
                                            />
                                        )}

                                        {/* Selection indicator */}
                                        {atlas.oid === currentAtlas?.oid && (
                                            <Box
                                                sx={{
                                                    position: 'absolute',
                                                    top: 2,
                                                    right: 2,
                                                    width: 18,
                                                    height: 18,
                                                    borderRadius: '50%',
                                                    backgroundColor: theme.palette.primary.main,
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    boxShadow: `0 2px 6px ${alpha(theme.palette.primary.main, 0.5)}`
                                                }}
                                            >
                                                <Eye size={10} color="white" />
                                            </Box>
                                        )}

                                        {/* Hover overlay with name */}
                                        <Fade in={hoveredAtlas === atlas.oid}>
                                            <Box
                                                sx={{
                                                    position: 'absolute',
                                                    bottom: 0,
                                                    left: 0,
                                                    right: 0,
                                                    background: `linear-gradient(to top, ${alpha(theme.palette.common.black, 0.8)} 0%, transparent 100%)`,
                                                    p: 0.5,
                                                }}
                                            >
                                                <Typography
                                                    variant="caption"
                                                    sx={{
                                                        color: 'white',
                                                        fontSize: '0.6rem',
                                                        fontWeight: 600,
                                                        display: 'block',
                                                        textAlign: 'center',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap',
                                                        lineHeight: 1.2
                                                    }}
                                                >
                                                    {atlas.name}
                                                </Typography>
                                            </Box>
                                        </Fade>
                                    </Paper>
                                ))}
                            </Box>

                            {/* Down Arrow - only show when scrollable */}
                            {!isMobile && Atlases.length > VISIBLE_THUMBNAILS && (
                                <Fade in={canScrollDown}>
                                    <IconButton
                                        size="small"
                                        onClick={() => scrollThumbnails('down')}
                                        sx={{
                                            position: 'absolute',
                                            bottom: -8,
                                            left: '50%',
                                            transform: 'translateX(-50%)',
                                            zIndex: 2,
                                            backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                            boxShadow: 2,
                                            '&:hover': {
                                                backgroundColor: theme.palette.background.paper,
                                            }
                                        }}
                                    >
                                        <ChevronDown />
                                    </IconButton>
                                </Fade>
                            )}
                        </Box>

                        {/* Main Atlas Viewer */}
                        <Paper
                            variant="outlined"
                            onMouseEnter={() => setShowZoomControls(true)}
                            onMouseLeave={() => setShowZoomControls(false)}
                            sx={{
                                position: 'relative',
                                flex: 1,
                                width: mainAtlasWidth,
                                height: isMobile ? 200 : '100%',
                                backgroundColor: '#000',
                                borderRadius: 2,
                                overflow: 'hidden',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                order: isMobile ? 1 : 2
                            }}
                        >
                            {currentAtlas && (
                                <>
                                    <Box
                                        sx={{
                                            transform: `scale(${atlasZoom})`,
                                            transition: 'transform 0.3s ease',
                                            transformOrigin: 'center'
                                        }}
                                    >
                                        <AtlasViewer
                                            imageMapJson={currentAtlas?.meta}
                                            finalWidth={isMobile ? 280 : 500}
                                            finalHeight={isMobile ? 180 : 280}
                                            name={currentAtlas?.name}
                                            backgroundColor="black"
                                            onImageClick={onImageClick}
                                        />
                                    </Box>

                                    {/* Zoom Controls - Show on Hover */}
                                    <Fade in={showZoomControls || isMobile}>
                                        <Box
                                            sx={{
                                                position: 'absolute',
                                                bottom: 12,
                                                right: 12,
                                                display: 'flex',
                                                gap: 0.5,
                                                backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                                backdropFilter: 'blur(10px)',
                                                borderRadius: 2,
                                                p: 0.5,
                                                boxShadow: `0 2px 8px ${alpha(theme.palette.common.black, 0.2)}`
                                            }}
                                        >
                                            <Tooltip title="Zoom Out">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => setAtlasZoom(prev => Math.max(0.5, prev - 0.1))}
                                                    sx={{ p: 0.5 }}
                                                >
                                                    <ZoomOut fontSize="small" />
                                                </IconButton>
                                            </Tooltip>

                                            <Chip
                                                label={`${Math.round(atlasZoom * 100)}%`}
                                                size="small"
                                                sx={{ minWidth: 50, height: 24, fontSize: '0.7rem' }}
                                            />

                                            <Tooltip title="Zoom In">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => setAtlasZoom(prev => Math.min(3, prev + 0.1))}
                                                    sx={{ p: 0.5 }}
                                                >
                                                    <ZoomIn fontSize="small" />
                                                </IconButton>
                                            </Tooltip>

                                            <Tooltip title="Reset Zoom">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => setAtlasZoom(1)}
                                                    sx={{ p: 0.5 }}
                                                >
                                                    <CenterFocusStrong fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </Box>
                                    </Fade>
                                </>
                            )}
                        </Paper>
                    </Box>
                </Collapse>
            </Paper>
        );
    };

    // Render the appropriate view based on viewMode
    const renderNavView = () => {
        switch (viewMode) {
            case 'grid':
                return renderGridView();
            case 'tree':
                return renderTreeView();
            case 'flat':
                return renderFlatView();
            default:
                return null;
        }
    };

    // Render the tree view
    const renderTreeView = () => {
        return (
            <HierarchyBrowser
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="Image Hierarchy"
            />
        );
    };

    // Render the grid/stacked view
    const renderGridView = () => {
        return (
            <ColumnBrowser
                imageColumns={ImageColumns}
                onImageClick={onImageClick}
                sessionName={sessionName}
                showSettings={true}
                initialSettingsCollapsed={false}
                height="100%"
            />
        );
    };

    // Render the flat view
    const renderFlatView = () => {
        return (
            <GridGallery
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="All Images"
            />
        );
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            position: 'relative'
        }}>
            {/* Header with session selector */}
            <Box sx={{
                flexShrink: 0,
                p: 1,
                borderBottom: `1px solid ${theme.palette.divider}`
            }}>
                <Box sx={{
                    display: 'flex',
                    gap: 2,
                    alignItems: 'center',
                    mb: 1
                }}>
                    {/* Session selector */}
                    <Box sx={{ flex: 1 }}>
                        {renderSessionSelector()}
                    </Box>
                </Box>

                {/* Enhanced Atlas section */}
                {renderEnhancedAtlasSection()}

                {/* View mode selector */}
                <Box>
                    {renderViewModeSelector()}
                </Box>
            </Box>

            {/* Main image navigation view */}
            <Box sx={{
                flex: 1,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
            }}>
                {renderNavView()}
            </Box>

            {/* Floating Action Button for Atlas Toggle */}
            <Fab
                color="primary"
                size="small"
                onClick={toggleAtlasVisibility}
                sx={{
                    position: 'absolute',
                    bottom: 16,
                    right: 16,
                    zIndex: 1000,
                    boxShadow: 3,
                    '&:hover': {
                        boxShadow: 6,
                        transform: 'scale(1.05)'
                    },
                    transition: 'all 0.2s ease-in-out'
                }}
                aria-label={isAtlasVisible ? "Hide Atlas" : "Show Atlas"}
            >
                {isAtlasVisible ? <VisibilityOff /> : <Visibility />}
            </Fab>
        </Box>
    );
};