import IconButton from "@mui/material/IconButton";
import ImageInfoDto from "./ImageInfoDto.ts";
import ImageListItemBar from "@mui/material/ImageListItemBar";
import { ImageListItem, Box } from "@mui/material";
import { useState } from "react";
import { settings } from "../../../core/settings.ts";
import { useImageViewerStore } from './store/imageViewerStore.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface IThumbImagesProps {
    image: ImageInfoDto;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    level: number;
    isSelected: boolean;
    fixedHeight?: boolean; // Add prop to control consistent sizing
    size?: 'small' | 'medium' | 'large'; // Control thumbnail size
}

export const ThumbImage = ({
                               image,
                               onImageClick,
                               level,
                               isSelected,
                               fixedHeight = false,
                               size = 'medium'
                           }: IThumbImagesProps) => {
    const [isHovered, setIsHovered] = useState(false);
    const childrenCount = image.children_count || 0;

    // Get the current session from the store
    const { currentSession } = useImageViewerStore();
    const sessionName = currentSession?.name || '';

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
        image.level = level;
        onImageClick(image, level);
    };

    const barStyle = {
        borderRadius: isHovered ? '7px' : '0', // 5px for the bottom, 0 for the other sides
        margin: isHovered ? '1px' : '0', // 10px margins for left, bottom, and right when hovered
    };

    // Size mapping for consistent dimensions
    const sizeMapping = {
        small: { width: 120, height: 120 },
        medium: { width: 150, height: 150 },
        large: { width: 200, height: 200 }
    };

    // Get dimensions based on size prop
    const dimensions = sizeMapping[size];

    return (
        <Box
            sx={{
                width: '100%',
                height: fixedHeight ? dimensions.height : 'auto',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                overflow: 'hidden'
            }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <ImageListItem
                sx={{
                    width: '100%',
                    maxWidth: dimensions.width,
                    height: 'auto',
                    aspectRatio: '1/1'
                }}
            >
                <IconButton
                    sx={{
                        padding: '0px',
                        width: '100%',
                        height: '100%',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center'
                    }}
                    onClick={handleClick}
                >
                    <img
                        src={`${BASE_URL}/image_thumbnail?name=${image.name}&sessionName=${sessionName}`}
                        alt="image"
                        loading="lazy"
                        className={combinedClassName}
                        style={{
                            width: '100%',
                            height: 'auto',
                            objectFit: 'cover',
                            aspectRatio: '1/1'
                        }}
                    />
                </IconButton>
                <ImageListItemBar
                    title={`${image.children_count} De: ${image.defocus}`}
                    subtitle={image.name}
                    sx={barStyle} // Apply the border-radius and margin styles
                />
            </ImageListItem>
        </Box>
    );
};