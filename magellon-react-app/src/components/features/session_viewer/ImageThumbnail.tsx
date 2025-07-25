import React, { useState, useMemo } from "react";
import {
    IconButton,
    ImageListItemBar,
    ImageListItem,
    Box,
    Tooltip,
    Badge,
    Skeleton,
    useTheme
} from "@mui/material";
import { FileImage, Folder, FolderOpen } from "lucide-react";
import ImageInfoDto from "./ImageInfoDto.ts";
import { settings } from "../../../core/settings.ts";
import { useImageViewerStore } from './store/imageViewerStore.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface ThumbImageProps {
    image: ImageInfoDto;
    onImageClick: (imageInfo: ImageInfoDto, column?: number) => void;
    level: number;
    isSelected: boolean;
    fixedHeight?: boolean;
    size?: 'small' | 'medium' | 'large';
    showMetadata?: boolean;
}

export const ImageThumbnail = ({
                                   image,
                                   onImageClick,
                                   level,
                                   isSelected,
                                   fixedHeight = false,
                                   size = 'medium',
                                   showMetadata = true
                               }: ThumbImageProps) => {
    const [isHovered, setIsHovered] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);
    const theme = useTheme();

    const { currentSession } = useImageViewerStore();
    const sessionName = currentSession?.name || '';

    const childrenCount = image.children_count || 0;
    const hasChildren = childrenCount > 0;
    const imageName = image.name || 'Unnamed Image';
    const imageDefocus = image.defocus !== undefined ? `${image.defocus?.toFixed(2)}μm` : 'N/A';

    const imageClasses = useMemo(() => {
        const classes = ['thumb-image'];
        if (hasChildren) classes.push('thumb-image-has-children');
        if (isSelected) classes.push('thumb-image-selected');
        return classes.join(' ');
    }, [hasChildren, isSelected]);

    const dimensions = useMemo(() => {
        const sizeMapping = {
            small: { width: 120, height: 120 },
            medium: { width: 150, height: 150 },
            large: { width: 200, height: 200 }
        };
        return sizeMapping[size];
    }, [size]);

    const imageUrl = useMemo(() =>
            `${BASE_URL}/image_thumbnail?name=${image.name}&sessionName=${sessionName}`,
        [image.name, sessionName]
    );

    const handleMouseEnter = () => setIsHovered(true);
    const handleMouseLeave = () => setIsHovered(false);

    const handleClick = () => {
        const imageWithLevel = { ...image, level };
        onImageClick(imageWithLevel, level);
    };

    const handleImageLoad = () => setIsLoading(false);
    const handleImageError = () => {
        setIsLoading(false);
        setHasError(true);
    };

    const tooltipContent = (
        <Box sx={{ p: 1, maxWidth: 220 }}>
            <strong>Name:</strong> {imageName}<br />
            {image.defocus !== undefined && <><strong>Defocus:</strong> {imageDefocus}<br /></>}
            {image.mag && <><strong>Magnification:</strong> {image.mag}×<br /></>}
            {image.pixelSize && <><strong>Pixel Size:</strong> {image.pixelSize.toFixed(2)} Å/pix<br /></>}
            {hasChildren && <><strong>Child Images:</strong> {childrenCount}</>}
        </Box>
    );

    const barStyle = {
        borderRadius: isHovered ? '0 0 8px 8px' : '0',
        margin: isHovered ? '1px' : '0',
        '.MuiImageListItemBar-title': {
            fontSize: '0.75rem',
            fontWeight: 500,
            textOverflow: 'ellipsis',
            overflow: 'hidden'
        },
        '.MuiImageListItemBar-subtitle': {
            fontSize: '0.7rem',
            textOverflow: 'ellipsis',
            overflow: 'hidden',
            whiteSpace: 'nowrap'
        }
    };

    return (
        <Tooltip title={tooltipContent} placement="right" arrow>
            <Box
                sx={{
                    width: '100%',
                    height: fixedHeight ? dimensions.height : 'auto',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                    transition: 'transform 0.2s',
                    transform: isHovered ? 'scale(1.02)' : 'scale(1)',
                }}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
            >
                <ImageListItem
                    sx={{
                        width: '100%',
                        maxWidth: dimensions.width,
                        height: 'auto',
                        aspectRatio: '1/1',
                        position: 'relative',
                        boxShadow: isSelected ? `0 0 0 2px ${theme.palette.primary.main}` : 'none',
                        borderRadius: '8px',
                        overflow: 'hidden'
                    }}
                >
                    <IconButton
                        sx={{
                            padding: 0,
                            width: '100%',
                            height: '100%',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            borderRadius: '8px',
                        }}
                        onClick={handleClick}
                        disableRipple={false}
                    >
                        {isLoading && (
                            <Skeleton
                                variant="rectangular"
                                width="100%"
                                height="100%"
                                animation="wave"
                                sx={{ position: 'absolute', top: 0, left: 0, borderRadius: '8px' }}
                            />
                        )}

                        {hasError ? (
                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    width: '100%',
                                    height: '100%',
                                    backgroundColor: theme.palette.mode === 'dark'
                                        ? 'rgba(0, 0, 0, 0.2)'
                                        : 'rgba(0, 0, 0, 0.05)',
                                    color: theme.palette.text.secondary,
                                    borderRadius: '8px',
                                    p: 1,
                                    textAlign: 'center'
                                }}
                            >
                                <FileImage size={24} style={{ marginBottom: 4 }} />
                                <Box sx={{ fontSize: '0.7rem' }}>Image not available</Box>
                            </Box>
                        ) : (
                            <img
                                src={imageUrl}
                                alt={imageName}
                                loading="lazy"
                                className={imageClasses}
                                style={{
                                    width: '100%',
                                    height: 'auto',
                                    objectFit: 'cover',
                                    aspectRatio: '1/1'
                                }}
                                onLoad={handleImageLoad}
                                onError={handleImageError}
                            />
                        )}
                    </IconButton>

                    {/* Enhanced Folder badge for images with children */}
                    {hasChildren && (
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 6,
                                right: 6,
                                backgroundColor: theme.palette.mode === 'dark'
                                    ? 'rgba(0, 0, 0, 0.7)'
                                    : 'rgba(255, 255, 255, 0.9)',
                                borderRadius: '6px',
                                width: 32,
                                height: 32,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                                zIndex: 2,
                                padding: 0,
                                border: `2px solid ${theme.palette.primary.main}`,
                            }}
                        >
                            <FolderOpen
                                size={20}
                                color={theme.palette.primary.main}
                                fill={theme.palette.primary.main}
                                style={{
                                    display: 'block',
                                    margin: 'auto',
                                    strokeWidth: 2.5
                                }}
                            />
                        </Box>
                    )}

                    {showMetadata && (
                        <ImageListItemBar
                            title={`${hasChildren ? `${childrenCount} Imgs` : ''} ${imageDefocus !== 'N/A' ? `Def: ${imageDefocus}` : ''}`}
                            subtitle={imageName}
                            sx={barStyle}
                        />
                    )}
                </ImageListItem>
            </Box>
        </Tooltip>
    );
};