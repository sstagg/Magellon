import {
    ButtonGroup,
    Card,
    CardContent, FormControl,
    Grid,
    ImageList,
    ImageListItem, InputLabel, MenuItem, Select, SelectChangeEvent,
    Stack
} from "@mui/material";
import Typography from "@mui/material/Typography";
import {ImagesStackComponent} from "./ImagesStackComponent.tsx";
import ImageInfoDto, {AtlasImageDto, SessionDto} from "./ImageInfoDto.ts";
import IconButton from "@mui/material/IconButton";
import {EyeOutlined} from "@ant-design/icons";
import {useEffect, useState} from "react";
import {ImageColumnState} from "../../views/panel/ImagesPageView.tsx";
import AtlasImage from "./AtlasImage.tsx";
import {settings} from "../../../core/settings.ts";
import {AccountTreeRounded, GridViewRounded} from "@mui/icons-material";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;

interface ImageNavigatorProps {
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void,
    selectedImage: ImageInfoDto | null,
    selectedSession: SessionDto | null,
    ImageColumns: ImageColumnState[],
    Atlases: AtlasImageDto[],
    Sessions: SessionDto[],
    OnSessionSelected :(event: SelectChangeEvent) => void
}



export const ImageNavigatorComponent: React.FC<ImageNavigatorProps>  = ({
                                                                            onImageClick,
                                                                            selectedImage,
                                                                            selectedSession,
                                                                            ImageColumns,
                                                                            Atlases,
                                                                            Sessions,
                                                                            OnSessionSelected
                                                                        }) => {

    const [isAtlasVisible, setIsAtlasVisible] = useState(true);
    const [currentAtlas, setCurrentAtlas] = useState<AtlasImageDto>(null);
    const [viewMode, setViewMode] = useState<'grid' | 'tree'>('grid');

    useEffect(() => {
        if (Atlases && Atlases.length > 0) {
            setCurrentAtlas(Atlases[0]);
        }
    }, [Atlases]);

    const handleAtlasClick = (atlas: AtlasImageDto) => {
        setCurrentAtlas(atlas);
    };

    const renderNavView = () => {
        switch (viewMode) {
            case 'grid':
                return renderGridView();
            //case 'table':
               // return renderTableView();
            case 'tree':
                return renderTreeView();
            default:
                return null;
        }
    };
    const renderTreeView = () => {
        // Render tree view
        return <div>🌳🌲 Get ready for a Tree View coming soon! Stay tuned! 🌳🌲</div>;
    };
    const renderGridView = () => {
        // Render grid view
        return(
                <Grid item container sx={{ marginTop:3 }} >
                    <ImagesStackComponent caption={ImageColumns[0].caption} images={ImageColumns[0].images} level={0} onImageClick={(image) => onImageClick(image,0)} />
                    <ImagesStackComponent caption={ImageColumns[1].caption} images={ImageColumns[1].images} level={1} onImageClick={(image) => onImageClick(image,1)} />
                    <ImagesStackComponent caption={ImageColumns[2].caption} images={ImageColumns[2].images}level={2} onImageClick={(image) => onImageClick(image,2)} />
                    <ImagesStackComponent caption={ImageColumns[3].caption} images={ImageColumns[3].images} level={3} onImageClick={(image) => onImageClick(image,3)} />
                </Grid>
            );
    };

    return (
        <Grid container direction="column">
            <Grid item container >
                <Stack>
                    <FormControl sx={{ m: 1, minWidth: 120 }} size="small"  variant="standard" >
                        <InputLabel id="demo-select-small-label">Session</InputLabel>
                        <Select
                            labelId="demo-select-small-label"
                            id="demo-select-small"
                            value={selectedSession?.name}
                            label="Session"
                             onChange={OnSessionSelected }
                        >
                            <MenuItem value="none" >
                                <em>None</em>
                            </MenuItem>
                            {Sessions?.map((session) => (
                                <MenuItem key={session.Oid} value={session.name}>
                                    {session.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <ButtonGroup size="small" >
                        <IconButton  key="one" onClick={()=>setIsAtlasVisible(!isAtlasVisible)}><EyeOutlined/></IconButton>
                        <IconButton  key="two"  onClick={() => setViewMode('grid')}><GridViewRounded/></IconButton>
                        <IconButton  key="three"  onClick={() => setViewMode('tree')}><AccountTreeRounded/></IconButton>
                    </ButtonGroup>
                    {isAtlasVisible ? (
                        <Grid container >
                            <Grid item>
                                <ImageList cols={1} rowHeight={170} sx={{ width: 170, height: 400,display:'block'  }}>
                                    {Atlases?.map((atlas, index) => (
                                        <ImageListItem key={index}  onClick={() => handleAtlasClick(atlas)}>
                                            <img  src={`${BASE_URL}/atlas-image?name=${atlas?.name}`} alt="atlas" className={"thumb-image"} style={{ cursor: 'pointer' }} />
                                        </ImageListItem>
                                    ))}
                                </ImageList >
                            </Grid>
                            <Grid item>
                                <Card sx={{maxWidth: 345, marginLeft: 2}}>
                                    <AtlasImage imageMapJson={currentAtlas?.meta} finalWidth={300} finalHeight={300}
                                          name={currentAtlas?.name}      backgroundColor={"black"} onImageClick={onImageClick}/>
                                    <CardContent>
                                        <Typography gutterBottom variant="h5" component="div">
                                            Name: {currentAtlas?.name}
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        </Grid>
                    ) : null}
                </Stack>

            </Grid>
            {renderNavView()}
        </Grid>
    );
};
