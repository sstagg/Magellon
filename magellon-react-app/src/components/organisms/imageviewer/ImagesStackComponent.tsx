import ImageInfoDto, {PagedImageResponse} from "./ImageInfoDto.ts";
import {ImageList} from "@mui/material";
import './ImageViewerStyles.scss'
import {ThumbImage} from "./ThumbImage.tsx";
import {InfiniteData} from "react-query";
import {useState} from "react";

interface IImagesStackProps{
    images:InfiniteData<PagedImageResponse> | null;
    caption?:string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    level: number;
}
export const ImagesStackComponent = ({caption,images,onImageClick,level} : IImagesStackProps) => {
    const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null);


    const handleImageClick = (image: ImageInfoDto, column : number) => {
        // If the clicked image is already selected, unselect it
        // Otherwise, select the clicked image and unselect the previously selected image
        if (selectedImage === image) {
            // setSelectedImage(null);
            //onImageClick(null); // Pass null to indicate that no image is selected
        } else {
            setSelectedImage(image);
            onImageClick(image,column);
        }
    };


    return (
        <>
            {/*<h3>{caption}</h3>*/}
            <ImageList cols={1} rowHeight={170} sx={{ width: 170, height: 700,display:'block'  }}>
                {images?.pages?.map((_thePagedImageResponse, index) => (
                    _thePagedImageResponse.result.map((img,index)=>
                        <ThumbImage
                            image={img}
                            key={index}
                            isSelected={selectedImage === img}
                            onImageClick={() => handleImageClick(img)}
                            level={level}
                        />
                    )
                ))}
            </ImageList >
        </>

    );
};
