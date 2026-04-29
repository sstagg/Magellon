import React, { useState, useMemo } from "react";
import { Box, Tooltip, Skeleton, useTheme } from "@mui/material";
import { FileImage, FolderOpen } from "lucide-react";
import ImageInfoDto from "../../../entities/image/types.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import { THUMBNAIL_SIZES } from '../constants.ts';

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
    const [loaded, setLoaded] = useState(false);
    const theme = useTheme();

    const { currentSession } = useImageViewerStore();
    const sessionName = currentSession?.name || '';

    const childrenCount = image.children_count || 0;
    const hasChildren = childrenCount > 0;
    const imageName = image.name || 'Unnamed Image';
    const imageDefocus = image.defocus !== undefined ? `${image.defocus?.toFixed(2)}μm` : 'N/A';

    const dimensions = useMemo(() => {
        const mapping: Record<string, { width: number; height: number }> = {
            small: THUMBNAIL_SIZES.SMALL,
            medium: THUMBNAIL_SIZES.MEDIUM,
            large: THUMBNAIL_SIZES.LARGE,
        };
        return mapping[size];
    }, [size]);

    const apiUrl = useMemo(() =>
            `${BASE_URL}/image_thumbnail?name=${encodeURIComponent(image.name)}&sessionName=${sessionName}`,
        [image.name, sessionName]
    );

    const { imageUrl, isLoading, error: imageError } = useAuthenticatedImage(apiUrl);
    const hasError = !!imageError;

    const handleClick = () => {
        const imageWithLevel = { ...image, level };
        onImageClick(imageWithLevel, level);
    };

    const tooltipContent = (
        <Box sx={{ p: 1, maxWidth: 220 }}>
            <strong>Name:</strong> {imageName}<br />
            {image.defocus !== undefined && <><strong>Defocus:</strong> {imageDefocus}<br /></>}
            {image.mag && <><strong>Magnification:</strong> {image.mag}&times;<br /></>}
            {image.pixelSize && <><strong>Pixel Size:</strong> {image.pixelSize?.toFixed(2)} &Aring;/pix<br /></>}
            {hasChildren && <><strong>Child Images:</strong> {childrenCount}</>}
        </Box>
    );

    const showSkeleton = isLoading && !loaded && !hasError;

    return (
        <Tooltip title={tooltipContent} placement="right" arrow>
            <Box
                component="button"
                onClick={handleClick}
                sx={{
                    /* reset button defaults */
                    border: 'none',
                    padding: 0,
                    background: 'none',
                    font: 'inherit',
                    cursor: 'pointer',
                    textAlign: 'left',

                    /* layout */
                    position: 'relative',
                    overflow: 'hidden',
                    borderRadius: '8px',
                    width: dimensions.width,
                    height: fixedHeight ? dimensions.height : dimensions.width,
                    aspectRatio: '1 / 1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',

                    /* selection ring */
                    outline: isSelected
                        ? `2px solid ${theme.palette.primary.main}`
                        : `1px solid ${theme.palette.divider}`,
                    outlineOffset: isSelected ? '0px' : '-1px',

                    /* hover scale */
                    transition: 'transform 0.15s ease, outline 0.15s ease',
                    '&:hover': {
                        transform: 'scale(1.02)',
                    },
                }}
            >
                {/* Skeleton placeholder */}
                {showSkeleton && (
                    <Skeleton
                        variant="rectangular"
                        width="100%"
                        height="100%"
                        animation="wave"
                        sx={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            borderRadius: '8px',
                        }}
                    />
                )}

                {/* Error state */}
                {hasError && (
                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '100%',
                            height: '100%',
                            backgroundColor:
                                theme.palette.mode === 'dark'
                                    ? 'rgba(0,0,0,0.2)'
                                    : 'rgba(0,0,0,0.05)',
                            color: theme.palette.text.secondary,
                            borderRadius: '8px',
                            p: 1,
                            textAlign: 'center',
                        }}
                    >
                        <FileImage size={24} style={{ marginBottom: 4 }} />
                        <Box sx={{ fontSize: '0.7rem' }}>Image not available</Box>
                    </Box>
                )}

                {/* Image. The src is a blob URL produced by
                    useAuthenticatedImage — the bytes are already in
                    memory, so no loading="lazy" (Chromium's lazy
                    intersection observer treats display:none images as
                    out-of-viewport and defers the load forever, which
                    leaves onLoad unfired and the img permanently
                    hidden). */}
                {!hasError && imageUrl && (
                    <img
                        src={imageUrl}
                        alt={imageName}
                        onLoad={() => setLoaded(true)}
                        style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            display: loaded ? 'block' : 'none',
                        }}
                    />
                )}

                {/* Children count badge — top-right */}
                {hasChildren && (
                    <Box
                        sx={{
                            position: 'absolute',
                            top: 4,
                            right: 4,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px',
                            backgroundColor:
                                theme.palette.mode === 'dark'
                                    ? 'rgba(0,0,0,0.75)'
                                    : 'rgba(255,255,255,0.9)',
                            color: theme.palette.primary.main,
                            borderRadius: '10px',
                            px: 0.75,
                            py: 0.25,
                            fontSize: '0.65rem',
                            fontWeight: 600,
                            lineHeight: 1,
                            boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
                            zIndex: 2,
                            pointerEvents: 'none',
                        }}
                    >
                        <FolderOpen size={12} />
                        {childrenCount}
                    </Box>
                )}

                {/* Name gradient overlay — bottom */}
                {showMetadata && (
                    <Box
                        sx={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 100%)',
                            px: 0.75,
                            py: 0.5,
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'flex-end',
                            pointerEvents: 'none',
                            minHeight: '36px',
                        }}
                    >
                        <Box
                            component="span"
                            sx={{
                                color: '#fff',
                                fontSize: '0.68rem',
                                fontWeight: 500,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {imageName}
                        </Box>
                        {imageDefocus !== 'N/A' && (
                            <Box
                                component="span"
                                sx={{
                                    color: 'rgba(255,255,255,0.7)',
                                    fontSize: '0.6rem',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                Def: {imageDefocus}
                            </Box>
                        )}
                    </Box>
                )}
            </Box>
        </Tooltip>
    );
};
