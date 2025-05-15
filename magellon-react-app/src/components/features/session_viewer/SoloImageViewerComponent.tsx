import Box from "@mui/material/Box";
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';
import { SyntheticEvent, useEffect } from "react";
import { ButtonGroup, FormControl, InputLabel, MenuItem, Select, SelectChangeEvent, Stack, useTheme } from "@mui/material";
import IconButton from "@mui/material/IconButton";
import { AddOutlined, HighlightOff, Save, SyncOutlined } from "@mui/icons-material";
import { InfoLineComponent } from "./InfoLineComponent.tsx";
import { InfoOutlined } from "@ant-design/icons";
import ImageInfoDto from "./ImageInfoDto.ts";
import { settings } from "../../../core/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ImageParticlePicking from "./ImageParticlePicking.tsx";
import { CreateParticlePickingDialog } from "./CreateParticlePickingDialog.tsx";
import { useImageParticlePickings, useUpdateParticlePicking } from "../../../services/api/ParticlePickingRestService.ts";
import { ParticlePickingDto } from "../../../domains/ParticlePickingDto.ts";
import CtfInfoCards from "./CtfInfoCards.tsx";
import { useFetchImageCtfInfo } from "../../../services/api/CtfRestService.ts";
import ImageMetadataDisplay from "./ImageMetadataDisplay.tsx";
import { useImageViewerStore } from './store/imageViewerStore.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

export const SoloImageViewerComponent: React.FC<SoloImageViewerProps> = ({ selectedImage }) => {
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

    const theme = useTheme();

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

    // Refresh CTF info when selected image changes
    useEffect(() => {
        if (selectedImage?.name) {
            refetchCtfInfo();
        }
    }, [selectedImage?.name, refetchCtfInfo]);

    // Handle tab change
    const handleChange = (event: SyntheticEvent, newValue: string) => {
        setActiveTab(newValue);
    };

    // Style for image display
    const ImageStyle: React.CSSProperties = {
        borderRadius: '10px',
        objectFit: 'cover',
        border: '3px solid rgba(215,215,225)',
        maxWidth: '100%',
    };

    // Update particle picking mutation
    const updatePPMutation = useUpdateParticlePicking();

    const handleSave = () => {
        try {
            updatePPMutation.mutateAsync({
                oid: selectedParticlePicking.oid,
                image_id: selectedParticlePicking.image_id,
                data: selectedParticlePicking?.temp
            });
        } catch (error) {
            console.error(error);
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

    // Tab click handlers
    const ParticlePickingTabClicked = () => {
        handleParticlePickingLoad();
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

    if (!selectedImage) {
        return (
            <Box sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                color: 'text.secondary',
                p: 3
            }}>
                No image selected. Select an image from the navigator.
            </Box>
        );
    }

    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'auto'
        }}>
            {/* Image info section */}
            <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Stack spacing={1}>
                    <InfoLineComponent icon={<InfoOutlined />} caption="File Name" value={selectedImage?.name} />
                    <Stack direction="row" spacing={3}>
                        <InfoLineComponent icon={<InfoOutlined />} caption="Mag" value={selectedImage?.mag} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Dose" value={selectedImage?.dose} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Defocus" value={`${selectedImage?.defocus} μm`} />
                    </Stack>
                    <Stack direction="row" spacing={3}>
                        <InfoLineComponent icon={<InfoOutlined />} caption="PixelSize" value={`${selectedImage?.pixelSize} Å/pix`} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Researcher" value="Magellon User" />
                    </Stack>
                </Stack>
            </Box>

            {/* Tabs section - takes all remaining height */}
            <Box sx={{
                flexGrow: 1,
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0 // This is crucial for flex child to not overflow its parent
            }}>
                <TabContext value={activeTab}>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                        <TabList
                            onChange={handleChange}
                            aria-label="image viewer tabs"
                            variant="scrollable"
                            scrollButtons="auto"
                        >
                            <Tab label="Image" value="1" />
                            <Tab label="FFT" value="2" />
                            <Tab label="Particle Picking" value="3" onClick={ParticlePickingTabClicked} />
                            <Tab label="CTF" value="5" onClick={handleCtfInfoLoad} />
                            <Tab label="Frame Alignment" value="6" />
                            <Tab label="Meta" value="7" />
                        </TabList>
                    </Box>

                    {/* Custom styling for TabPanel to fill available space */}
                    <Box sx={{ flexGrow: 1, overflow: 'auto', position: 'relative' }}>
                        <TabPanel
                            value="1"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center'
                            }}
                        >
                            <ImageViewer
                                imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                width={1024}
                                height={1024}
                                style={ImageStyle}
                            />
                        </TabPanel>

                        <TabPanel
                            value="2"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center'
                            }}
                        >
                            <img
                                src={`${BASE_URL}/fft_image?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                alt="FFT image"
                                style={ImageStyle}
                            />
                        </TabPanel>

                        <TabPanel
                            value="3"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto',
                                display: 'flex',
                                flexDirection: 'column'
                            }}
                        >
                            <Box sx={{ mb: 2 }}>
                                <h3>{selectedParticlePicking?.name ?? "Empty"}</h3>
                                <ButtonGroup size="small">
                                    <FormControl sx={{m: 1, minWidth: 180}} size="small" variant="standard">
                                        <InputLabel id="demo-select-small-label">Particle Picking</InputLabel>
                                        <Select
                                            labelId="session_select-label"
                                            id="session_select"
                                            value={selectedParticlePicking?.oid || ""}
                                            label="Session"
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
                                    <IconButton onClick={handleParticlePickingLoad} key="load"><SyncOutlined/></IconButton>
                                    <IconButton onClick={handleOpen} key="new"><AddOutlined/></IconButton>
                                    <IconButton key="save" onClick={handleSave}><Save/></IconButton>
                                    <IconButton key="four"><HighlightOff/></IconButton>
                                    <CreateParticlePickingDialog open={isParticlePickingDialogOpen} onClose={handleClose} ImageDto={selectedImage}/>
                                </ButtonGroup>
                            </Box>

                            <Box sx={{ display: 'flex', justifyContent: 'center', flexGrow: 1, overflow: 'auto' }}>
                                <ImageParticlePicking
                                    image={selectedImage}
                                    ipp={selectedParticlePicking}
                                    imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    width={1024}
                                    height={1024}
                                    onCirclesSelected={(circles) => console.log("Circles selected:", circles)}
                                    onIppUpdate={handleIppUpdate}
                                />
                            </Box>
                        </TabPanel>

                        <TabPanel value="4">Item 4</TabPanel>

                        <TabPanel
                            value="5"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center'
                            }}
                        >
                            <Box sx={{ width: '100%', mb: 3 }}>
                                {isCtfInfoLoading ? (
                                    <p>Loading CTF data...</p>
                                ) : isCtfInfoError ? (
                                    <p>Error loading CTF data: {isCtfInfoError.message}</p>
                                ) : ImageCtfData && ImageCtfData.defocus1 !== null ? (
                                    <CtfInfoCards
                                        defocus1Micrometers={ImageCtfData.defocus1}
                                        defocus2Micrometers={ImageCtfData.defocus2}
                                        angleAstigmatismDegrees={ImageCtfData.angleAstigmatism}
                                        resolutionAngstroms={ImageCtfData.resolution}
                                    />
                                ) : (
                                    <p>No CTF data available.</p>
                                )}
                            </Box>

                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'center' }}>
                                <img
                                    src={`${BASE_URL}/ctf_image?image_type=powerspec&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="CTF power spec image"
                                    style={ImageStyle}
                                />
                                <img
                                    src={`${BASE_URL}/ctf_image?image_type=plots&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                    alt="CTF plots image"
                                    style={ImageStyle}
                                />
                            </Box>
                        </TabPanel>

                        <TabPanel
                            value="6"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: 3
                            }}
                        >
                            <img
                                src={`${BASE_URL}/fao_image?image_type=one&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                alt="Motion correction image one"
                                style={ImageStyle}
                            />
                            <img
                                src={`${BASE_URL}/fao_image?image_type=two&name=${selectedImage?.name}&sessionName=${sessionName}`}
                                alt="Motion correction image two"
                                style={ImageStyle}
                            />
                        </TabPanel>

                        <TabPanel
                            value="7"
                            sx={{
                                height: '100%',
                                p: 2,
                                overflow: 'auto'
                            }}
                        >
                            <ImageMetadataDisplay selectedImage={selectedImage} />
                        </TabPanel>
                    </Box>
                </TabContext>
            </Box>
        </Box>
    );
};