import ImageInfoDto, {PagedImageResponse} from "./ImageInfoDto.ts";
import {ImageList, ImageListItem, Stack} from "@mui/material";
import './ImageViewerStyles.scss'
import {ThumbImage} from "./ThumbImage.tsx";
import {InfiniteData} from "react-query";

interface IImagesStackProps{
    images:InfiniteData<PagedImageResponse> | null;
    caption?:string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    level: number;
}
export const ImagesStackComponent = ({caption,images,onImageClick,level} : IImagesStackProps) => {
    // const thumbImageStyle: React.CSSProperties = {
    //     borderRadius: '10px',
    //     width: '150px',
    //     height: '150px',
    //     objectFit: 'cover',
    //     border: active ? '3px solid #ff0000' : '3px solid rgba(215, 215, 225)'
    // };


    return (
        <>
            {/*<h3>{caption}</h3>*/}
            <ImageList cols={1} rowHeight={170} sx={{ width: 170, height: 700,display:'block'  }}>
                {images?.pages?.map((_thePagedImageResponse, index) => (
                    _thePagedImageResponse.result.map((img,index)=>
                        <ThumbImage image={img} key={index} onImageClick={onImageClick} level={level}/>
                    )
                ))}
            </ImageList >
        </>

    );
};
