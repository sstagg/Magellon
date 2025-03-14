import Box from "@mui/material/Box";
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';
import {SyntheticEvent, useEffect, useState} from "react";
import {ButtonGroup, FormControl, Grid, InputLabel, MenuItem, Select, SelectChangeEvent, Stack} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import {AddOutlined,  HighlightOff,  Save,  SyncOutlined} from "@mui/icons-material";
import {InfoLineComponent} from "./InfoLineComponent.tsx";
import {InfoOutlined} from "@ant-design/icons";
import ImageInfoDto, {ImageCtfInfo} from "./ImageInfoDto.ts";
import {settings} from "../../../../core/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ImageParticlePicking from "./ImageParticlePicking.tsx";
import {CreateParticlePickingDialog} from "./CreateParticlePickingDialog.tsx";
import {useImageParticlePickings, useUpdateParticlePicking} from "../../../../services/api/ParticlePickingRestService.ts";
import {ParticlePickingDto} from "../../../../domains/ParticlePickingDto.ts";



// import data from '../../../assets/data/editor.json'
import CtfInfoCards from "./CtfInfoCards.tsx";
import {useFetchImageCtfInfo} from "../../../../services/api/CtfRestService.ts";
// import {useFetchImageMetaData} from "../../../services/api/ImageMetaDataRestService.ts";
import ImageMetadataDisplay from "./ImageMetadataDisplay.tsx";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;

export interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

export const SoloImageViewerComponent : React.FC<SoloImageViewerProps>= ({ selectedImage }) => {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState('1');
    const [selectedIpp, setSelectedIpp] = useState<ParticlePickingDto>(null);

    // const [ctfData, setCtfData] = useState<ImageCtfInfo>({
    //     defocus1: null,
    //     defocus2: null,
    //     angleAstigmatism: null,
    //     resolution: null,
    // });

    const { data:ImageCtfData, error:isCtfInfoError, isLoading: isCtfInfoLoading  ,refetch:refetchCtfInfo } = useFetchImageCtfInfo(selectedImage?.name, false);
    const { data: ImageParticlePickings, isLoading: isIPPLoading, isError: isIPPError, refetch:refetchImageParticlePickings  } = useImageParticlePickings(selectedImage?.name,false);

    useEffect(() => {
        if (selectedImage?.name) {
            refetchCtfInfo();
        }
    }, [selectedImage?.name, refetchCtfInfo]);

    // const [selectedImage, setSelectedImage] = useState<ImageInfoDto>();
    const handleChange = (event: SyntheticEvent, newValue: string) => {
        setValue(newValue);
    };



    const ImageStyle: React.CSSProperties = {
        borderRadius: '10px',
        objectFit: 'cover',
        border: '3px solid rgba(215,215,225)',
    };

    const updatePPMutation = useUpdateParticlePicking();
    const handleSave = () => {
        try {
            updatePPMutation.mutateAsync({
                oid: selectedIpp.oid,
                image_id: selectedIpp.image_id,
                data: selectedIpp?.temp
            });
            // Handle success
        } catch (error) {
            // Handle error
            console.error(error)
        }
    };
    const handleParticlePickingLoad = () => {
        refetchImageParticlePickings();
    };
    const handleCtfInfoLoad = () => {
        refetchCtfInfo();
    };
    const handleOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
    };

    const ParticlePickingTabClicked = () => {
        handleParticlePickingLoad();
    };

    const OnIppSelected = (event: SelectChangeEvent) => {
        //debugger;
        const selectedValue = event.target.value;

        if (selectedValue && selectedValue.trim() !== '' && Array.isArray(ImageParticlePickings)) {
            const filteredRecords = ImageParticlePickings.filter(record => record.oid === selectedValue);
            if (filteredRecords.length > 0) {
                setSelectedIpp(filteredRecords[0]);
            }
        }else{
            setSelectedIpp(null);
        }
    };

    const handleIppUpdate = (ipp : ParticlePickingDto) => {
        // Update the selectedIpp state with the updatedIpp
        setSelectedIpp(ipp) ;
        // console.log(updatedIpp);
        console.log(ipp);
        //setSelectedIpp(updatedIpp);
        // You can perform any additional actions here if needed
    };

    return (

        <Stack>

                <Stack   direction="column">
                    <InfoLineComponent icon={<InfoOutlined />} caption="File Name" value={selectedImage?.name} />
                    <Stack direction="row" >
                        <InfoLineComponent icon={<InfoOutlined />} caption="Mag" value={selectedImage?.mag} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Dose" value={selectedImage?.dose} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Defocus" value={`${selectedImage?.defocus} μm`} />
                    </Stack>
                    <Stack direction="row" >
                        {/*<InfoLine icon={<Info />} caption="PixelSize" value={imageInfo?.pixelSize} />*/}
                        {/*<InfoLine icon={<Mail />} caption="Created" value={imageInfo?.filename} />*/}
                        <InfoLineComponent icon={<InfoOutlined />} caption="PixelSize" value={`${selectedImage?.pixelSize} Å/pix`} />
                        <InfoLineComponent icon={<InfoOutlined />} caption="Researcher" value="Magellon User" />
                    </Stack>

                </Stack>


                <TabContext value={value}>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                        <TabList onChange={handleChange} aria-label="lab API tabs example">
                            <Tab label="Image" value="1" />
                            <Tab label="FFT" value="2" />
                            <Tab label="Particle Picking" value="3" onClick={ParticlePickingTabClicked} />
                            {/*<Tab label="Variations" value="4" />*/}
                            <Tab label="CTF" value="5" onClick={handleCtfInfoLoad} />
                            <Tab label="Frame Alignment" value="6" />
                            <Tab label="Meta" value="7" />
                        </TabList>
                    </Box>
                    <TabPanel value="1">
                        {/*<img src={`/images-controller/${selectedImages?.name}.png`} alt="image" style={ImageStyle}/>*/}
                        {/*<img  src={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}`} alt="image" style={ImageStyle} />*/}
                        <ImageViewer imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}`} width={1024} height={1024} style={ImageStyle} />
                    </TabPanel>
                    <TabPanel value="2">
                        <img  src={`${BASE_URL}/fft_image?name=${selectedImage?.name}`} alt="image" style={ImageStyle} />
                    </TabPanel>
                    <TabPanel value="3">
                        <h3>{selectedIpp?.name ?? "Empty"}</h3>
                        <ButtonGroup size="small">
                            {/*<IconButton  key="one" onClick={()=>console.log("clicked")}><Palette/></IconButton>*/}
                            {/*<IconButton  key="two"><Straighten/></IconButton>*/}


                            <FormControl sx={{m: 1, minWidth: 180}} size="small" variant="standard">
                                <InputLabel id="demo-select-small-label">Particle Picking</InputLabel>
                                <Select
                                    labelId="session_select-label"
                                    id="session_select"
                                    value={selectedIpp?.oid}
                                    label="Session"
                                     onChange={OnIppSelected }
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
                            <CreateParticlePickingDialog open={open} onClose={handleClose} ImageDto={selectedImage}/>
                        </ButtonGroup>


                        <ImageParticlePicking
                            image={selectedImage}
                            ipp={selectedIpp}
                            imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}`}
                            width={1024}
                            height={1024}
                            onIppUpdate={handleIppUpdate}
                        />

                    </TabPanel>
                    <TabPanel value="4">Item 4</TabPanel>
                    <TabPanel value="5">


                        <div>
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
                        </div>


                        <img width={900} src={`${BASE_URL}/ctf_image?image_type=powerspec&name=${selectedImage?.name}`} alt="ctf power spec image" style={ImageStyle}/>
                        <img width={900} src={`${BASE_URL}/ctf_image?image_type=plots&name=${selectedImage?.name}`} alt="ctf plots image" style={ImageStyle}/>


                    </TabPanel>
                    <TabPanel value="6">
                        <img width={900} src={`${BASE_URL}/fao_image?image_type=one&name=${selectedImage?.name}`} alt="motioncor image one" style={ImageStyle}/>
                        <img width={900} src={`${BASE_URL}/fao_image?image_type=two&name=${selectedImage?.name}`} alt="motioncor image two" style={ImageStyle}/>

                    </TabPanel>
                    <TabPanel value="7">
                        <ImageMetadataDisplay selectedImage={selectedImage} />

                    </TabPanel>
                </TabContext>
        </Stack>


    );
};
