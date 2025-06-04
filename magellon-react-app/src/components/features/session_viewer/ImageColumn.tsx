import React, { useState, useEffect, useCallback } from "react";
import {
    ImageList,
    Box,
    Typography,
    Paper,
    CircularProgress,
    Button,
    useTheme,
    alpha
} from "@mui/material";
import { InfiniteData } from "react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import ImageInfoDto, { PagedImageResponse } from "./ImageInfoDto.ts";
import { ImageThumbnail } from "./ImageThumbnail.tsx";
import './ImageViewerStyles.scss';
import { useImageViewerStore } from './store/imageViewerStore';


interface ImagesStackProps {
    /**
     * Collection of images to display
     */
    images: InfiniteData<PagedImageResponse> | null;
    /**
     * Optional caption for the stack
     */
    caption?: string;
    /**
     * Callback when an image is clicked
     */
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    /**
     * Hierarchical level of images in this stack
     */
    level: number;
    /**
     * Layout direction for the image stack
     */
    direction?: 'vertical' | 'horizontal';
    /**
     * Custom width (useful for horizontal layout)
     */
    width?: number;
    /**
     * Custom height (useful for horizontal layout)
     */
    height?: number;

}

/**
 * Component that displays a vertical or horizontal stack of image thumbnails
 */
export const ImageColumn: React.FC<ImagesStackProps> = ({
                                                            caption,
                                                            images,
                                                            onImageClick,
                                                            level,
                                                            direction = 'vertical',
                                                            width,
                                                            height



                                                        }) => {
    // Local state
    const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);

    // Access store to check if any image matches current column selection
    const { currentImage } = useImageViewerStore();
    const theme = useTheme();

    // Get all image results from all pages
    const allImages = images?.pages?.flatMap(page => page.result) || [];

    // Check if there are more pages to load
    const hasNextPage = images?.pages?.[images.pages.length - 1]?.next_page != null;

    // Update selected image if store's current image is in this column level
    useEffect(() => {
        if (currentImage && currentImage.level === level) {
            setSelectedImage(currentImage);
        }
    }, [currentImage, level]);

    // Handle image click - only update if different image selected
    const handleImageClick = useCallback((image: ImageInfoDto) => {
        if (image !== null && image.oid !== selectedImage?.oid) {
            setSelectedImage(image);
            onImageClick(image, level);
        }
    }, [selectedImage, onImageClick, level]);

    // Calculate if images are available to show
    const hasImages = allImages.length > 0;

    // Determine if we're in horizontal mode
    const isHorizontal = direction === 'horizontal';

    // Calculate container dimensions
    const containerWidth = isHorizontal ? '100%' : 180;
    const containerHeight = isHorizontal ? (height || 200) : '100%';
    const maxHeight = isHorizontal ? (height || 200) : 700;

    // DEBUG: Log the props being received
    console.log('ImageColumn Debug:', {
        level,
        direction,
        isHorizontal,
        width,
        height,
        containerWidth,
        containerHeight,
        imageCount: allImages.length,
        caption
    });

    // Return early if no images to show
    if (!hasImages) {
        return null;
    }

    return (
        <Paper
            elevation={0}
            sx={{
                width: containerWidth,
                height: containerHeight,
                maxHeight: maxHeight,
                maxWidth: '100%', // Prevent exceeding container width
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: 'transparent',
                position: 'relative',
                overflow: 'hidden',
                // DEBUG: Add visible border to see container bounds
                border: `2px solid ${isHorizontal ? 'red' : 'blue'}`,
                borderRadius: 1
            }}
        >
            {/* DEBUG: Show direction info */}
            <Typography
                variant="caption"
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    background: isHorizontal ? 'red' : 'blue',
                    color: 'white',
                    padding: '2px 4px',
                    zIndex: 10,
                    fontSize: '10px'
                }}
            >
                {isHorizontal ? 'HORIZONTAL' : 'VERTICAL'} L{level}
            </Typography>

            <Box
                sx={{
                    overflow: isHorizontal ? 'hidden' : 'auto',
                    scrollbarWidth: 'thin',
                    '&::-webkit-scrollbar': {
                        width: isHorizontal ? '4px' : '4px',
                        height: isHorizontal ? '4px' : '4px',
                    },
                    '&::-webkit-scrollbar-track': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.05),
                    },
                    '&::-webkit-scrollbar-thumb': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                        borderRadius: '3px',
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.3),
                        },
                    },
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    // DEBUG: Add background color to see the scrollable area
                    backgroundColor: alpha(theme.palette.warning.main, 0.1)
                }}
            >
                {isHorizontal ? (
                    // Horizontal layout
                    <Box
                        sx={{
                            width: '100%',
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'row',
                            alignItems: 'center',
                            gap: 1,
                            p: 1,
                            overflowX: 'auto',
                            overflowY: 'hidden',
                            // DEBUG: Add background to see image container
                            backgroundColor: alpha(theme.palette.success.main, 0.1),
                            border: '1px dashed green'
                        }}
                    >
                        {allImages.map((img, index) => (
                            <Box
                                key={`${level}-${img.oid || index}`}
                                sx={{
                                    flexShrink: 0,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    // DEBUG: Add background to see individual image containers
                                    backgroundColor: alpha(theme.palette.info.main, 0.1),
                                    border: '1px solid purple',
                                    width: '120px',
                                    height: '120px'
                                }}
                            >
                                <ImageThumbnail
                                    image={img}
                                    isSelected={selectedImage?.oid === img.oid}
                                    onImageClick={handleImageClick}
                                    level={level}
                                    fixedHeight={true}
                                    size="small"
                                />
                            </Box>
                        ))}

                        {/* Load more button for horizontal */}
                        {hasNextPage && (
                            <Box sx={{
                                flexShrink: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '100px',
                                height: '120px',
                                p: 1
                            }}>
                                <Button
                                    variant="text"
                                    size="small"
                                    onClick={() => {
                                        if (images && !loadingMore) {
                                            setLoadingMore(true);
                                            // This is a placeholder for the fetchNextPage function
                                            // In a real implementation, you would call images.fetchNextPage()
                                            // and then set loadingMore to false when complete
                                            setTimeout(() => setLoadingMore(false), 1000);
                                        }
                                    }}
                                    disabled={loadingMore}
                                    startIcon={loadingMore ? <CircularProgress size={14} /> : <ChevronRight size={14} />}
                                    sx={{
                                        fontSize: '0.75rem',
                                        flexDirection: 'column',
                                        height: '100%'
                                    }}
                                >
                                    {loadingMore ? 'Loading...' : 'Load more'}
                                </Button>
                            </Box>
                        )}
                    </Box>
                ) : (
                    // Vertical layout
                    <ImageList
                        cols={1}
                        gap={8}
                        sx={{
                            width: 170,
                            margin: 0,
                            padding: '4px',
                            paddingBottom: hasNextPage ? '40px' : '8px'
                        }}
                    >
                        {allImages.map((img, index) => (
                            <ImageThumbnail
                                key={`${level}-${img.oid || index}`}
                                image={img}
                                isSelected={selectedImage?.oid === img.oid}
                                onImageClick={handleImageClick}
                                level={level}
                                fixedHeight={true}
                                size="medium"
                            />
                        ))}
                    </ImageList>
                )}

                {/* "Load more" button for vertical layout */}
                {!isHorizontal && hasNextPage && (
                    <Box
                        sx={{
                            position: 'sticky',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            display: 'flex',
                            justifyContent: 'center',
                            padding: '8px',
                            backgroundColor: alpha(theme.palette.background.paper, 0.8),
                            backdropFilter: 'blur(4px)',
                            borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                        }}
                    >
                        <Button
                            variant="text"
                            size="small"
                            onClick={() => {
                                if (images && !loadingMore) {
                                    setLoadingMore(true);
                                    // This is a placeholder for the fetchNextPage function
                                    // In a real implementation, you would call images.fetchNextPage()
                                    // and then set loadingMore to false when complete
                                    setTimeout(() => setLoadingMore(false), 1000);
                                }
                            }}
                            disabled={loadingMore}
                            startIcon={loadingMore ? <CircularProgress size={14} /> : <ChevronDown size={14} />}
                            sx={{ fontSize: '0.75rem' }}
                        >
                            {loadingMore ? 'Loading...' : 'Load more'}
                        </Button>
                    </Box>
                )}

                {/* Debug info */}
                <Box sx={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    background: 'black',
                    color: 'white',
                    padding: '2px 4px',
                    fontSize: '10px',
                    zIndex: 10
                }}>
                    Images: {allImages.length} | {isHorizontal ? `W:${containerWidth}` : `H:${containerHeight}`}
                </Box>
            </Box>
        </Paper>
    );
};