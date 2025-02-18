import { FC } from 'react'
import { ImageListItem, ImageListItemBar } from '@mui/material'
import ImageInfoDto from "../ImageInfoDto.ts";
import {settings} from "../../../../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL

interface ThumbImageProps {
    image: ImageInfoDto
    isSelected: boolean
    onImageClick: () => void
    level: number
}

export const ThumbImage: FC<ThumbImageProps> = ({
                                                    image,
                                                    isSelected,
                                                    onImageClick,
                                                    level
                                                }) => {
    const hasChildren = image.children_count > 0
    const className = `thumb-image ${hasChildren ? 'thumb-image-has-children' : ''} ${isSelected ? 'thumb-image-selected' : ''}`

    return (
        <ImageListItem onClick={onImageClick}>
            <img
                src={`${BASE_URL}/image_thumbnail?name=${image.name}`}
                alt={image.name}
                loading="lazy"
                className={className}
            />
            <ImageListItemBar
                title={`Children: ${image.children_count} Defocus: ${image.defocus}`}
                subtitle={image.name}
            />
        </ImageListItem>
    )
}