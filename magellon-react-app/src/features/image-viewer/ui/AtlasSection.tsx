import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box,
    Paper,
    Typography,
    Chip,
    IconButton,
    Collapse,
    Skeleton,
    Tooltip,
    Fade,
    Badge,
    CircularProgress,
    alpha,
    useTheme,
    useMediaQuery
} from '@mui/material';
import {
    ExpandMore,
    ExpandLess,
    ZoomIn,
    ZoomOut,
    CenterFocusStrong
} from '@mui/icons-material';
import {
    Map,
    Layers,
    Eye,
    EyeOff,
    ChevronUp,
    ChevronDown,
    ImageOff
} from 'lucide-react';
import { AtlasImageDto } from '../../../entities/image/types.ts';
import ImageInfoDto from '../../../entities/image/types.ts';
import AtlasViewer from './AtlasViewer';
import { settings } from '../../../shared/config/settings.ts';
import { AuthenticatedAtlasImage } from './AuthenticatedAtlasImage';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface AtlasSectionProps {
    atlases: AtlasImageDto[];
    currentAtlas: AtlasImageDto | null;
    sessionName: string;
    isVisible: boolean;
    onAtlasChange: (atlas: AtlasImageDto) => void;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
}

const THUMB_SIZE = 72;
const THUMB_COLUMN_WIDTH = 88;
const SCROLL_STEP = THUMB_SIZE + 8;

export const AtlasSection: React.FC<AtlasSectionProps> = ({
    atlases,
    currentAtlas,
    sessionName,
    isVisible,
    onAtlasChange,
    onImageClick
}) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const [atlasZoom, setAtlasZoom] = useState(1);
    const [expanded, setExpanded] = useState(true);
    const [atlasHidden, setAtlasHidden] = useState(false);
    const [hoveredAtlas, setHoveredAtlas] = useState<string | null>(null);
    const [atlasLoading, setAtlasLoading] = useState<string | null>(null);
    const [showZoomControls, setShowZoomControls] = useState(false);
    const [canScrollUp, setCanScrollUp] = useState(false);
    const [canScrollDown, setCanScrollDown] = useState(false);
    const [isInitialLoad, setIsInitialLoad] = useState(true);

    const thumbnailContainerRef = useRef<HTMLDivElement>(null);

    // --- scroll helpers ---
    const checkScrollAvailability = useCallback(() => {
        const el = thumbnailContainerRef.current;
        if (el) {
            setCanScrollUp(el.scrollTop > 0);
            setCanScrollDown(el.scrollTop + el.clientHeight < el.scrollHeight - 1);
        }
    }, []);

    useEffect(() => {
        checkScrollAvailability();
        const el = thumbnailContainerRef.current;
        if (el) {
            el.addEventListener('scroll', checkScrollAvailability);
            return () => el.removeEventListener('scroll', checkScrollAvailability);
        }
    }, [atlases, expanded, checkScrollAvailability]);

    // simulate initial load
    useEffect(() => {
        if (atlases && atlases.length > 0) {
            const t = setTimeout(() => setIsInitialLoad(false), 400);
            return () => clearTimeout(t);
        }
    }, [atlases]);

    const scrollThumbnails = (direction: 'up' | 'down') => {
        thumbnailContainerRef.current?.scrollBy({
            top: direction === 'up' ? -SCROLL_STEP : SCROLL_STEP,
            behavior: 'smooth'
        });
    };

    const handleAtlasClick = (atlas: AtlasImageDto) => {
        setAtlasLoading(atlas.oid);
        onAtlasChange(atlas);
        setTimeout(() => setAtlasLoading(null), 300);
    };

    const handleZoomIn = () => setAtlasZoom(z => Math.min(3, +(z + 0.1).toFixed(1)));
    const handleZoomOut = () => setAtlasZoom(z => Math.max(0.5, +(z - 0.1).toFixed(1)));
    const handleZoomReset = () => setAtlasZoom(1);

    // --- loading state ---
    if (isInitialLoad && atlases && atlases.length > 0) {
        return (
            <Paper
                elevation={2}
                sx={{
                    mb: 2,
                    borderRadius: 2,
                    p: 4,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 2,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
            >
                <CircularProgress size={24} />
                <Typography variant="body2" sx={{
                    color: "text.secondary"
                }}>
                    Loading atlas data...
                </Typography>
            </Paper>
        );
    }

    // --- empty state ---
    if (!atlases || atlases.length === 0) {
        return (
            <Paper
                elevation={0}
                sx={{
                    mb: 2,
                    borderRadius: 2,
                    p: 4,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 1.5,
                    border: `1px dashed ${alpha(theme.palette.divider, 0.3)}`,
                    backgroundColor: alpha(theme.palette.action.hover, 0.03),
                }}
            >
                <ImageOff size={32} color={theme.palette.text.disabled} />
                <Typography variant="body2" sx={{
                    color: "text.secondary"
                }}>
                    No atlas images available for this session.
                </Typography>
            </Paper>
        );
    }

    // --- hidden via visibility toggle ---
    if (!isVisible) {
        return null;
    }

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
            {/* ===== HEADER ===== */}
            <Box
                sx={{
                    px: 2,
                    py: 1,
                    borderBottom: expanded ? `1px solid ${alpha(theme.palette.divider, 0.1)}` : 'none',
                    background: `linear-gradient(to right, ${alpha(theme.palette.primary.main, 0.03)} 0%, transparent 50%)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    minHeight: 44,
                    cursor: 'pointer',
                    userSelect: 'none',
                    '&:hover': {
                        backgroundColor: alpha(theme.palette.action.hover, 0.04),
                    },
                }}
                onClick={() => setExpanded(e => !e)}
            >
                {/* Left side */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, overflow: 'hidden' }}>
                    <Box
                        sx={{
                            width: 28,
                            height: 28,
                            borderRadius: 1.5,
                            background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                            boxShadow: `0 2px 6px ${alpha(theme.palette.primary.main, 0.3)}`
                        }}
                    >
                        <Map size={14} color="white" />
                    </Box>

                    <Typography variant="body2" sx={{ fontWeight: 600, flexShrink: 0 }}>
                        Atlas Navigator
                    </Typography>

                    <Badge badgeContent={atlases.length} color="primary" max={99}>
                        <Layers size={16} color={theme.palette.text.secondary} />
                    </Badge>

                    {currentAtlas && (
                        <Chip
                            label={currentAtlas.name}
                            size="small"
                            color="primary"
                            variant="outlined"
                            sx={{
                                height: 20,
                                fontSize: '0.68rem',
                                maxWidth: 160,
                                '& .MuiChip-label': {
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }
                            }}
                        />
                    )}
                </Box>

                {/* Right side */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Tooltip title={atlasHidden ? 'Show Atlas Viewer' : 'Hide Atlas Viewer'}>
                        <IconButton
                            size="small"
                            onClick={(e) => {
                                e.stopPropagation();
                                setAtlasHidden(h => !h);
                            }}
                            sx={{ p: 0.5 }}
                        >
                            {atlasHidden
                                ? <EyeOff size={16} color={theme.palette.text.secondary} />
                                : <Eye size={16} color={theme.palette.text.secondary} />}
                        </IconButton>
                    </Tooltip>

                    <IconButton size="small" sx={{ p: 0.5 }}>
                        {expanded
                            ? <ExpandLess fontSize="small" />
                            : <ExpandMore fontSize="small" />}
                    </IconButton>
                </Box>
            </Box>
            {/* ===== BODY ===== */}
            <Collapse in={expanded && !atlasHidden}>
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: isMobile ? 'column' : 'row',
                        height: isMobile ? 'auto' : 320,
                    }}
                >
                    {/* --- Thumbnail strip (left column) --- */}
                    <Box
                        sx={{
                            width: isMobile ? '100%' : THUMB_COLUMN_WIDTH,
                            height: isMobile ? 90 : '100%',
                            display: 'flex',
                            flexDirection: isMobile ? 'row' : 'column',
                            alignItems: 'center',
                            position: 'relative',
                            borderRight: isMobile ? 'none' : `1px solid ${alpha(theme.palette.divider, 0.08)}`,
                            borderBottom: isMobile ? `1px solid ${alpha(theme.palette.divider, 0.08)}` : 'none',
                            py: isMobile ? 0 : 0.5,
                            order: isMobile ? 2 : 1,
                        }}
                    >
                        {/* Scroll up button */}
                        {!isMobile && (
                            <Fade in={canScrollUp}>
                                <IconButton
                                    size="small"
                                    onClick={() => scrollThumbnails('up')}
                                    sx={{
                                        width: 28,
                                        height: 28,
                                        flexShrink: 0,
                                        backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                        '&:hover': { backgroundColor: theme.palette.action.hover },
                                    }}
                                >
                                    <ChevronUp size={16} />
                                </IconButton>
                            </Fade>
                        )}

                        {/* Thumbnails */}
                        <Box
                            ref={thumbnailContainerRef}
                            sx={{
                                flex: 1,
                                display: 'flex',
                                flexDirection: isMobile ? 'row' : 'column',
                                alignItems: 'center',
                                gap: 1,
                                overflowY: isMobile ? 'hidden' : 'auto',
                                overflowX: isMobile ? 'auto' : 'hidden',
                                scrollbarWidth: 'none',
                                '&::-webkit-scrollbar': { display: 'none' },
                                py: 1,
                                px: isMobile ? 1 : 0,
                            }}
                        >
                            {atlases.map((atlas) => {
                                const isActive = atlas.oid === currentAtlas?.oid;
                                const isHovered = hoveredAtlas === atlas.oid;

                                return (
                                    <Tooltip
                                        key={atlas.oid}
                                        title={atlas.name}
                                        placement={isMobile ? 'top' : 'right'}
                                        arrow
                                    >
                                        <Box
                                            onClick={() => handleAtlasClick(atlas)}
                                            onMouseEnter={() => setHoveredAtlas(atlas.oid)}
                                            onMouseLeave={() => setHoveredAtlas(null)}
                                            sx={{
                                                position: 'relative',
                                                cursor: 'pointer',
                                                width: THUMB_SIZE,
                                                height: THUMB_SIZE,
                                                minWidth: THUMB_SIZE,
                                                minHeight: THUMB_SIZE,
                                                borderRadius: 1.5,
                                                overflow: 'hidden',
                                                border: isActive
                                                    ? `2px solid ${theme.palette.primary.main}`
                                                    : `2px solid ${alpha(theme.palette.divider, 0.15)}`,
                                                boxShadow: isActive
                                                    ? `0 0 0 2px ${alpha(theme.palette.primary.main, 0.25)}`
                                                    : 'none',
                                                transition: 'all 0.2s ease',
                                                transform: isHovered ? 'scale(1.06)' : 'scale(1)',
                                                '&:hover': {
                                                    borderColor: theme.palette.primary.light,
                                                    boxShadow: `0 4px 12px ${alpha(theme.palette.common.black, 0.15)}`,
                                                },
                                            }}
                                        >
                                            {atlasLoading === atlas.oid ? (
                                                <Skeleton
                                                    variant="rectangular"
                                                    width="100%"
                                                    height="100%"
                                                    animation="wave"
                                                />
                                            ) : (
                                                <AuthenticatedAtlasImage
                                                    atlasName={atlas.name}
                                                    sessionName={sessionName}
                                                    alt={atlas.name}
                                                    style={{
                                                        width: '100%',
                                                        height: '100%',
                                                        objectFit: 'cover',
                                                    }}
                                                    baseUrl={BASE_URL}
                                                />
                                            )}

                                            {/* Active indicator (eye badge) */}
                                            {isActive && (
                                                <Box
                                                    sx={{
                                                        position: 'absolute',
                                                        top: 3,
                                                        right: 3,
                                                        width: 18,
                                                        height: 18,
                                                        borderRadius: '50%',
                                                        backgroundColor: theme.palette.primary.main,
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        boxShadow: `0 1px 4px ${alpha(theme.palette.primary.main, 0.5)}`,
                                                    }}
                                                >
                                                    <Eye size={10} color="white" />
                                                </Box>
                                            )}
                                        </Box>
                                    </Tooltip>
                                );
                            })}
                        </Box>

                        {/* Scroll down button */}
                        {!isMobile && (
                            <Fade in={canScrollDown}>
                                <IconButton
                                    size="small"
                                    onClick={() => scrollThumbnails('down')}
                                    sx={{
                                        width: 28,
                                        height: 28,
                                        flexShrink: 0,
                                        backgroundColor: alpha(theme.palette.background.paper, 0.9),
                                        '&:hover': { backgroundColor: theme.palette.action.hover },
                                    }}
                                >
                                    <ChevronDown size={16} />
                                </IconButton>
                            </Fade>
                        )}
                    </Box>

                    {/* --- Main Atlas Viewer (right area) --- */}
                    <Box
                        onMouseEnter={() => setShowZoomControls(true)}
                        onMouseLeave={() => setShowZoomControls(false)}
                        sx={{
                            position: 'relative',
                            flex: 1,
                            height: isMobile ? 220 : '100%',
                            backgroundColor: '#0a0a0a',
                            overflow: 'hidden',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            order: isMobile ? 1 : 2,
                        }}
                    >
                        {currentAtlas ? (
                            <>
                                <Box
                                    sx={{
                                        transform: `scale(${atlasZoom})`,
                                        transition: 'transform 0.25s ease-out',
                                        transformOrigin: 'center',
                                    }}
                                >
                                    <AtlasViewer
                                        imageMapJson={currentAtlas.meta}
                                        finalWidth={isMobile ? 280 : 500}
                                        finalHeight={isMobile ? 180 : 280}
                                        name={currentAtlas.name}
                                        backgroundColor="black"
                                        onImageClick={onImageClick}
                                    />
                                </Box>

                                {/* Zoom controls overlay */}
                                <Fade in={showZoomControls || isMobile}>
                                    <Box
                                        sx={{
                                            position: 'absolute',
                                            bottom: 12,
                                            right: 12,
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.5,
                                            backgroundColor: alpha(theme.palette.background.paper, 0.88),
                                            backdropFilter: 'blur(10px)',
                                            borderRadius: 2,
                                            p: 0.5,
                                            boxShadow: `0 2px 10px ${alpha(theme.palette.common.black, 0.25)}`,
                                        }}
                                    >
                                        <Tooltip title="Zoom Out (-10%)">
                                            <IconButton size="small" onClick={handleZoomOut} sx={{ p: 0.5 }}>
                                                <ZoomOut fontSize="small" />
                                            </IconButton>
                                        </Tooltip>

                                        <Chip
                                            label={`${Math.round(atlasZoom * 100)}%`}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                minWidth: 52,
                                                height: 24,
                                                fontSize: '0.7rem',
                                                fontWeight: 600,
                                                fontVariantNumeric: 'tabular-nums',
                                            }}
                                        />

                                        <Tooltip title="Zoom In (+10%)">
                                            <IconButton size="small" onClick={handleZoomIn} sx={{ p: 0.5 }}>
                                                <ZoomIn fontSize="small" />
                                            </IconButton>
                                        </Tooltip>

                                        <Tooltip title="Reset Zoom (1x)">
                                            <IconButton size="small" onClick={handleZoomReset} sx={{ p: 0.5 }}>
                                                <CenterFocusStrong fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                </Fade>
                            </>
                        ) : (
                            /* No atlas selected state */
                            (<Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: 1,
                                    color: theme.palette.text.disabled,
                                }}
                            >
                                <Map size={28} />
                                <Typography variant="caption" sx={{
                                    color: "text.disabled"
                                }}>
                                    Select an atlas from the panel
                                </Typography>
                            </Box>)
                        )}
                    </Box>
                </Box>
            </Collapse>
        </Paper>
    );
};
