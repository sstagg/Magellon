import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { IMAGE_SIZE_DESKTOP, IMAGE_SIZE_MOBILE } from '../constants';
import {
    Box,
    Button,
    Card,
    CardContent,
    Typography,
    SelectChangeEvent,
    Alert,
    Skeleton,
    useTheme,
    useMediaQuery,
    Badge,
    Tab,
    Tabs,
    alpha,
} from "@mui/material";
import { TabContext, TabPanel } from '@mui/lab';
import {
    ImageOutlined,
    Timeline,
    ScatterPlot,
    Analytics,
    TuneOutlined,
} from "@mui/icons-material";
import {
    FileImage,
    Database,
    Eye,
} from "lucide-react";
import ImageInfoDto from "../../../entities/image/types.ts";
import { settings } from "../../../shared/config/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ParticleEditor from "./ParticleEditor.tsx";
import { ParticleSessionDialog } from "./ParticleSessionDialog.tsx";
import { useImageParticlePickings, useUpdateParticlePicking } from "../../../features/particle-picking/api/ParticlePickingRestService.ts";
import { ParticlePickingDto } from "../../../entities/particle-picking/types.ts";
import CtfInfoCards from "./CtfInfoCards.tsx";
import { useFetchImageCtfInfo } from "../../../features/ctf-analysis/api/CtfRestService.ts";
import MetadataExplorer from "./MetadataExplorer.tsx";
import { useFetchImageMetaData } from "../api/ImageMetaDataRestService.ts";
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import {ParticlePickingTab} from "./ParticlePickingTab.tsx";
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import { ImageInfoHeader } from "./ImageInfoHeader.tsx";
import { CTFAnalysisPanel } from "./CTFAnalysisPanel.tsx";
import { FrameAlignmentPanel } from "./FrameAlignmentPanel.tsx";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

export const ImageInspector: React.FC<SoloImageViewerProps> = ({ selectedImage }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Refs for advanced functionality
    const imageViewerRef = useRef<HTMLDivElement>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // UI state
    const [imageError, setImageError] = useState<string | null>(null);
    const [isInfoExpanded, setIsInfoExpanded] = useState(!isMobile);
    const [loadingProgress, setLoadingProgress] = useState<number>(0);

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

    // Only fetch metadata when Metadata tab is active
    const isMetadataTab = activeTab === '7';
    const { data: imageMetadata, error: metadataError, isLoading: isMetadataLoading, refetch: refetchMetadata } = useFetchImageMetaData(selectedImage?.name, isMetadataTab);

    // Only fetch FFT when FFT tab is active
    const fftImageUrl = (activeTab === '2' && selectedImage?.name)
        ? `${BASE_URL}/fft_image?name=${encodeURIComponent(selectedImage.name)}&sessionName=${sessionName}`
        : null;
    const { imageUrl: authenticatedFftUrl, isLoading: isFftLoading } = useAuthenticatedImage(fftImageUrl);

    // Only fetch CTF images when CTF tab is active
    const isCtfTab = activeTab === '5';
    const ctfPowerspecUrl = (isCtfTab && selectedImage?.name)
        ? `${BASE_URL}/ctf_image?image_type=powerspec&name=${encodeURIComponent(selectedImage.name)}&sessionName=${sessionName}`
        : null;
    const { imageUrl: authenticatedCtfPowerspecUrl, isLoading: isCtfPowerspecLoading } = useAuthenticatedImage(ctfPowerspecUrl);

    const ctfPlotsUrl = (isCtfTab && selectedImage?.name)
        ? `${BASE_URL}/ctf_image?image_type=plots&name=${encodeURIComponent(selectedImage.name)}&sessionName=${sessionName}`
        : null;
    const { imageUrl: authenticatedCtfPlotsUrl, isLoading: isCtfPlotsLoading } = useAuthenticatedImage(ctfPlotsUrl);

    // Only fetch FAO images when Frame Alignment tab is active
    const isFaoTab = activeTab === '6';
    const faoImageOneUrl = (isFaoTab && selectedImage?.name)
        ? `${BASE_URL}/fao_image?image_type=one&name=${encodeURIComponent(selectedImage.name)}&sessionName=${sessionName}`
        : null;
    const { imageUrl: authenticatedFaoOneUrl, isLoading: isFaoOneLoading } = useAuthenticatedImage(faoImageOneUrl);

    const faoImageTwoUrl = (isFaoTab && selectedImage?.name)
        ? `${BASE_URL}/fao_image?image_type=two&name=${encodeURIComponent(selectedImage.name)}&sessionName=${sessionName}`
        : null;
    const { imageUrl: authenticatedFaoTwoUrl, isLoading: isFaoTwoLoading } = useAuthenticatedImage(faoImageTwoUrl);

    // Only fetch CTF data when CTF tab is active or has been visited
    const {
        data: ImageCtfData,
        error: isCtfInfoError,
        isLoading: isCtfInfoLoading,
        refetch: refetchCtfInfo
    } = useFetchImageCtfInfo(selectedImage?.name, false);

    // Only fetch particle pickings when PP tab is active
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

    // Enhanced tab configuration with dynamic badges
    const tabConfig = useMemo(() => [
        {
            label: "Image",
            value: "1",
            icon: <FileImage size={18} />,
            badge: null
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
    ], [selectedParticlePicking, ImageCtfData]);

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
        boxShadow: theme.shadows[2],
    };

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
            <ImageInfoHeader
                selectedImage={selectedImage}
                sessionName={sessionName}
                isLoading={isCtfInfoLoading || isIPPLoading}
                loadingProgress={loadingProgress}
                isMobile={isMobile}
                isInfoExpanded={isInfoExpanded}
            />

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
                                <ImageViewer
                                    imageUrl={`${BASE_URL}/image_thumbnail?name=${encodeURIComponent(selectedImage?.name)}&sessionName=${sessionName}`}
                                    width={isMobile ? IMAGE_SIZE_MOBILE : IMAGE_SIZE_DESKTOP}
                                    height={isMobile ? IMAGE_SIZE_MOBILE : IMAGE_SIZE_DESKTOP}
                                    imageStyle={imageStyle}
                                />

                            </Box>
                        </TabPanel>

                        {/* Other tab panels remain similar but with enhanced styling... */}
                        <TabPanel value="2" sx={{ p: 3 }}>
                            <Box sx={{ textAlign: 'center' }}>
                                {isFftLoading ? (
                                    <Skeleton variant="rectangular" width="100%" height={400} />
                                ) : authenticatedFftUrl ? (
                                    <img
                                        src={authenticatedFftUrl}
                                        alt="FFT image"
                                        style={{
                                            ...imageStyle,
                                            maxWidth: isMobile ? '100%' : '900px'
                                        }}
                                        onError={() => setImageError('Failed to load FFT image')}
                                    />
                                ) : (
                                    <Alert severity="info" sx={{ mt: 2 }}>
                                        No FFT image available
                                    </Alert>
                                )}
                                {imageError && (
                                    <Alert severity="warning" sx={{ mt: 2 }}>
                                        {imageError}
                                    </Alert>
                                )}
                            </Box>
                        </TabPanel>

                        <TabPanel value="3" sx={{ p: 0, height: '100%' }}>
                            <ParticlePickingTab
                                selectedImage={selectedImage}
                                ImageParticlePickings={ImageParticlePickings}
                                isIPPLoading={isIPPLoading}
                                isIPPError={isIPPError}
                                onParticlePickingLoad={handleParticlePickingLoad}
                                OnIppSelected={OnIppSelected}
                                handleSave={handleSave}
                                handleOpen={handleOpen}
                                handleClose={handleClose}
                                handleIppUpdate={handleIppUpdate}
                            />
                        </TabPanel>


                        <TabPanel value="5" sx={{ p: 3 }}>
                            <CTFAnalysisPanel
                                ctfData={ImageCtfData}
                                isLoading={isCtfInfoLoading}
                                error={isCtfInfoError}
                                onRefresh={handleCtfInfoLoad}
                                powerspecUrl={authenticatedCtfPowerspecUrl}
                                isPowerspecLoading={isCtfPowerspecLoading}
                                plotsUrl={authenticatedCtfPlotsUrl}
                                isPlotsLoading={isCtfPlotsLoading}
                                isMobile={isMobile}
                            />
                        </TabPanel>




                        <TabPanel value="6" sx={{ p: 3 }}>
                            <FrameAlignmentPanel
                                faoOneUrl={authenticatedFaoOneUrl}
                                isFaoOneLoading={isFaoOneLoading}
                                faoTwoUrl={authenticatedFaoTwoUrl}
                                isFaoTwoLoading={isFaoTwoLoading}
                                imageStyle={imageStyle}
                                isMobile={isMobile}
                            />
                        </TabPanel>

                        <TabPanel value="7" sx={{ p: 3 }}>
                            <MetadataExplorer
                                categories={imageMetadata ?? null}
                                isLoading={isMetadataLoading}
                                error={metadataError as Error | null}
                                onRefresh={refetchMetadata}
                            />
                        </TabPanel>


                    </Box>
                </TabContext>
            </Card>

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
