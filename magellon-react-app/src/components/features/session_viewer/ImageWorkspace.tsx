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
    useMediaQuery
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
    ChevronRight
} from "lucide-react";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import AtlasViewer from "./AtlasViewer.tsx";
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import ColumnBrowser from "./ColumnBrowser.tsx";
import { ImageColumnState } from "../../panel/pages/ImagesPageView.tsx";
import { settings } from "../../../core/settings.ts";
import { useState, useEffect } from "react";

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
    const renderEnhancedAtlasSection = () => {
        if (!isAtlasVisible || !Atlases || Atlases.length === 0) {
            return null;
        }

        const atlasGridSize = isMobile ? 80 : 100; // Square size for atlas thumbnails
        const mainAtlasHeight = isMobile ? 200 : 300; // Height for main atlas viewer

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
                {/* Atlas Header */}
                <Box
                    sx={{
                        p: 2,
                        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        background: `linear-gradient(to right, ${alpha(theme.palette.primary.main, 0.03)} 0%, transparent 50%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box
                            sx={{
                                width: 36,
                                height: 36,
                                borderRadius: 2,
                                background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: `0 3px 10px ${alpha(theme.palette.primary.main, 0.3)}`
                            }}
                        >
                            <Map size={18} color="white" />
                        </Box>
                        <Box>
                            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                Atlas Navigator
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Chip
                                    icon={<Layers size={12} />}
                                    label={`${Atlases.length} views`}
                                    size="small"
                                    sx={{ height: 20, fontSize: '0.65rem' }}
                                />
                                {currentAtlas && (
                                    <Chip
                                        label={currentAtlas.name}
                                        size="small"
                                        color="primary"
                                        variant="outlined"
                                        sx={{ height: 20, fontSize: '0.65rem' }}
                                    />
                                )}
                            </Box>
                        </Box>
                    </Box>

                    <IconButton
                        onClick={() => setAtlasExpanded(!atlasExpanded)}
                        size="small"
                    >
                        {atlasExpanded ? <ExpandLess /> : <ExpandMore />}
                    </IconButton>
                </Box>

                {/* Atlas Content */}
                <Collapse in={atlasExpanded}>
                    <Box sx={{ p: 2 }}>
                        <Grid container spacing={2}>
                            {/* Atlas Thumbnails Grid - Square Layout */}
                            <Grid item xs={12} md={4}>
                                <Paper
                                    variant="outlined"
                                    sx={{
                                        p: 1,
                                        maxHeight: mainAtlasHeight,
                                        overflow: 'auto',
                                        backgroundColor: alpha(theme.palette.background.default, 0.5),
                                        '&::-webkit-scrollbar': {
                                            width: 8,
                                        },
                                        '&::-webkit-scrollbar-thumb': {
                                            backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                            borderRadius: 4,
                                        }
                                    }}
                                >
                                    <Typography variant="caption" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
                                        Available Atlases
                                    </Typography>

                                    <Box
                                        sx={{
                                            display: 'grid',
                                            gridTemplateColumns: `repeat(auto-fill, minmax(${atlasGridSize}px, 1fr))`,
                                            gap: 1,
                                        }}
                                    >
                                        {Atlases.map((atlas) => (
                                            <Paper
                                                key={atlas.oid}
                                                elevation={atlas.oid === currentAtlas?.oid ? 8 : 1}
                                                onClick={() => handleAtlasClick(atlas)}
                                                onMouseEnter={() => setHoveredAtlas(atlas.oid)}
                                                onMouseLeave={() => setHoveredAtlas(null)}
                                                sx={{
                                                    position: 'relative',
                                                    cursor: 'pointer',
                                                    aspectRatio: '1',
                                                    overflow: 'hidden',
                                                    borderRadius: 1.5,
                                                    border: atlas.oid === currentAtlas?.oid
                                                        ? `2px solid ${theme.palette.primary.main}`
                                                        : '2px solid transparent',
                                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                    transform: hoveredAtlas === atlas.oid ? 'scale(1.05)' : 'scale(1)',
                                                    '&:hover': {
                                                        boxShadow: `0 8px 16px ${alpha(theme.palette.common.black, 0.15)}`,
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
                                                            top: 4,
                                                            right: 4,
                                                            width: 24,
                                                            height: 24,
                                                            borderRadius: '50%',
                                                            backgroundColor: theme.palette.primary.main,
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.5)}`
                                                        }}
                                                    >
                                                        <Eye size={14} color="white" />
                                                    </Box>
                                                )}

                                                {/* Hover overlay with name */}
                                                {hoveredAtlas === atlas.oid && (
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
                                                                fontSize: '0.65rem',
                                                                fontWeight: 600,
                                                                display: 'block',
                                                                textAlign: 'center',
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'nowrap'
                                                            }}
                                                        >
                                                            {atlas.name}
                                                        </Typography>
                                                    </Box>
                                                )}
                                            </Paper>
                                        ))}
                                    </Box>
                                </Paper>
                            </Grid>

                            {/* Main Atlas Viewer - Bigger */}
                            <Grid item xs={12} md={8}>
                                <Paper
                                    variant="outlined"
                                    sx={{
                                        position: 'relative',
                                        height: mainAtlasHeight,
                                        backgroundColor: '#000',
                                        borderRadius: 2,
                                        overflow: 'hidden',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
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

                                            {/* Floating Controls */}
                                            <Box
                                                sx={{
                                                    position: 'absolute',
                                                    bottom: 16,
                                                    right: 16,
                                                    display: 'flex',
                                                    gap: 1,
                                                    backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                                    backdropFilter: 'blur(10px)',
                                                    borderRadius: 2,
                                                    p: 0.5,
                                                    boxShadow: `0 4px 16px ${alpha(theme.palette.common.black, 0.2)}`
                                                }}
                                            >
                                                <Tooltip title="Zoom Out">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => setAtlasZoom(prev => Math.max(0.5, prev - 0.1))}
                                                    >
                                                        <ZoomOut fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>

                                                <Chip
                                                    label={`${Math.round(atlasZoom * 100)}%`}
                                                    size="small"
                                                    sx={{ minWidth: 60 }}
                                                />

                                                <Tooltip title="Zoom In">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => setAtlasZoom(prev => Math.min(3, prev + 0.1))}
                                                    >
                                                        <ZoomIn fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>

                                                <Divider orientation="vertical" flexItem />

                                                <Tooltip title="Reset Zoom">
                                                    <IconButton size="small" onClick={() => setAtlasZoom(1)}>
                                                        <CenterFocusStrong fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>
                                            </Box>

                                            {/* Navigation Controls */}
                                            <Box
                                                sx={{
                                                    position: 'absolute',
                                                    top: '50%',
                                                    transform: 'translateY(-50%)',
                                                    width: '100%',
                                                    display: 'flex',
                                                    justifyContent: 'space-between',
                                                    px: 2,
                                                    pointerEvents: 'none'
                                                }}
                                            >
                                                <IconButton
                                                    onClick={() => navigateAtlas('prev')}
                                                    sx={{
                                                        backgroundColor: alpha(theme.palette.background.paper, 0.8),
                                                        pointerEvents: 'auto',
                                                        '&:hover': {
                                                            backgroundColor: theme.palette.background.paper,
                                                            transform: 'scale(1.1)'
                                                        }
                                                    }}
                                                >
                                                    <ChevronLeft />
                                                </IconButton>

                                                <IconButton
                                                    onClick={() => navigateAtlas('next')}
                                                    sx={{
                                                        backgroundColor: alpha(theme.palette.background.paper, 0.8),
                                                        pointerEvents: 'auto',
                                                        '&:hover': {
                                                            backgroundColor: theme.palette.background.paper,
                                                            transform: 'scale(1.1)'
                                                        }
                                                    }}
                                                >
                                                    <ChevronRight />
                                                </IconButton>
                                            </Box>
                                        </>
                                    )}
                                </Paper>
                            </Grid>
                        </Grid>
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