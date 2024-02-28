import Box from "@mui/material/Box";
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';
import {SyntheticEvent, useState } from "react";
import {ButtonGroup, FormControl, Grid, InputLabel, MenuItem, Select, Stack} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import {AddOutlined, ControlPoint, HighlightOff, Palette, Save, Straighten, SyncOutlined} from "@mui/icons-material";
import {InfoLineComponent} from "./InfoLineComponent.tsx";
import {InfoOutlined} from "@ant-design/icons";
import ImageInfoDto from "./ImageInfoDto.ts";
import {settings} from "../../../core/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ImageParticlePicking from "./ImageParticlePicking.tsx";
import {CreateParticlePickingDialog} from "./CreateParticlePickingDialog.tsx";
import {useImageParticlePickings} from "../../../services/api/ParticlePickingRestService.ts";


const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;
interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

export const SoloImageViewerComponent : React.FC<SoloImageViewerProps>= ({ selectedImage }) => {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState('1');


    const { data: ImageParticlePickings, isLoading: isIPPLoading, isError: isIPPError, refetch  } = useImageParticlePickings(selectedImage?.name,false);
    // const [selectedImage, setSelectedImage] = useState<ImageInfoDto>();
    const handleChange = (event: SyntheticEvent, newValue: string) => {
        setValue(newValue);
    };



    const ImageStyle: React.CSSProperties = {
        borderRadius: '10px',
        objectFit: 'cover',
        border: '3px solid rgba(215,215,225)',
    };

    const handleLoad = () => {
      refetch();
    };
    const handleOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
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
                        <InfoLineComponent icon={<InfoOutlined />} caption="Researcher" value="Shirin" />
                    </Stack>

                </Stack>


                <TabContext value={value}>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                        <TabList onChange={handleChange} aria-label="lab API tabs example">
                            <Tab label="Image" value="1" />
                            <Tab label="FFT" value="2" />
                            <Tab label="Particle Picking" value="3" />
                            <Tab label="Variations" value="4" />
                            <Tab label="CTF" value="5" />
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
                        <ButtonGroup size="small" >
                            {/*<IconButton  key="one" onClick={()=>console.log("clicked")}><Palette/></IconButton>*/}
                            {/*<IconButton  key="two"><Straighten/></IconButton>*/}


                            <FormControl sx={{ m: 1, minWidth: 180 }} size="small"  variant="standard" >
                                <InputLabel id="demo-select-small-label">Particle Picking</InputLabel>
                                <Select
                                    labelId="demo-select-small-label"
                                    id="demo-select-small"
                                    // value={selectedSession?.name}
                                    label="Session"
                                    // onChange={OnSessionSelected }
                                >
                                    <MenuItem value="none" >
                                        <em>None</em>
                                    </MenuItem>
                                    {ImageParticlePickings?.map((ipp) => (
                                        <MenuItem key={ipp.oid} value={ipp.oid}>
                                            {ipp.name}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                            <IconButton   onClick={handleLoad} key="load"><SyncOutlined/></IconButton>
                            <IconButton   onClick={handleOpen} key="new"><AddOutlined/></IconButton>
                            <IconButton  key="save"><Save/></IconButton>
                            <IconButton  key="four" ><HighlightOff/></IconButton>
                            <CreateParticlePickingDialog open={open} onClose={handleClose} ImageDto ={selectedImage}/>
                        </ButtonGroup>


                        <ImageParticlePicking
                            imageUrl={`${BASE_URL}/image_thumbnail?name=${selectedImage?.name}`}
                            width={1024}
                            height={1024}
                                               />

                    </TabPanel>
                    <TabPanel value="4">Item 4</TabPanel>
                    <TabPanel value="5">Item 5</TabPanel>
                    <TabPanel value="6">
                        Frame Alignment
                    </TabPanel>
                    <TabPanel value="7">


                    </TabPanel>
                </TabContext>
        </Stack>


    );
};
