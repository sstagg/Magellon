import React, { useEffect, useState, useMemo } from "react";
import { Box, Typography, Skeleton, Alert, Paper, CircularProgress } from "@mui/material";
import { Folder, AlertTriangle } from "lucide-react";
import ImageInfoDto from "./ImageInfoDto.ts";
import { ImagesStackComponent } from "./ImagesStackComponent.tsx";
import { usePagedImages } from "../../../services/api/usePagedImagesHook.ts";

interface ImageColumnProps {
    /**
     * Callback when an image is clicked
     */
    onImageClick: (imageInfo: ImageInfoDto) => void;
    /**
     * Parent image that serves as filter for this column's images
     */
    parentImage: ImageInfoDto | null;
    /**
     * Current session name
     */
    sessionName: string;
    /**
     * Column caption/title
     */
    caption: string;
    /**
     * Hierarchical level of images in this column
     */
    level: number;
}

/**
 * ImageColumnComponent displays a column of images in a hierarchical view.
 * Each column shows images that are children of the selected image in the previous column.
 */
export const ImageColumnComponent: React.FC<ImageColumnProps> = ({
                                                                     onImageClick,
                                                                     parentImage,
                                                                     sessionName,
                                                                     level,
                                                                     caption
                                                                 }) => {
    // State to track the parent ID for filtering
    const [parentId, setParentId] = useState<string | null>(null);

    // Configuration
    const pageSize = 20; // Increased for better user experience

    // Determine if loading should occur based on parent image
    const shouldLoad = useMemo(() => {
        if (level === 0) return true; // Always load the first level

        // For deeper levels, only load if parent exists and has children
        return parentImage !== null && (parentImage.children_count || 0) > 0;
    }, [level, parentImage]);

    // Update parent ID when parent image changes
    useEffect(() => {
        const parentImageLevel = parentImage?.level ?? 0;

        // Set parent ID if parent image is at the previous level
        if (parentImage && parentImageLevel === level - 1) {
            setParentId(parentImage.oid);
        } else {
            setParentId(null);
        }

        // Only refetch if we should load data for this column
        if (shouldLoad) {
            refetch();
        }
    }, [parentImage, level, shouldLoad]);

    // Fetch paged images from API
    const {
        data,
        error,
        isLoading,
        isSuccess,
        isError,
        refetch,
        fetchNextPage,
        hasNextPage,
        isFetching,
    } = usePagedImages({
        sessionName,
        parentId,
        pageSize,
        level,
        idName: caption,
        enabled: shouldLoad
    });

    // Loading state with skeleton
    if (isLoading) {
        return (
            <Paper
                elevation={0}
                sx={{
                    width: 180,
                    height: 700,
                    p: 1,
                    backgroundColor: 'transparent',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1
                }}
            >
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                    {caption}
                </Typography>

                {Array.from({ length: 5 }).map((_, index) => (
                    <Skeleton
                        key={index}
                        variant="rectangular"
                        width={160}
                        height={160}
                        sx={{ borderRadius: 1, mb: 1 }}
                    />
                ))}

                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                    <CircularProgress size={24} />
                </Box>
            </Paper>
        );
    }

    // Error state
    if (isError && error) {
        return (
            <Paper
                elevation={0}
                sx={{
                    width: 180,
                    height: 'auto',
                    p: 1,
                    backgroundColor: 'transparent'
                }}
            >
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                    {caption}
                </Typography>

                <Alert
                    severity="error"
                    icon={<AlertTriangle size={24} />}
                    sx={{ mb: 1 }}
                >
                    Error loading images
                </Alert>

                <Typography variant="caption" color="error">
                    {error.message}
                </Typography>
            </Paper>
        );
    }

    // Empty state - no parent selected or parent has no children
    if (level > 0 && (!parentImage || (parentImage.children_count || 0) === 0)) {
        return (
            <Paper
                elevation={0}
                sx={{
                    width: 180,
                    height: 'auto',
                    p: 1,
                    backgroundColor: 'transparent',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'flex-start'
                }}
            >
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold', alignSelf: 'flex-start' }}>
                    {caption}
                </Typography>

                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: 200,
                        width: '100%',
                        borderRadius: 1,
                        backgroundColor: 'rgba(0, 0, 0, 0.03)',
                        p: 2
                    }}
                >
                    <Folder size={32} color="#9e9e9e" />
                    <Typography variant="body2" color="textSecondary" sx={{ mt: 2, textAlign: 'center' }}>
                        {level === 0
                            ? "No images available"
                            : parentImage
                                ? "No child images"
                                : "Select an image"}
                    </Typography>
                </Box>
            </Paper>
        );
    }

    // Successful data loading state
    return (
        <Box sx={{ width: 180, position: 'relative' }}>
            <Typography
                variant="subtitle2"
                sx={{
                    mb: 1,
                    fontWeight: 'bold',
                    position: 'sticky',
                    top: 0,
                    backgroundColor: theme => theme.palette.background.default,
                    zIndex: 1,
                    p: 1,
                    borderRadius: 1
                }}
            >
                {caption}
                {isSuccess && data?.pages && data.pages[0].total_count > 0 && (
                    <Typography
                        component="span"
                        variant="caption"
                        sx={{ ml: 1, color: 'text.secondary' }}
                    >
                        ({data.pages[0].total_count})
                    </Typography>
                )}
            </Typography>

            {isSuccess && data?.pages ? (
                <>
                    <ImagesStackComponent
                        caption={caption}
                        images={data}
                        level={level}
                        onImageClick={onImageClick}
                    />

                    {/* Loading more indicator */}
                    {isFetching && (
                        <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
                            <CircularProgress size={16} />
                        </Box>
                    )}

                    {/* Load more button for infinite scrolling could be added here */}
                </>
            ) : null}
        </Box>
    );
};