import IconButton from "@mui/material/IconButton";
import ImageInfoDto from "./ImageInfoDto.ts";
import ImageListItemBar from "@mui/material/ImageListItemBar";
import {ImageListItem} from "@mui/material";
import {useState} from "react";
import {settings} from "../../../../core/settings.ts";
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;
interface IThumbImagesProps{
    image:ImageInfoDto;
    onImageClick: (imageInfo: ImageInfoDto, column : number) => void;
    level: number;
    isSelected: boolean;
}

export const ThumbImage = ({image,onImageClick,level,isSelected} : IThumbImagesProps) => {
    const [isHovered, setIsHovered] = useState(false);
    const childrenCount = image.children_count || 0;

    const hasChildrenClass = childrenCount > 0 ? 'thumb-image-has-children' : '';
    const hasSelectedClass = isSelected ? 'thumb-image-selected' : '';

    const combinedClassName = `thumb-image ${hasChildrenClass} ${hasSelectedClass}`;

    const handleMouseEnter = () => {
        setIsHovered(true);
    };

    const handleMouseLeave = () => {
        setIsHovered(false);
    };

    const handleClick = () => {
         // debugger;
        image.level=level;
        // console.log("image is " + JSON.stringify(image));
        onImageClick(image,level);
        // setIsSelected(!isSelected); // Toggle the selected state
    };

    const barStyle = {
        borderRadius: isHovered ? '7px' : '0', // 5px for the bottom, 0 for the other sides
        margin: isHovered ? '1px' : '0', // 10px margins for left, bottom, and right when hovered
    };

    return (
        <ImageListItem
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <IconButton   sx={{padding:'0px'}} onClick={handleClick} >
                <img
                    src={`${BASE_URL}/image_thumbnail?name=${image.name}`}
                    alt="image"
                    loading="lazy"
                    className={combinedClassName}
                />
            </IconButton>
            <ImageListItemBar
                title={`${image.children_count} De: ${image.defocus}`}
                subtitle={image.name}
                sx={barStyle} // Apply the border-radius and margin styles
            />
            {/*{isHovered && (*/}

            {/*)}*/}
        </ImageListItem>
    );
};
