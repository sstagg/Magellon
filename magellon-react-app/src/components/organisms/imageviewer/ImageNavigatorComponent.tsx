import {
    ButtonGroup,
    Card,
    CardActionArea,
    CardContent,
    CardMedia,
    Grid,
    ImageList,
    ImageListItem,
    Stack
} from "@mui/material";
import Typography from "@mui/material/Typography";
import {ImagesStackComponent} from "./ImagesStackComponent.tsx";
import ImageInfoDto, {AtlasImageDto, PagedImageResponse} from "./ImageInfoDto.ts";
import {InfiniteData, useInfiniteQuery, useQuery} from "react-query";
import {fetchImagesPage} from "../../../services/api/imagesApiReactQuery.tsx";
import IconButton from "@mui/material/IconButton";
import {EyeOutlined} from "@ant-design/icons";
import {useEffect, useState} from "react";
import InfoIcon from "@mui/icons-material/Info";
import {ImageColumnComponent} from "./ImageColumnComponent.tsx";
import {ImageColumnState} from "../../views/panel/ImagesPageView.tsx";
import {ThumbImage} from "./ThumbImage.tsx";
import AtlasImage, {ImageMap} from "./AtlasImage.tsx";


interface ImageNavigatorProps {
    onImageClick: (imageInfo: ImageInfoDto, column : number ) => void;
    selectedImage: ImageInfoDto | null;
    ImageColumns: ImageColumnState[];
    Atlases: AtlasImageDto[];
}



// function jsonToImageMap(jsonString: string | undefined): ImageMap | null {
//     try {
//         if (jsonString === undefined) {
//             console.error('JSON string is undefined');
//             return null;
//         }
// debugger;
//         const parsedJson = JSON.parse(jsonString);
//         return parsedJson as ImageMap;
//     } catch (error) {
//         console.error('Error parsing JSON:', error);
//         return null;
//     }
// }
export const ImageNavigatorComponent: React.FC<ImageNavigatorProps>  = ({ onImageClick , selectedImage,ImageColumns,Atlases }) => {

    const [isAtlasVisible, setIsAtlasVisible] = useState(true);
    const [currentAtlas, setCurrentAtlas] = useState<AtlasImageDto>(null);

    useEffect(() => {
        if (Atlases && Atlases.length > 0) {
            setCurrentAtlas(Atlases[0]);
        }
    }, [Atlases]);

    const handleAtlasClick = (atlas: AtlasImageDto) => {
        setCurrentAtlas(atlas);
    };


    // const handleLoadNextPage = () => {
    //     // fetchNextPage();
    // };

    return (
        <Grid container direction="column">
            <Grid item container >
                <Stack>
                    <ButtonGroup size="small" >
                        <IconButton  key="one" ><InfoIcon/></IconButton>
                        <IconButton  key="four"onClick={()=>setIsAtlasVisible(!isAtlasVisible)}><EyeOutlined/></IconButton>
                    </ButtonGroup>
                    {isAtlasVisible ? (
                        <Grid container >
                            <Grid item>
                                <ImageList cols={1} rowHeight={170} sx={{ width: 170, height: 400,display:'block'  }}>
                                    {Atlases?.map((atlas, index) => (
                                        <ImageListItem key={index}  onClick={() => handleAtlasClick(atlas)}>
                                            <img  src={`http://127.0.0.1:8000/web/atlas-image?name=${atlas?.name}`} alt="atlas" className={"thumb-image"} style={{ cursor: 'pointer' }} />
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
            <Grid item container sx={{ marginTop:3 }} >
                <ImagesStackComponent caption={ImageColumns[0].caption} images={ImageColumns[0].images} level={0} onImageClick={(image) => onImageClick(image,0)} />
                <ImagesStackComponent caption={ImageColumns[1].caption} images={ImageColumns[1].images} level={1} onImageClick={(image) => onImageClick(image,1)} />
                <ImagesStackComponent caption={ImageColumns[2].caption} images={ImageColumns[2].images}level={2} onImageClick={(image) => onImageClick(image,2)} />
                <ImagesStackComponent caption={ImageColumns[3].caption} images={ImageColumns[3].images} level={3} onImageClick={(image) => onImageClick(image,3)} />
            </Grid>
        </Grid>
    );
};
