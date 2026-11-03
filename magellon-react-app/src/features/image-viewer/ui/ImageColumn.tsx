import React, { useState, useEffect, useCallback, useRef } from "react";
import {
    ImageList,
    Box,
    Paper,
    CircularProgress,
    Button,
    useTheme,
    alpha
} from "@mui/material";
import type { InfiniteData } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { PagedImageResponse } from "../../../entities/image/types.ts";
import type ImageInfoDto from "../../../entities/image/types.ts";
import { ImageThumbnail } from "./ImageThumbnail.tsx";
import './ImageViewerStyles.css';
import { useImageViewerStore } from '../model/imageViewerStore';

interface ImagesStackProps {
    images: InfiniteData<PagedImageResponse> | null;
    caption?: string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    level: number;
    direction?: 'vertical' | 'horizontal';
    width?: number;
    height?: number;
    onLoadMore?: () => void;
    isLoadingMore?: boolean;
    /** The column's selection when it can come from outside (an atlas tile). */
    selected?: ImageInfoDto | null;
}

/** The list with the selected image first if its page isn't loaded yet. */
export const withSelected = (images: ImageInfoDto[], selected?: ImageInfoDto | null): ImageInfoDto[] =>
    selected && !images.some((image) => image.oid === selected.oid) ? [selected, ...images] : images;

export const ImageColumn: React.FC<ImagesStackProps> = ({
                                                            caption: _caption,
                                                            images,
                                                            onImageClick,
                                                            level,
                                                            direction = 'vertical',
                                                            width: _width,
                                                            height,
                                                            onLoadMore,
                                                            isLoadingMore: loadingMore = false,
                                                            selected
                                                        }) => {
    const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null);
    const listRef = useRef<HTMLDivElement>(null);

    const { currentImage } = useImageViewerStore();
    const theme = useTheme();

    const allImages = withSelected(images?.pages?.flatMap(page => page.result) || [], selected);
    const hasNextPage = !!onLoadMore && images?.pages?.[images.pages.length - 1]?.next_page != null;

    useEffect(() => {
        if (selected !== undefined) {
            setSelectedImage(selected);
        } else if (currentImage && currentImage.level === level) {
            setSelectedImage(currentImage);
        }
    }, [selected, currentImage, level]);

    // Bring the selection into view, however it was made.
    useEffect(() => {
        if (selected?.oid) {
            listRef.current?.querySelector(`[data-image-oid="${selected.oid}"]`)
                ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
    }, [selected?.oid]);

    const handleImageClick = useCallback((image: ImageInfoDto) => {
        if (image !== null && image.oid !== selectedImage?.oid) {
            setSelectedImage(image);
            onImageClick(image, level);
        }
    }, [selectedImage, onImageClick, level]);

    const hasImages = allImages.length > 0;
    const isHorizontal = direction === 'horizontal';

    const containerWidth = isHorizontal ? '100%' : 180;
    const containerHeight = isHorizontal ? (height || 200) : '100%';
    const maxHeight = isHorizontal ? (height || 200) : 700;

    if (!hasImages) {
        return null;
    }

    return (
        <Paper
            ref={listRef}
            elevation={0}
            sx={{
                width: containerWidth,
                height: containerHeight,
                maxHeight,
                maxWidth: '100%',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: 'transparent',
                position: 'relative',
                overflow: 'hidden',
                borderRadius: 1
            }}
        >
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
                }}
            >
                {isHorizontal ? (
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
                        }}
                    >
                        {allImages.map((img, index) => (
                            <Box
                                key={`${level}-${img.oid || index}`}
                                data-image-oid={img.oid}
                                sx={{
                                    flexShrink: 0,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
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
                                    onClick={onLoadMore}
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
                            <div key={`${level}-${img.oid || index}`} data-image-oid={img.oid}>
                                <ImageThumbnail
                                    image={img}
                                    isSelected={selectedImage?.oid === img.oid}
                                    onImageClick={handleImageClick}
                                    level={level}
                                    fixedHeight={true}
                                    size="medium"
                                />
                            </div>
                        ))}
                    </ImageList>
                )}

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
                            onClick={onLoadMore}
                            disabled={loadingMore}
                            startIcon={loadingMore ? <CircularProgress size={14} /> : <ChevronDown size={14} />}
                            sx={{ fontSize: '0.75rem' }}
                        >
                            {loadingMore ? 'Loading...' : 'Load more'}
                        </Button>
                    </Box>
                )}
            </Box>
        </Paper>
    );
};