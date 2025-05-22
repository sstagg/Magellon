import React, { useEffect, useMemo, useState } from "react";
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
    Collapse
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
    ExpandLess
} from "@mui/icons-material";
import { FileImage, Zap, Settings, Database } from "lucide-react";
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

// Enhanced info component with better styling
const InfoItem: React.FC<{
    label: string;
    value: string | number | undefined;
    icon?: React.ReactNode;
}> = ({ label, value, icon }) => {
    const theme = useTheme();

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            py: 0.5,
            minWidth: 0 // Allow text truncation
        }}>
            {icon && (
                <Box sx={{ mr: 1, color: 'text.secondary', flexShrink: 0 }}>
                    {icon}
                </Box>
            )}
            <Typography
                variant="caption"
                sx={{
                    color: 'text.secondary',
                    fontWeight: 500,
                    mr: 1,
                    flexShrink: 0
                }}
            >
                {label}:
            </Typography>
            <Typography
                variant="body2"
                sx={{
                    fontWeight: 400,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                }}
            >
                {value || 'N/A'}
            </Typography>
        </Box>
    );
};

export const ImageInspector: React.FC<SoloImageViewerProps> = ({ selectedImage }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Local state
    const [imageError, setImageError] = useState<string | null>(null);
    const [isInfoExpanded, setIsInfoExpanded] = useState(!isMobile);

    // Access store state and actions
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
        closeParticlePickingDialog
    } = useImageViewerStore();

    // Get the current session name
    const sessionName = currentSession?.name || '';

    // Fetch CTF info
    const {
        data: ImageCtfData,
        error: isCtfInfoError,
        isLoading: isCtfInfoLoading,
        refetch: refetchCtfInfo
    } = useFetchImageCtfInfo(selectedImage?.name, false);

    // Fetch particle pickings
    const {
        data: ImageParticlePickings,
        isLoading: isIPPLoading,
        isError: isIPPError,
        refetch: refetchImageParticlePickings
    } = useImageParticlePickings(selectedImage?.name, false);

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

    // Tab configuration with icons
    const tabConfig = useMemo(() => [
        { label: "Image", value: "1", icon: <FileImage size={18} /> },
        { label: "FFT", value: "2", icon: <Timeline size={18} /> },
        { label: "Particle Picking", value: "3", icon: <ScatterPlot size={18} /> },
        { label: "CTF", value: "5", icon: <Analytics size={18} /> },
        { label: "Frame Alignment", value: "6", icon: <TuneOutlined fontSize="small" /> },
        { label: "Metadata", value: "7", icon: <Database size={18} /> }
    ], []);

    // Handle tab change
    const handleChange = (event: React.SyntheticEvent, newValue: string) => {
        setActiveTab(newValue);

        // Load data when specific tabs are clicked
        if (newValue === "3") {
            handleParticlePickingLoad();
        } else if (newValue === "5") {
            handleCtfInfoLoad();
        }
    };

    // Enhanced image style
    const imageStyle: React.CSSProperties = {
        borderRadius: '12px',
        objectFit: 'contain',
        border: `2px solid ${theme.palette.divider}`,
        maxWidth: '100%',
        height: 'auto',
        boxShadow: theme.shadows[2]
    };

    // Update particle picking mutation
    const updatePPMutation = useUpdateParticlePicking();

    const handleSave = async () => {
        if (!selectedParticlePicking) return;

        try {
            await updatePPMutation.mutateAsync({
                oid: selectedParticlePicking.oid,
                image_id: selectedParticlePicking.image_id,
                data: selectedParticlePicking?.temp
            });
        } catch (error) {
            console.error('Failed to save particle picking:', error);
        }
    };

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

    // Particle picking selection handler
    const OnIppSelected = (event: SelectChangeEvent) => {
        const selectedValue = event.target.value;

        if (selectedValue && selectedValue.trim() !== '' && Array.isArray(ImageParticlePickings)) {
            const filteredRecords = ImageParticlePickings.filter(record => record.oid === selectedValue);
            if (filteredRecords.length > 0) {
                setSelectedParticlePicking(filteredRecords[0]);
            }
        } else {
            setSelectedParticlePicking(null);
        }
    };

    // Update particle picking handler
    const handleIppUpdate = (ipp: ParticlePickingDto) => {
        updateParticlePicking(ipp);
    };

    // Show empty state if no image is selected
    if (!selectedImage) {
        return (
            <Card sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CardContent sx={{ textAlign: 'center', py: 8 }}>
                    <FileImage size={64} color={theme.palette.text.secondary} />
                    <Typography variant="h6" color="text.secondary" sx={{ mt: 2 }}>
                        No Image Selected
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Select an image from the navigation panel to view details
                    </Typography>
                </CardContent>
            </Card>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Image Information Header */}
            <Card sx={{ mb: 2 }}>
                <CardHeader
                    avatar={<FileImage size={24} />}
                    title={
                        <Typography variant="h6" component="div" noWrap>
                            {selectedImage.name}
                        </Typography>
                    }
                    action={
                        <IconButton onClick={() => setIsInfoExpanded(!isInfoExpanded)}>
                            {isInfoExpanded ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                    }
                    sx={{ pb: 1 }}
                />

                <Collapse in={isInfoExpanded}>
                    <CardContent sx={{ pt: 0 }}>
                        <Stack
                            direction={isMobile ? "column" : "row"}
                            spacing={isMobile ? 1 : 3}
                            divider={!isMobile && <Divider orientation="vertical" flexItem />}
                        >
                            <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                                <InfoItem
                                    label="Magnification"
                                    value={selectedImage.mag ? `${selectedImage.mag}×` : undefined}
                                    icon={<Zap size={14} />}
                                />
                                <InfoItem
                                    label="Defocus"
                                    value={selectedImage.defocus ? `${selectedImage.defocus.toFixed(2)} μm` : undefined}
                                    icon={<TuneOutlined fontSize="small" />}
                                />
                            </Stack>

                            <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                                <InfoItem
                                    label="Pixel Size"
                                    value={selectedImage.pixelSize ? `${selectedImage.pixelSize.toFixed(2)} Å/pix` : undefined}
                                    icon={<Settings size={14} />}
                                />
                                <InfoItem
                                    label="Dose"
                                    value={selectedImage.dose}
                                    icon={<Analytics fontSize="small" />}
                                />
                            </Stack>

                            {!isMobile && (
                                <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                                    <InfoItem
                                        label="Session"
                                        value={sessionName}
                                        icon={<Database size={14} />}
                                    />
                                    <InfoItem
                                        label="Level"
                                        value={selectedImage.level}
                                        icon={<MuiInfoOutlined fontSize="small" />}
                                    />
                                </Stack>
                            )}
                        </Stack>
                    </CardContent>
                </Collapse>
            </Card>

            {/* Main Content with Tabs */}
            <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <TabContext value={activeTab}>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                        <Tabs
                            value={activeTab}
                            onChange={handleChange}
                            variant={isMobile ? "scrollable" : "standard"}
                            scrollButtons={isMobile ? "auto" : false}
                            sx={{
                                '& .MuiTab-root': {
                                    minHeight: 48,
                                    textTransform: 'none',
                                    fontWeight: 500
                                }
                            }}
                        >
                            {tabConfig.map((tab) => (
                                <Tab
                                    key={tab.value}
                                    label={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {tab.icon}
                                            <span>{isMobile ? tab.label.split(' ')[0] : tab.label}</span>
                                        </Box>
                                    }
                                    value={tab.value}
                                />
                            ))}
                        </Tabs>
                    </Box>

                    {/* Tab Panels */}
                    <Box sx={{ flex: 1, overflow: 'auto' }}>
                        <TabPanel value="1" sx={{ p: 3 }}>
                            <Box sx={{ textAlign: 'center' }}>
                                <ImageViewer
                                    imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    width={isMobile ? 300 : 1024}
                                    height={isMobile ? 300 : 1024}
                                    imageStyle={imageStyle}
                                />
                            </Box>
                        </TabPanel>

                        <TabPanel value="2" sx={{ p: 3 }}>
                            <Box sx={{ textAlign: 'center' }}>
                                <img
                                    src={`${BASE_URL}/fft_image?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="FFT image"
                                    style={{
                                        ...imageStyle,
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
                            <Stack spacing={3}>
                                {isCtfInfoLoading ? (
                                    <Stack spacing={2}>
                                        <Skeleton variant="rectangular" height={120} />
                                        <Skeleton variant="rectangular" height={400} />
                                    </Stack>
                                ) : isCtfInfoError ? (
                                    <Alert severity="error">
                                        Error loading CTF data: {isCtfInfoError.message}
                                    </Alert>
                                ) : ImageCtfData && ImageCtfData.defocus1 !== null ? (
                                    <>
                                        <CtfInfoCards
                                            defocus1Micrometers={ImageCtfData.defocus1}
                                            defocus2Micrometers={ImageCtfData.defocus2}
                                            angleAstigmatismDegrees={ImageCtfData.angleAstigmatism}
                                            resolutionAngstroms={ImageCtfData.resolution}
                                        />

                                        <Stack spacing={2}>
                                            <img
                                                src={`${BASE_URL}/ctf_image?image_type=powerspec&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                                alt="CTF power spectrum"
                                                style={{
                                                    ...imageStyle,
                                                    maxWidth: isMobile ? '100%' : '900px'
                                                }}
                                            />
                                            <img
                                                src={`${BASE_URL}/ctf_image?image_type=plots&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                                alt="CTF plots"
                                                style={{
                                                    ...imageStyle,
                                                    maxWidth: isMobile ? '100%' : '900px'
                                                }}
                                            />
                                        </Stack>
                                    </>
                                ) : (
                                    <Alert severity="info">
                                        No CTF data available for this image.
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
        </Box>
    );
};