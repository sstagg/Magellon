import IconButton from "@mui/material/IconButton";
import ImageInfoDto from "./ImageInfoDto.ts";
import ImageListItemBar from "@mui/material/ImageListItemBar";
import InfoIcon from '@mui/icons-material/Info';
import {ImageListItem} from "@mui/material";
import {useState} from "react";
interface IThumbImagesProps{
    image:ImageInfoDto;
    onImageClick: (imageInfo: ImageInfoDto, column : number) => void;
    level: number;
    // key:number;
}

export const ThumbImage = ({image,onImageClick,level} : IThumbImagesProps) => {
    const [isHovered, setIsHovered] = useState(false);
    const [isSelected, setIsSelected] = useState(false);


    const childrenCount = image.children_count || 0;

    let hasChildrenClass = childrenCount > 0 ? 'thumb-image-has-children' : '';
    const hasSelectedClass = isSelected ? 'thumb-image-selected' : '';
    const handleMouseEnter = () => {
        setIsHovered(true);
    };

    const handleMouseLeave = () => {
        setIsHovered(false);
    };

    const handleClick = () => {
         // debugger;
        image.level=level;
        console.log("image is " + JSON.stringify(image));
        onImageClick(image,level);
        setIsSelected(!isSelected); // Toggle the selected state
    };



    const barStyle = {
        borderRadius: isHovered ? '7px' : '0', // 5px for the bottom, 0 for the other sides
        margin: isHovered ? '1px' : '0', // 10px margins for left, bottom, and right when hovered
    };

    const combinedClassName = `thumb-image ${hasChildrenClass} ${hasSelectedClass}`;

    // console.log(isSelected,combinedClassName);

    return (
        <ImageListItem
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <IconButton   sx={{padding:'0px'}} onClick={handleClick} >
                <img
                    src={`http://127.0.0.1:8000/web/image_thumbnail?name=${image.name}`}
                    alt="image"
                    loading="lazy"
                    className={combinedClassName}
                />
            </IconButton>
            {isHovered && (
                <ImageListItemBar
                    title={`${image.children_count} De: ${image.defocus}`}
                    subtitle={image.name}
                    // actionPosition="left"
                    // actionIcon={
                    //     <IconButton sx={{ color: 'rgba(232,237,241,0.54)' }} aria-label={`info about ${image.name}`}>
                    //         <InfoIcon />
                    //     </IconButton>
                    // }
                    sx={barStyle} // Apply the border-radius and margin styles
                />
            )}
        </ImageListItem>
    );
};
