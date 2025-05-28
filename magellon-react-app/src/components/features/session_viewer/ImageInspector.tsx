import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import {
    Box,
    Card,
    CardContent,
    CardHeader,
    Tab,
    Tabs,
    Paper,
    Typography,
    ButtonGroup,
    FormControl,
    InputLabel,
    MenuItem,
    Select,
    SelectChangeEvent,
    Stack,
    IconButton,
    Alert,
    Skeleton,
    Chip,
    Divider,
    useTheme,
    useMediaQuery,
    Tooltip,
    Collapse,
    LinearProgress,
    Badge,
    Fab,
    Zoom,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Slider,
    Switch,
    FormControlLabel,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Snackbar,
    alpha,
    Grid
} from "@mui/material";
import { TabContext, TabPanel } from '@mui/lab';
import {
    AddOutlined,
    HighlightOff,
    Save,
    SyncOutlined,
    ImageOutlined,
    Timeline,
    ScatterPlot,
    Analytics,
    TuneOutlined,
    InfoOutlined as MuiInfoOutlined,
    ExpandMore,
    ExpandLess,
    ZoomIn,
    ZoomOut,
    Brightness4,
    Contrast,
    Refresh,
    Download,
    Share,
    Print,
    Fullscreen,
    FullscreenExit,
    Settings,
    Visibility,
    VisibilityOff,
    Edit,
    Delete,
    Compare,
    History,
    BookmarkBorder,
    Bookmark,
    FilterList
} from "@mui/icons-material";
import {
    FileImage,
    Zap,
    Database,
    Layers,
    Target,
    BarChart3,
    Eye,
    EyeOff,
    Maximize2,
    Minimize2,
    RotateCw,
    FlipHorizontal,
    FlipVertical,
    AlertCircle, CheckCircle
} from "lucide-react";
import ImageInfoDto from "./ImageInfoDto.ts";
import { settings } from "../../../core/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ParticleEditor from "./ParticleEditor.tsx";
import { ParticleSessionDialog } from "./ParticleSessionDialog.tsx";
import { useImageParticlePickings, useUpdateParticlePicking } from "../../../services/api/ParticlePickingRestService.ts";
import { ParticlePickingDto } from "../../../domains/ParticlePickingDto.ts";
import CtfInfoCards from "./CtfInfoCards.tsx";
import { useFetchImageCtfInfo } from "../../../services/api/CtfRestService.ts";
import MetadataExplorer from "./MetadataExplorer.tsx";
import { useImageViewerStore } from './store/imageViewerStore.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

// Enhanced info component with animation and better styling
const InfoItem: React.FC<{
    label: string;
    value: string | number | undefined | null;
    icon?: React.ReactNode;
    color?: string;
    loading?: boolean;
    formatter?: (value: any) => string;
}> = ({
          label,
          value,
          icon,
          color,
          loading = false,
          formatter = (val) => val
      }) => {
    const theme = useTheme();

    // Determine the display value
    const displayValue = (() => {
        // Handle null, undefined, or empty values
        if (value === null || value === undefined || value === '') {
            return 'N/A';
        }

        // Apply custom formatter if provided
        try {
            return formatter(value);
        } catch (error) {
            console.warn(`Formatting error for ${label}:`, error);
            return String(value);
        }
    })();

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            py: 0.75,
            px: 1,
            borderRadius: 1,
            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)}, transparent)`,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            transition: 'all 0.2s ease',
            '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                transform: 'translateX(2px)',
            }
        }}>
            {icon && (
                <Box sx={{
                    mr: 1.5,
                    color: color || 'primary.main',
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center'
                }}>
                    {icon}
                </Box>
            )}
            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="caption"
                    sx={{
                        color: 'text.secondary',
                        fontWeight: 600,
                        display: 'block',
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontSize: '0.65rem'
                    }}
                >
                    {label}
                </Typography>
                {loading ? (
                    <Skeleton width={60} height={20} />
                ) : (
                    <Typography
                        variant="body2"
                        sx={{
                            fontWeight: 500,
                            color: displayValue === 'N/A' ? 'text.disabled' : 'text.primary',
                            fontSize: '0.875rem'
                        }}
                    >
                        {displayValue}
                    </Typography>
                )}
            </Box>
        </Box>
    );
};

// Image processing controls component
const ImageProcessingControls: React.FC<{
    brightness: number;
    contrast: number;
    scale: number;
    onBrightnessChange: (value: number) => void;
    onContrastChange: (value: number) => void;
    onScaleChange: (value: number) => void;
    onReset: () => void;
}> = ({ brightness, contrast, scale, onBrightnessChange, onContrastChange, onScaleChange, onReset }) => {
    const [expanded, setExpanded] = useState(false);

    return (
        <Card elevation={1} sx={{ mb: 2 }}>
            <CardHeader
                title="Image Processing"
                action={
                    <IconButton onClick={() => setExpanded(!expanded)}>
                        {expanded ? <ExpandLess /> : <ExpandMore />}
                    </IconButton>
                }
                sx={{ pb: 1 }}
            />
            <Collapse in={expanded}>
                <CardContent sx={{ pt: 0 }}>
                    <Stack spacing={3}>
                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <Brightness4 sx={{ mr: 1, fontSize: 16 }} />
                                <Typography variant="body2">Brightness: {brightness}</Typography>
                            </Box>
                            <Slider
                                value={brightness}
                                onChange={(_, value) => onBrightnessChange(value as number)}
                                min={0}
                                max={100}
                                size="small"
                                sx={{ '& .MuiSlider-thumb': { width: 16, height: 16 } }}
                            />
                        </Box>

                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <Contrast sx={{ mr: 1, fontSize: 16 }} />
                                <Typography variant="body2">Contrast: {contrast}</Typography>
                            </Box>
                            <Slider
                                value={contrast}
                                onChange={(_, value) => onContrastChange(value as number)}
                                min={0}
                                max={100}
                                size="small"
                                sx={{ '& .MuiSlider-thumb': { width: 16, height: 16 } }}
                            />
                        </Box>

                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <ZoomIn sx={{ mr: 1, fontSize: 16 }} />
                                <Typography variant="body2">Scale: {scale.toFixed(1)}x</Typography>
                            </Box>
                            <Slider
                                value={scale}
                                onChange={(_, value) => onScaleChange(value as number)}
                                min={0.1}
                                max={3}
                                step={0.1}
                                size="small"
                                sx={{ '& .MuiSlider-thumb': { width: 16, height: 16 } }}
                            />
                        </Box>

                        <Button
                            variant="outlined"
                            size="small"
                            onClick={onReset}
                            startIcon={<Refresh />}
                        >
                            Reset
                        </Button>
                    </Stack>
                </CardContent>
            </Collapse>
        </Card>
    );
};

// Action buttons component
const ActionButtons: React.FC<{
    onSave: () => void;
    onDownload: () => void;
    onShare: () => void;
    onCompare: () => void;
    saving?: boolean;
}> = ({ onSave, onDownload, onShare, onCompare, saving = false }) => {
    const [speedDialOpen, setSpeedDialOpen] = useState(false);

    const actions = [
        { icon: <Save />, name: 'Save', onClick: onSave, loading: saving },
        { icon: <Download />, name: 'Download', onClick: onDownload },
        { icon: <Share />, name: 'Share', onClick: onShare },
        { icon: <Compare />, name: 'Compare', onClick: onCompare },
    ];

    return (
        <SpeedDial
            ariaLabel="Image actions"
            sx={{ position: 'fixed', bottom: 24, right: 24 }}
            icon={<SpeedDialIcon />}
            open={speedDialOpen}
            onOpen={() => setSpeedDialOpen(true)}
            onClose={() => setSpeedDialOpen(false)}
        >
            {actions.map((action) => (
                <SpeedDialAction
                    key={action.name}
                    icon={action.loading ? <LinearProgress /> : action.icon}
                    tooltipTitle={action.name}
                    onClick={() => {
                        action.onClick();
                        setSpeedDialOpen(false);
                    }}
                />
            ))}
        </SpeedDial>
    );
};

// Progress indicator for data loading
const DataLoadingProgress: React.FC<{
    isLoading: boolean;
    progress?: number;
    label?: string;
}> = ({ isLoading, progress, label = "Loading..." }) => {
    if (!isLoading) return null;

    return (
        <Box sx={{ width: '100%', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="body2" sx={{ mr: 1 }}>{label}</Typography>
                {progress !== undefined && (
                    <Typography variant="body2" color="text.secondary">
                        {Math.round(progress)}%
                    </Typography>
                )}
            </Box>
            <LinearProgress
                variant={progress !== undefined ? "determinate" : "indeterminate"}
                value={progress}
                sx={{ height: 6, borderRadius: 3 }}
            />
        </Box>
    );
};

export const ImageInspector: React.FC<SoloImageViewerProps> = ({ selectedImage }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Refs for advanced functionality
    const imageViewerRef = useRef<HTMLDivElement>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Enhanced state management
    const [imageError, setImageError] = useState<string | null>(null);
    const [isInfoExpanded, setIsInfoExpanded] = useState(!isMobile);
    const [loadingProgress, setLoadingProgress] = useState<number>(0);
    const [bookmarked, setBookmarked] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const [imageHistory, setImageHistory] = useState<ImageInfoDto[]>([]);

    // Processing state
    const [imageTransforms, setImageTransforms] = useState({
        rotation: 0,
        flipHorizontal: false,
        flipVertical: false,
    });

    // Access store state and actions with enhanced functionality
    const {
        activeTab,
        selectedParticlePicking,
        isParticlePickingDialogOpen,
        brightness,
        contrast,
        scale,
        currentSession,
        setActiveTab,
        setSelectedParticlePicking,
        updateParticlePicking,
        openParticlePickingDialog,
        closeParticlePickingDialog,
        setBrightness,
        setContrast,
        setScale
    } = useImageViewerStore();

    // Get the current session name
    const sessionName = currentSession?.name || '';

    // Enhanced API calls with progress tracking
    const {
        data: ImageCtfData,
        error: isCtfInfoError,
        isLoading: isCtfInfoLoading,
        refetch: refetchCtfInfo
    } = useFetchImageCtfInfo(selectedImage?.name, false);

    const {
        data: ImageParticlePickings,
        isLoading: isIPPLoading,
        isError: isIPPError,
        refetch: refetchImageParticlePickings
    } = useImageParticlePickings(selectedImage?.name, false);

    // Track image history
    useEffect(() => {
        if (selectedImage) {
            setImageHistory(prev => {
                const filtered = prev.filter(img => img.oid !== selectedImage.oid);
                return [selectedImage, ...filtered].slice(0, 10); // Keep last 10
            });
        }
    }, [selectedImage]);

    // Clear error when image changes
    useEffect(() => {
        setImageError(null);
    }, [selectedImage]);

    // Refresh CTF info when selected image changes
    useEffect(() => {
        if (selectedImage?.name) {
            refetchCtfInfo();
        }
    }, [selectedImage?.name, refetchCtfInfo]);

    // Enhanced tab configuration with dynamic badges
    const tabConfig = useMemo(() => [
        {
            label: "Image",
            value: "1",
            icon: <FileImage size={18} />,
            badge: imageTransforms.rotation !== 0 || imageTransforms.flipHorizontal || imageTransforms.flipVertical ? "modified" : null
        },
        {
            label: "FFT",
            value: "2",
            icon: <Timeline size={18} />
        },
        {
            label: "Particle Picking",
            value: "3",
            icon: <ScatterPlot size={18} />,
            badge: selectedParticlePicking ? "active" : null
        },
        {
            label: "CTF",
            value: "5",
            icon: <Analytics size={18} />,
            badge: ImageCtfData ? "data" : null
        },
        {
            label: "Frame Alignment",
            value: "6",
            icon: <TuneOutlined fontSize="small" />
        },
        {
            label: "Metadata",
            value: "7",
            icon: <Database size={18} />
        }
    ], [imageTransforms, selectedParticlePicking, ImageCtfData]);

    // Enhanced image processing functions
    const resetImageProcessing = useCallback(() => {
        setBrightness(50);
        setContrast(50);
        setScale(1);
        setImageTransforms({
            rotation: 0,
            flipHorizontal: false,
            flipVertical: false,
        });
    }, [setBrightness, setContrast, setScale]);

    const toggleFullscreen = useCallback(() => {
        if (!document.fullscreenElement && imageViewerRef.current) {
            imageViewerRef.current.requestFullscreen?.();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen?.();
            setIsFullscreen(false);
        }
    }, []);

    // Enhanced event handlers
    const handleTabChange = useCallback((event: React.SyntheticEvent, newValue: string) => {
        setActiveTab(newValue);
        setLoadingProgress(0);

        // Simulate loading progress for demo
        if (newValue === "3") {
            handleParticlePickingLoad();
        } else if (newValue === "5") {
            handleCtfInfoLoad();
        }
    }, [setActiveTab]);

    const handleSave = useCallback(async () => {
        if (!selectedParticlePicking) return;

        try {
            const updatePPMutation = useUpdateParticlePicking();
            await updatePPMutation.mutateAsync({
                oid: selectedParticlePicking.oid,
                image_id: selectedParticlePicking.image_id,
                data: selectedParticlePicking?.temp
            });
        } catch (error) {
            console.error('Failed to save particle picking:', error);
        }
    }, [selectedParticlePicking]);

    const handleDownload = useCallback(() => {
        // Implementation for downloading image
        console.log('Download functionality would be implemented here');
    }, []);

    const handleShare = useCallback(() => {
        // Implementation for sharing image
        console.log('Share functionality would be implemented here');
    }, []);

    const handleCompare = useCallback(() => {
        // Implementation for comparing images
        console.log('Compare functionality would be implemented here');
    }, []);

    // Reload data handlers
    const handleParticlePickingLoad = () => {
        refetchImageParticlePickings();
    };

    const handleCtfInfoLoad = () => {
        refetchCtfInfo();
    };

    // Dialog handlers
    const handleOpen = () => {
        openParticlePickingDialog();
    };

    const handleClose = () => {
        closeParticlePickingDialog();
    };

    const imageStyle: React.CSSProperties = {
        borderRadius: '12px',
        objectFit: 'contain',
        border: `2px solid ${theme.palette.divider}`,
        maxWidth: '100%',
        height: 'auto',
        boxShadow: theme.shadows[2]
    };

    // Enhanced image style with transforms
    const getImageStyle = useCallback((): React.CSSProperties => {
        const baseStyle: React.CSSProperties = {
            borderRadius: '12px',
            objectFit: 'contain',
            border: `2px solid ${theme.palette.divider}`,
            maxWidth: '100%',
            height: 'auto',
            boxShadow: theme.shadows[2],
            transition: 'transform 0.3s ease',
        };

        const transforms = [];
        if (imageTransforms.rotation !== 0) {
            transforms.push(`rotate(${imageTransforms.rotation}deg)`);
        }
        if (imageTransforms.flipHorizontal) {
            transforms.push('scaleX(-1)');
        }
        if (imageTransforms.flipVertical) {
            transforms.push('scaleY(-1)');
        }

        if (transforms.length > 0) {
            baseStyle.transform = transforms.join(' ');
        }

        return baseStyle;
    }, [theme, imageTransforms]);

    const OnIppSelected = useCallback((event: SelectChangeEvent) => {
        const selectedValue = event.target.value;

        if (selectedValue && selectedValue.trim() !== '' && Array.isArray(ImageParticlePickings)) {
            const filteredRecords = ImageParticlePickings.filter(record => record.oid === selectedValue);
            if (filteredRecords.length > 0) {
                setSelectedParticlePicking(filteredRecords[0]);
            }
        } else {
            setSelectedParticlePicking(null);
        }
    }, [ImageParticlePickings, setSelectedParticlePicking]);

    const handleIppUpdate = useCallback((ipp: ParticlePickingDto) => {
        updateParticlePicking(ipp);
    }, [updateParticlePicking]);

    // Show empty state if no image is selected
    if (!selectedImage) {
        return (
            <Card sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)}, ${alpha(theme.palette.secondary.main, 0.05)})`
            }}>
                <CardContent sx={{ textAlign: 'center', py: 8 }}>
                    <FileImage size={80} color={theme.palette.text.secondary} />
                    <Typography variant="h5" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
                        No Image Selected
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        Select an image from the navigation panel to view details
                    </Typography>
                    <Button variant="outlined" startIcon={<Eye />}>
                        Browse Images
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
            {/* Enhanced Image Information Header */}
            <Card sx={{ mb: 2, overflow: 'hidden' }}>
                <CardHeader
                    avatar={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <FileImage size={24} />
                            {bookmarked && <Bookmark color="warning" fontSize="small" />}
                        </Box>
                    }
                    title={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="h6" component="div" noWrap sx={{ flex: 1 }}>
                                {selectedImage.name}
                            </Typography>
                            <Chip
                                label={`Level ${selectedImage.level || 0}`}
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                        </Box>
                    }
                    action={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Tooltip title="Toggle bookmark">
                                <IconButton onClick={() => setBookmarked(!bookmarked)}>
                                    {bookmarked ? <Bookmark /> : <BookmarkBorder />}
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="View history">
                                <IconButton onClick={() => setShowHistory(true)}>
                                    <Badge badgeContent={imageHistory.length} color="primary">
                                        <History />
                                    </Badge>
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Toggle info">
                                <IconButton onClick={() => setIsInfoExpanded(!isInfoExpanded)}>
                                    {isInfoExpanded ? <ExpandLess /> : <ExpandMore />}
                                </IconButton>
                            </Tooltip>
                        </Box>
                    }
                    sx={{ pb: 1 }}
                />

                <Collapse in={isInfoExpanded}>
                    <CardContent sx={{ pt: 0 }}>
                        <DataLoadingProgress
                            isLoading={isCtfInfoLoading || isIPPLoading}
                            progress={loadingProgress}
                            label="Loading image data..."
                        />

                        <Stack
                            direction={isMobile ? "column" : "row"}
                            spacing={2}
                            divider={!isMobile && <Divider orientation="vertical" flexItem />}
                        >
                            <Stack spacing={1} sx={{ flex: 1 }}>
                                <InfoItem
                                    label="Magnification"
                                    value={selectedImage.mag ? `${selectedImage.mag}×` : undefined}
                                    icon={<Zap size={16} />}
                                    color={theme.palette.primary.main}
                                />
                                <InfoItem
                                    label="Defocus"
                                    value={selectedImage.defocus ? `${selectedImage.defocus.toFixed(2)} μm` : undefined}
                                    icon={<Target size={16} />}
                                    color={theme.palette.warning.main}
                                />
                            </Stack>

                            <Stack spacing={1} sx={{ flex: 1 }}>
                                <InfoItem
                                    label="Pixel Size"
                                    value={selectedImage.pixelSize ? `${selectedImage.pixelSize.toFixed(2)} Å/pix` : undefined}
                                    icon={<Layers size={16} />}
                                    color={theme.palette.info.main}
                                />
                                <InfoItem
                                    label="Dose"
                                    value={selectedImage.dose}
                                    icon={<BarChart3 size={16} />}
                                    color={theme.palette.success.main}
                                />
                            </Stack>

                            <Stack spacing={1} sx={{ flex: 1 }}>
                                <InfoItem
                                    label="Session"
                                    value={sessionName}
                                    icon={<Database size={16} />}
                                    color={theme.palette.secondary.main}
                                />
                                <InfoItem
                                    label="Children"
                                    value={selectedImage.children_count || 0}
                                    icon={<Layers size={16} />}
                                    color={theme.palette.text.secondary}
                                />
                            </Stack>
                        </Stack>
                    </CardContent>
                </Collapse>
            </Card>

            {/* Image Processing Controls */}
            {activeTab === "1" && (
                <ImageProcessingControls
                    brightness={brightness}
                    contrast={contrast}
                    scale={scale}
                    onBrightnessChange={setBrightness}
                    onContrastChange={setContrast}
                    onScaleChange={setScale}
                    onReset={resetImageProcessing}
                />
            )}

            {/* Main Content with Enhanced Tabs */}
            <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <TabContext value={activeTab}>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>


                        <Tabs
                            value={activeTab}
                            onChange={handleTabChange}
                            variant={isMobile ? "scrollable" : "standard"}
                            scrollButtons={isMobile ? "auto" : false}
                            sx={{
                                '& .MuiTab-root': {
                                    minHeight: 56,
                                    textTransform: 'none',
                                    fontWeight: 500,
                                    transition: 'all 0.2s ease'
                                }
                            }}
                        >
                            {tabConfig.map((tab) => (
                                <Tab
                                    key={tab.value}
                                    label={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {tab.badge ? (
                                                <Badge
                                                    badgeContent=""
                                                    variant="dot"
                                                    color={tab.badge === "active" ? "success" : "primary"}
                                                >
                                                    {tab.icon}
                                                </Badge>
                                            ) : (
                                                tab.icon
                                            )}
                                            <span>{isMobile ? tab.label.split(' ')[0] : tab.label}</span>
                                        </Box>
                                    }
                                    value={tab.value}
                                />
                            ))}
                        </Tabs>
                    </Box>


                    <Box sx={{ flex: 1, overflow: 'auto' }} ref={imageViewerRef}>
                        <TabPanel value="1" sx={{ p: 3, height: '100%' }}>
                            <Box sx={{
                                textAlign: 'center',
                                height: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center'
                            }}>
                                <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'center' }}>
                                    <Tooltip title="Rotate 90°">
                                        <IconButton
                                            onClick={() => setImageTransforms(prev => ({
                                                ...prev,
                                                rotation: (prev.rotation + 90) % 360
                                            }))}
                                            size="small"
                                        >
                                            <RotateCw size={18} />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Flip Horizontal">
                                        <IconButton
                                            onClick={() => setImageTransforms(prev => ({
                                                ...prev,
                                                flipHorizontal: !prev.flipHorizontal
                                            }))}
                                            size="small"
                                            color={imageTransforms.flipHorizontal ? "primary" : "default"}
                                        >
                                            <FlipHorizontal size={18} />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Flip Vertical">
                                        <IconButton
                                            onClick={() => setImageTransforms(prev => ({
                                                ...prev,
                                                flipVertical: !prev.flipVertical
                                            }))}
                                            size="small"
                                            color={imageTransforms.flipVertical ? "primary" : "default"}
                                        >
                                            <FlipVertical size={18} />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
                                        <IconButton onClick={toggleFullscreen} size="small">
                                            {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                                        </IconButton>
                                    </Tooltip>
                                </Box>
                                <ImageViewer
                                    imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    width={isMobile ? 300 : 1024}
                                    height={isMobile ? 300 : 1024}
                                    imageStyle={getImageStyle()}
                                />

                            </Box>
                        </TabPanel>

                        {/* Other tab panels remain similar but with enhanced styling... */}
                        <TabPanel value="2" sx={{ p: 3 }}>
                            <Box sx={{ textAlign: 'center' }}>
                                <img
                                    src={`${BASE_URL}/fft_image?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="FFT image"
                                    style={{
                                        ...getImageStyle(),
                                        maxWidth: isMobile ? '100%' : '900px'
                                    }}
                                    onError={() => setImageError('Failed to load FFT image')}
                                />
                                {imageError && (
                                    <Alert severity="warning" sx={{ mt: 2 }}>
                                        {imageError}
                                    </Alert>
                                )}
                            </Box>
                        </TabPanel>

                        <TabPanel value="3" sx={{ p: 3 }}>
                            <Stack spacing={3}>
                                {/* Particle Picking Controls */}
                                <Paper elevation={1} sx={{ p: 2 }}>
                                    <Typography variant="subtitle1" gutterBottom>
                                        Particle Picking: {selectedParticlePicking?.name || "None Selected"}
                                    </Typography>

                                    <Stack direction={isMobile ? "column" : "row"} spacing={2} alignItems="flex-start">
                                        <FormControl size="small" sx={{ minWidth: 200 }}>
                                            <InputLabel>Particle Picking</InputLabel>
                                            <Select
                                                value={selectedParticlePicking?.oid || ""}
                                                label="Particle Picking"
                                                onChange={OnIppSelected}
                                            >
                                                <MenuItem value="">
                                                    <em>None</em>
                                                </MenuItem>
                                                {Array.isArray(ImageParticlePickings) && ImageParticlePickings?.map((ipp) => (
                                                    <MenuItem key={ipp.oid} value={ipp.oid}>
                                                        {ipp.name}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        <ButtonGroup size="small" variant="outlined">
                                            <Tooltip title="Refresh">
                                                <IconButton onClick={handleParticlePickingLoad}>
                                                    <SyncOutlined />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Create New">
                                                <IconButton onClick={handleOpen}>
                                                    <AddOutlined />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Save">
                                                <IconButton onClick={handleSave} disabled={!selectedParticlePicking}>
                                                    <Save />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Delete">
                                                <IconButton>
                                                    <HighlightOff />
                                                </IconButton>
                                            </Tooltip>
                                        </ButtonGroup>
                                    </Stack>
                                </Paper>

                                {/* Particle Picking Image */}
                                <Box sx={{ textAlign: 'center' }}>
                                    <ParticleEditor
                                        image={selectedImage}
                                        ipp={selectedParticlePicking}
                                        imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                        width={isMobile ? 300 : 1024}
                                        height={isMobile ? 300 : 1024}
                                        onCirclesSelected={(circles) => console.log("Circles selected:", circles)}
                                        onIppUpdate={handleIppUpdate}
                                    />
                                </Box>

                                <ParticleSessionDialog
                                    open={isParticlePickingDialogOpen}
                                    onClose={handleClose}
                                    ImageDto={selectedImage}
                                />
                            </Stack>
                        </TabPanel>


                        <TabPanel value="5" sx={{ p: 3 }}>
                            <Stack spacing={4}>
                                {isCtfInfoLoading ? (
                                    <Stack spacing={3}>
                                        {/* Loading skeleton for metrics */}
                                        <Grid container spacing={3}>
                                            {[1, 2, 3, 4].map((item) => (
                                                <Grid item xs={12} sm={6} md={3} key={item}>
                                                    <Skeleton
                                                        variant="rounded"
                                                        height={160}
                                                        sx={{
                                                            borderRadius: 3,
                                                            background: `linear-gradient(90deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(theme.palette.primary.main, 0.1)} 50%, ${alpha(theme.palette.primary.main, 0.05)} 100%)`
                                                        }}
                                                    />
                                                </Grid>
                                            ))}
                                        </Grid>

                                        {/* Loading skeleton for images */}
                                        <Grid container spacing={3}>
                                            <Grid item xs={12} lg={6}>
                                                <Skeleton variant="rounded" height={450} sx={{ borderRadius: 3 }} />
                                            </Grid>
                                            <Grid item xs={12} lg={6}>
                                                <Skeleton variant="rounded" height={450} sx={{ borderRadius: 3 }} />
                                            </Grid>
                                        </Grid>
                                    </Stack>
                                ) : isCtfInfoError ? (
                                    <Alert
                                        severity="error"
                                        icon={<AlertCircle size={20} />}
                                        sx={{
                                            borderRadius: 2,
                                            backgroundColor: alpha(theme.palette.error.main, 0.08),
                                            border: `1px solid ${alpha(theme.palette.error.main, 0.2)}`,
                                        }}
                                        action={
                                            <Button
                                                color="inherit"
                                                size="small"
                                                onClick={handleCtfInfoLoad}
                                                startIcon={<Refresh />}
                                            >
                                                Retry
                                            </Button>
                                        }
                                    >
                                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                                            Error loading CTF data
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            {isCtfInfoError.message || 'Unable to fetch CTF analysis results'}
                                        </Typography>
                                    </Alert>
                                ) : ImageCtfData && ImageCtfData.defocus1 !== null ? (
                                    <>
                                        {/* Header Section */}
                                        <Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                    <Box
                                                        sx={{
                                                            width: 48,
                                                            height: 48,
                                                            borderRadius: 2,
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                                                            color: 'white',
                                                            boxShadow: `0 4px 12px ${alpha(theme.palette.primary.main, 0.3)}`,
                                                        }}
                                                    >
                                                        <Analytics />
                                                    </Box>
                                                    <Box>
                                                        <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                                                            CTF Analysis Results
                                                        </Typography>
                                                        <Typography variant="body2" color="text.secondary">
                                                            Contrast Transfer Function parameters
                                                        </Typography>
                                                    </Box>
                                                </Box>

                                                {!isMobile && (
                                                    <ButtonGroup variant="outlined" size="small">
                                                        <Button startIcon={<Refresh />} onClick={handleCtfInfoLoad}>
                                                            Refresh
                                                        </Button>
                                                        <Button startIcon={<Download />}>
                                                            Export
                                                        </Button>
                                                    </ButtonGroup>
                                                )}
                                            </Box>

                                            <Divider sx={{ backgroundColor: alpha(theme.palette.divider, 0.08) }} />
                                        </Box>

                                        {/* Metrics Cards with modern design */}
                                        <Grid container spacing={3}>
                                            {/* Defocus 1 Card */}
                                            <Grid item xs={12} sm={6} md={3}>
                                                <Card
                                                    elevation={0}
                                                    sx={{
                                                        height: '100%',
                                                        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.08)}, ${alpha(theme.palette.primary.main, 0.02)})`,
                                                        border: `1px solid ${alpha(theme.palette.primary.main, 0.15)}`,
                                                        borderRadius: 3,
                                                        position: 'relative',
                                                        overflow: 'hidden',
                                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                        '&:hover': {
                                                            transform: 'translateY(-4px)',
                                                            boxShadow: `0 12px 24px ${alpha(theme.palette.primary.main, 0.15)}`,
                                                            borderColor: alpha(theme.palette.primary.main, 0.3),
                                                        }
                                                    }}
                                                >
                                                    <CardContent sx={{ p: 3 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                                            <Box
                                                                sx={{
                                                                    width: 44,
                                                                    height: 44,
                                                                    borderRadius: 2,
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                                    color: theme.palette.primary.main,
                                                                }}
                                                            >
                                                                <Target size={20} />
                                                            </Box>
                                                            {ImageCtfData.defocus1 >= 0.5 && ImageCtfData.defocus1 <= 3.0 && (
                                                                <CheckCircle sx={{ color: 'success.main', fontSize: 20 }} />
                                                            )}
                                                        </Box>

                                                        <Typography
                                                            variant="h4"
                                                            sx={{
                                                                fontWeight: 700,
                                                                color: theme.palette.primary.main,
                                                                mb: 0.5,
                                                                fontFamily: 'monospace',
                                                            }}
                                                        >
                                                            {ImageCtfData.defocus1.toFixed(2)}
                                                            <Typography
                                                                component="span"
                                                                variant="body1"
                                                                sx={{
                                                                    ml: 0.5,
                                                                    fontWeight: 400,
                                                                    color: 'text.secondary',
                                                                }}
                                                            >
                                                                μm
                                                            </Typography>
                                                        </Typography>

                                                        <Typography
                                                            variant="body2"
                                                            color="text.secondary"
                                                            sx={{ fontWeight: 600 }}
                                                        >
                                                            Defocus 1
                                                        </Typography>
                                                    </CardContent>

                                                    {/* Decorative element */}
                                                    <Box
                                                        sx={{
                                                            position: 'absolute',
                                                            bottom: -20,
                                                            right: -20,
                                                            width: 80,
                                                            height: 80,
                                                            borderRadius: '50%',
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                                        }}
                                                    />
                                                </Card>
                                            </Grid>

                                            {/* Defocus 2 Card */}
                                            <Grid item xs={12} sm={6} md={3}>
                                                <Card
                                                    elevation={0}
                                                    sx={{
                                                        height: '100%',
                                                        background: `linear-gradient(135deg, ${alpha(theme.palette.secondary.main, 0.08)}, ${alpha(theme.palette.secondary.main, 0.02)})`,
                                                        border: `1px solid ${alpha(theme.palette.secondary.main, 0.15)}`,
                                                        borderRadius: 3,
                                                        position: 'relative',
                                                        overflow: 'hidden',
                                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                        '&:hover': {
                                                            transform: 'translateY(-4px)',
                                                            boxShadow: `0 12px 24px ${alpha(theme.palette.secondary.main, 0.15)}`,
                                                            borderColor: alpha(theme.palette.secondary.main, 0.3),
                                                        }
                                                    }}
                                                >
                                                    <CardContent sx={{ p: 3 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                                            <Box
                                                                sx={{
                                                                    width: 44,
                                                                    height: 44,
                                                                    borderRadius: 2,
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                                                    color: theme.palette.secondary.main,
                                                                }}
                                                            >
                                                                <Target size={20} />
                                                            </Box>
                                                            {ImageCtfData.defocus2 >= 0.5 && ImageCtfData.defocus2 <= 3.0 && (
                                                                <CheckCircle sx={{ color: 'success.main', fontSize: 20 }} />
                                                            )}
                                                        </Box>

                                                        <Typography
                                                            variant="h4"
                                                            sx={{
                                                                fontWeight: 700,
                                                                color: theme.palette.secondary.main,
                                                                mb: 0.5,
                                                                fontFamily: 'monospace',
                                                            }}
                                                        >
                                                            {ImageCtfData.defocus2.toFixed(2)}
                                                            <Typography
                                                                component="span"
                                                                variant="body1"
                                                                sx={{
                                                                    ml: 0.5,
                                                                    fontWeight: 400,
                                                                    color: 'text.secondary',
                                                                }}
                                                            >
                                                                μm
                                                            </Typography>
                                                        </Typography>

                                                        <Typography
                                                            variant="body2"
                                                            color="text.secondary"
                                                            sx={{ fontWeight: 600 }}
                                                        >
                                                            Defocus 2
                                                        </Typography>
                                                    </CardContent>

                                                    <Box
                                                        sx={{
                                                            position: 'absolute',
                                                            bottom: -20,
                                                            right: -20,
                                                            width: 80,
                                                            height: 80,
                                                            borderRadius: '50%',
                                                            backgroundColor: alpha(theme.palette.secondary.main, 0.05),
                                                        }}
                                                    />
                                                </Card>
                                            </Grid>

                                            {/* Angle Astigmatism Card */}
                                            <Grid item xs={12} sm={6} md={3}>
                                                <Card
                                                    elevation={0}
                                                    sx={{
                                                        height: '100%',
                                                        background: `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.08)}, ${alpha(theme.palette.warning.main, 0.02)})`,
                                                        border: `1px solid ${alpha(theme.palette.warning.main, 0.15)}`,
                                                        borderRadius: 3,
                                                        position: 'relative',
                                                        overflow: 'hidden',
                                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                        '&:hover': {
                                                            transform: 'translateY(-4px)',
                                                            boxShadow: `0 12px 24px ${alpha(theme.palette.warning.main, 0.15)}`,
                                                            borderColor: alpha(theme.palette.warning.main, 0.3),
                                                        }
                                                    }}
                                                >
                                                    <CardContent sx={{ p: 3 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                                            <Box
                                                                sx={{
                                                                    width: 44,
                                                                    height: 44,
                                                                    borderRadius: 2,
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    backgroundColor: alpha(theme.palette.warning.main, 0.1),
                                                                    color: theme.palette.warning.main,
                                                                }}
                                                            >
                                                                <Timeline />
                                                            </Box>
                                                        </Box>

                                                        <Typography
                                                            variant="h4"
                                                            sx={{
                                                                fontWeight: 700,
                                                                color: theme.palette.warning.main,
                                                                mb: 0.5,
                                                                fontFamily: 'monospace',
                                                            }}
                                                        >
                                                            {ImageCtfData.angleAstigmatism.toFixed(1)}
                                                            <Typography
                                                                component="span"
                                                                variant="body1"
                                                                sx={{
                                                                    ml: 0.5,
                                                                    fontWeight: 400,
                                                                    color: 'text.secondary',
                                                                }}
                                                            >
                                                                °
                                                            </Typography>
                                                        </Typography>

                                                        <Typography
                                                            variant="body2"
                                                            color="text.secondary"
                                                            sx={{ fontWeight: 600 }}
                                                        >
                                                            Angle Astigmatism
                                                        </Typography>
                                                    </CardContent>

                                                    <Box
                                                        sx={{
                                                            position: 'absolute',
                                                            bottom: -20,
                                                            right: -20,
                                                            width: 80,
                                                            height: 80,
                                                            borderRadius: '50%',
                                                            backgroundColor: alpha(theme.palette.warning.main, 0.05),
                                                        }}
                                                    />
                                                </Card>
                                            </Grid>

                                            {/* Resolution Card */}
                                            <Grid item xs={12} sm={6} md={3}>
                                                <Card
                                                    elevation={0}
                                                    sx={{
                                                        height: '100%',
                                                        background: `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.08)}, ${alpha(theme.palette.success.main, 0.02)})`,
                                                        border: `1px solid ${alpha(theme.palette.success.main, 0.15)}`,
                                                        borderRadius: 3,
                                                        position: 'relative',
                                                        overflow: 'hidden',
                                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                        '&:hover': {
                                                            transform: 'translateY(-4px)',
                                                            boxShadow: `0 12px 24px ${alpha(theme.palette.success.main, 0.15)}`,
                                                            borderColor: alpha(theme.palette.success.main, 0.3),
                                                        }
                                                    }}
                                                >
                                                    <CardContent sx={{ p: 3 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                                            <Box
                                                                sx={{
                                                                    width: 44,
                                                                    height: 44,
                                                                    borderRadius: 2,
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    backgroundColor: alpha(theme.palette.success.main, 0.1),
                                                                    color: theme.palette.success.main,
                                                                }}
                                                            >
                                                                <BarChart3 size={20} />
                                                            </Box>
                                                            {ImageCtfData.resolution <= 3.5 && (
                                                                <CheckCircle sx={{ color: 'success.main', fontSize: 20 }} />
                                                            )}
                                                        </Box>

                                                        <Typography
                                                            variant="h4"
                                                            sx={{
                                                                fontWeight: 700,
                                                                color: theme.palette.success.main,
                                                                mb: 0.5,
                                                                fontFamily: 'monospace',
                                                            }}
                                                        >
                                                            {ImageCtfData.resolution.toFixed(2)}
                                                            <Typography
                                                                component="span"
                                                                variant="body1"
                                                                sx={{
                                                                    ml: 0.5,
                                                                    fontWeight: 400,
                                                                    color: 'text.secondary',
                                                                }}
                                                            >
                                                                Å
                                                            </Typography>
                                                        </Typography>

                                                        <Typography
                                                            variant="body2"
                                                            color="text.secondary"
                                                            sx={{ fontWeight: 600 }}
                                                        >
                                                            Resolution 50%
                                                        </Typography>
                                                    </CardContent>

                                                    <Box
                                                        sx={{
                                                            position: 'absolute',
                                                            bottom: -20,
                                                            right: -20,
                                                            width: 80,
                                                            height: 80,
                                                            borderRadius: '50%',
                                                            backgroundColor: alpha(theme.palette.success.main, 0.05),
                                                        }}
                                                    />
                                                </Card>
                                            </Grid>
                                        </Grid>

                                        {/* CTF Images Section */}
                                        <Grid container spacing={3}>
                                            {/* Power Spectrum */}
                                            <Grid item xs={12} lg={6}>
                                                <Paper
                                                    elevation={0}
                                                    sx={{
                                                        borderRadius: 3,
                                                        overflow: 'hidden',
                                                        backgroundColor: 'background.paper',
                                                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                        position: 'relative',
                                                    }}
                                                >
                                                    <Box
                                                        sx={{
                                                            p: 2.5,
                                                            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                            background: `linear-gradient(to bottom, ${alpha(theme.palette.background.paper, 0.9)}, transparent)`,
                                                        }}
                                                    >
                                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                                                Power Spectrum
                                                            </Typography>
                                                            <ButtonGroup size="small" variant="text">
                                                                <Tooltip title="Download">
                                                                    <IconButton size="small">
                                                                        <Download fontSize="small" />
                                                                    </IconButton>
                                                                </Tooltip>
                                                                <Tooltip title="Fullscreen">
                                                                    <IconButton size="small">
                                                                        <Maximize2 size={16} />
                                                                    </IconButton>
                                                                </Tooltip>
                                                            </ButtonGroup>
                                                        </Box>
                                                    </Box>

                                                    <Box
                                                        sx={{
                                                            backgroundColor: '#000',
                                                            minHeight: 400,
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            p: 2,
                                                        }}
                                                    >
                                                        <img
                                                            src={`${BASE_URL}/ctf_image?image_type=powerspec&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                                            alt="CTF power spectrum"
                                                            style={{
                                                                maxWidth: '100%',
                                                                height: 'auto',
                                                                borderRadius: '8px',
                                                            }}
                                                        />
                                                    </Box>
                                                </Paper>
                                            </Grid>

                                            {/* CTF Plots */}
                                            <Grid item xs={12} lg={6}>
                                                <Paper
                                                    elevation={0}
                                                    sx={{
                                                        borderRadius: 3,
                                                        overflow: 'hidden',
                                                        backgroundColor: 'background.paper',
                                                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                        position: 'relative',
                                                    }}
                                                >
                                                    <Box
                                                        sx={{
                                                            p: 2.5,
                                                            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                            background: `linear-gradient(to bottom, ${alpha(theme.palette.background.paper, 0.9)}, transparent)`,
                                                        }}
                                                    >
                                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                                                CTF Fit Plots
                                                            </Typography>
                                                            <ButtonGroup size="small" variant="text">
                                                                <Tooltip title="Download">
                                                                    <IconButton size="small">
                                                                        <Download fontSize="small" />
                                                                    </IconButton>
                                                                </Tooltip>
                                                                <Tooltip title="Fullscreen">
                                                                    <IconButton size="small">
                                                                        <Maximize2 size={16} />
                                                                    </IconButton>
                                                                </Tooltip>
                                                            </ButtonGroup>
                                                        </Box>
                                                    </Box>

                                                    <Box
                                                        sx={{
                                                            backgroundColor: '#000',
                                                            minHeight: 400,
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            p: 2,
                                                        }}
                                                    >
                                                        <img
                                                            src={`${BASE_URL}/ctf_image?image_type=plots&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                                            alt="CTF plots"
                                                            style={{
                                                                maxWidth: '100%',
                                                                height: 'auto',
                                                                borderRadius: '8px',
                                                            }}
                                                        />
                                                    </Box>
                                                </Paper>
                                            </Grid>
                                        </Grid>

                                        {/* Additional Analysis Info */}
                                        <Card
                                            elevation={0}
                                            sx={{
                                                borderRadius: 3,
                                                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <CardContent sx={{ p: 3 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
                                                    <Box
                                                        sx={{
                                                            width: 32,
                                                            height: 32,
                                                            borderRadius: 1.5,
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                            color: theme.palette.primary.main,
                                                        }}
                                                    >
                                                        <MuiInfoOutlined fontSize="small" />
                                                    </Box>
                                                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                                        Detailed Analysis
                                                    </Typography>
                                                </Box>

                                                <Grid container spacing={3}>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                                                Defocus Difference
                                                            </Typography>
                                                            <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                                                {Math.abs(ImageCtfData.defocus1 - ImageCtfData.defocus2).toFixed(3)} μm
                                                            </Typography>
                                                        </Box>
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                                                Average Defocus
                                                            </Typography>
                                                            <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                                                {((ImageCtfData.defocus1 + ImageCtfData.defocus2) / 2).toFixed(3)} μm
                                                            </Typography>
                                                        </Box>
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                                                Astigmatism Ratio
                                                            </Typography>
                                                            <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                                                {(Math.abs(ImageCtfData.defocus1 - ImageCtfData.defocus2) /
                                                                    ((ImageCtfData.defocus1 + ImageCtfData.defocus2) / 2) * 100).toFixed(1)}%
                                                            </Typography>
                                                        </Box>
                                                    </Grid>
                                                    <Grid item xs={12} sm={6} md={3}>
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                                                Quality Assessment
                                                            </Typography>
                                                            <Box sx={{ mt: 0.5 }}>
                                                                <Chip
                                                                    label="Good Quality"
                                                                    size="small"
                                                                    color="success"
                                                                    icon={<CheckCircle />}
                                                                    sx={{
                                                                        fontWeight: 600,
                                                                        '& .MuiChip-icon': { fontSize: 16 }
                                                                    }}
                                                                />
                                                            </Box>
                                                        </Box>
                                                    </Grid>
                                                </Grid>
                                            </CardContent>
                                        </Card>
                                    </>
                                ) : (
                                    <Alert
                                        severity="info"
                                        icon={<MuiInfoOutlined />}
                                        sx={{
                                            borderRadius: 3,
                                            backgroundColor: alpha(theme.palette.info.main, 0.08),
                                            border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
                                        }}
                                    >
                                        <Typography variant="body1" sx={{ fontWeight: 600, mb: 1 }}>
                                            No CTF data available
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            CTF analysis has not been performed for this image yet. Please run CTF estimation to view results.
                                        </Typography>
                                    </Alert>
                                )}
                            </Stack>
                        </TabPanel>




                        <TabPanel value="6" sx={{ p: 3 }}>
                            <Stack spacing={2} alignItems="center">
                                <img
                                    src={`${BASE_URL}/fao_image?image_type=one&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="Frame alignment - image one"
                                    style={{
                                        ...imageStyle,
                                        maxWidth: isMobile ? '100%' : '900px'
                                    }}
                                />
                                <img
                                    src={`${BASE_URL}/fao_image?image_type=two&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="Frame alignment - image two"
                                    style={{
                                        ...imageStyle,
                                        maxWidth: isMobile ? '100%' : '900px'
                                    }}
                                />
                            </Stack>
                        </TabPanel>

                        <TabPanel value="7" sx={{ p: 3 }}>
                            <MetadataExplorer selectedImage={selectedImage} />
                        </TabPanel>


                    </Box>
                </TabContext>
            </Card>

            {/* Action Buttons */}
            <ActionButtons
                onSave={handleSave}
                onDownload={handleDownload}
                onShare={handleShare}
                onCompare={handleCompare}
                saving={false}
            />

            {/* History Dialog */}
            <Dialog open={showHistory} onClose={() => setShowHistory(false)} maxWidth="md" fullWidth>
                <DialogTitle>Image History</DialogTitle>
                <DialogContent>
                    <List>
                        {imageHistory.map((image, index) => (
                            <ListItem key={image.oid} button onClick={() => {
                                // Handle image selection from history
                                setShowHistory(false);
                            }}>
                                <ListItemIcon>
                                    <FileImage size={20} />
                                </ListItemIcon>
                                <ListItemText
                                    primary={image.name}
                                    secondary={`Level ${image.level || 0} • ${image.defocus?.toFixed(2) || 'N/A'} μm`}
                                />
                            </ListItem>
                        ))}
                    </List>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowHistory(false)}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Particle Picking Dialog */}
            <ParticleSessionDialog
                open={isParticlePickingDialogOpen}
                onClose={closeParticlePickingDialog}
                ImageDto={selectedImage}
            />
        </Box>
    );
};

export default ImageInspector;