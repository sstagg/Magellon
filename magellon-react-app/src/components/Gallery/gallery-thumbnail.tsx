// src/components/GalleryThumbnail.tsx
import React from 'react';
import { ImageListItem, ImageListItemBar, Tooltip } from '@mui/material';
import ImageInfoDto from "../panel/features/imageviewer/ImageInfoDto.ts";
import {settings} from "../../core/settings.ts";
// import ImageInfoDto from '../types/ImageInfoDto';
// import { settings } from '../core/settings';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface GalleryThumbnailProps {
  image: ImageInfoDto;
  isSelected: boolean;
  onImageClick: (image: ImageInfoDto) => void;
  size?: 'small' | 'medium' | 'large';
  showDetails?: boolean;
}

export const GalleryThumbnail: React.FC<GalleryThumbnailProps> = ({
  image,
  isSelected,
  onImageClick,
  size = 'medium',
  showDetails = true,
}) => {
  // Determine if the image has children
  const hasChildren = (image.children_count || 0) > 0;
  
  // Determine CSS classes based on state
  const className = `thumb-image ${hasChildren ? 'thumb-image-has-children' : ''} ${isSelected ? 'thumb-image-selected' : ''}`;
  
  // Size dimensions
  const sizeMap = {
    small: 120,
    medium: 170,
    large: 220,
  };
  
  const width = sizeMap[size];
  
  // Handle click event
  const handleClick = () => {
    onImageClick(image);
  };
  
  // Format defocus value for display
  const formatDefocus = (defocus?: number) => {
    if (defocus === undefined || defocus === null) return 'N/A';
    return `${defocus.toFixed(2)} μm`;
  };
  
  return (
    <Tooltip title={image.name || ''} placement="right" arrow>
      <ImageListItem 
        onClick={handleClick}
        sx={{ 
          width, 
          height: width,
          cursor: 'pointer',
        }}
      >
        <img
          src={`${BASE_URL}/image_thumbnail?name=${image.name}`}
          alt={image.name || 'Image thumbnail'}
          loading="lazy"
          className={className}
          style={{ 
            width: '100%', 
            height: '100%',
            objectFit: 'cover',
          }}
        />
        
        {showDetails && (
          <ImageListItemBar
            title={`${hasChildren ? `${image.children_count} child${image.children_count !== 1 ? 'ren' : ''}` : 'No children'}`}
            subtitle={`Defocus: ${formatDefocus(image.defocus)}`}
            sx={{
              borderRadius: '0 0 10px 10px',
              '& .MuiImageListItemBar-title': {
                fontSize: size === 'small' ? '0.75rem' : '0.875rem',
              },
              '& .MuiImageListItemBar-subtitle': {
                fontSize: size === 'small' ? '0.7rem' : '0.75rem',
              },
            }}
          />
        )}
      </ImageListItem>
    </Tooltip>
  );
};
