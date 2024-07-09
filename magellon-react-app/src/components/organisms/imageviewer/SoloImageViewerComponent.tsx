import Box from "@mui/material/Box";
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';
import {SyntheticEvent, useState } from "react";
import {ButtonGroup, FormControl, Grid, InputLabel, MenuItem, Select, SelectChangeEvent, Stack} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import {AddOutlined, ControlPoint, HighlightOff, Palette, Save, Straighten, SyncOutlined} from "@mui/icons-material";
import {InfoLineComponent} from "./InfoLineComponent.tsx";
import {InfoOutlined} from "@ant-design/icons";
import ImageInfoDto, {SessionDto} from "./ImageInfoDto.ts";
import {settings} from "../../../core/settings.ts";
import ImageViewer from "./ImageViewer.tsx";
import ImageParticlePicking from "./ImageParticlePicking.tsx";
import {CreateParticlePickingDialog} from "./CreateParticlePickingDialog.tsx";
import {useImageParticlePickings, useUpdateParticlePicking} from "../../../services/api/ParticlePickingRestService.ts";
import {ParticlePickingDto} from "../../../domains/ParticlePickingDto.ts";


import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';

import { RichTreeView } from '@mui/x-tree-view/RichTreeView';
import { TreeItem2 } from '@mui/x-tree-view/TreeItem2';

import { JsonEditor as Editor } from 'jsoneditor-react'
import 'jsoneditor-react/es/editor.min.css';

import data from '../../../assets/data/editor.json'

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;
interface SoloImageViewerProps {
    selectedImage: ImageInfoDto | null;
}

export const SoloImageViewerComponent : React.FC<SoloImageViewerProps>= ({ selectedImage }) => {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState('1');
    const [selectedIpp, setSelectedIpp] = useState<ParticlePickingDto>(null);
    // const [updatedIpp, setUpdatedIpp] = useState<ParticlePickingDto>(null);


    const { data: ImageParticlePickings, isLoading: isIPPLoading, isError: isIPPError, refetch:refetchImageParticlePickings  } = useImageParticlePickings(selectedImage?.name,false);

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
    const handleLoad = () => {
        refetchImageParticlePickings();
    };
    const handleOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
    };

    const ParticlePickingTabClicked = () => {
        handleLoad();
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
    const [json, setJson] = useState(data)
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
                            <Tab label="Particle Picking" value="3" onClick={ParticlePickingTabClicked} />
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
                            <IconButton onClick={handleLoad} key="load"><SyncOutlined/></IconButton>
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
                        <img width={900} src={`${BASE_URL}/ctf_image?type=powerspec&name=${selectedImage?.name}`} alt="ctf power spec image" style={ImageStyle}/>
                        <img width={900} src={`${BASE_URL}/ctf_image?type=plots&name=${selectedImage?.name}`} alt="ctf plots image" style={ImageStyle}/>


                    </TabPanel>
                    <TabPanel value="6">
                        Frame Alignment
                    </TabPanel>
                    <TabPanel value="7">
                        <Grid container spacing={2}>
                            <Grid item xs={4}>
                                <Box sx={{ height: 620, flexGrow: 1, maxWidth: 200 }}>
                                    {/*<RichTreeView items={MUI_X_PRODUCTS} />*/}
                                    <SimpleTreeView>
                                        <TreeItem itemId="grid" label="Analysis">
                                            <TreeItem itemId="grid-community" label="FFT" />
                                            <TreeItem itemId="grid-pro" label="CTF" />
                                            <TreeItem itemId="grid-premium" label="Frame Alignment" />
                                            <TreeItem itemId="pp" label="Partilce Picking" />
                                        </TreeItem>
                                        <TreeItem itemId="pickers" label="Other">
                                            <TreeItem itemId="pickers-community" label="example 1" />
                                            <TreeItem itemId="pickers-pro" label="example 2" />
                                        </TreeItem>
                                    </SimpleTreeView>
                                </Box>
                            </Grid>
                            <Grid item xs={8}>
                                <Box>
                                    <ButtonGroup size="small">
                                        <FormControl sx={{m: 1, minWidth: 180}} size="small" variant="standard">
                                            <InputLabel id="demo-select-small-label">Particle Picking</InputLabel>
                                            <Select
                                                labelId="session_select-label"
                                                id="session_select2"
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
                                        <IconButton onClick={handleLoad} key="load"><SyncOutlined/></IconButton>
                                        <IconButton onClick={handleOpen} key="new"><AddOutlined/></IconButton>
                                        <IconButton key="save" onClick={handleSave}><Save/></IconButton>
                                        <IconButton key="four"><HighlightOff/></IconButton>
                                    </ButtonGroup>
                                    <Editor
                                        mode="tree"
                                        history
                                        value={json}
                                        onChange={setJson}
                                    />
                                </Box>
                            </Grid>
                        </Grid>





                    </TabPanel>
                </TabContext>
        </Stack>


    );
};
