import React, { useEffect, useState } from 'react';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import { SelectChangeEvent } from '@mui/material';
import { SessionNavigatorComponent } from '../../features/session_viewer/SessionNavigatorComponent.tsx';
import { SoloImageViewerComponent } from '../../features/session_viewer/SoloImageViewerComponent.tsx';
import ImageInfoDto, { PagedImageResponse, SessionDto } from '../../features/session_viewer/ImageInfoDto.ts';
import { InfiniteData } from 'react-query';
import { usePagedImages } from '../../../services/api/usePagedImagesHook.ts';
import { useAtlasImages } from '../../../services/api/FetchSessionAtlasImages.ts';
import { useSessionNames } from '../../../services/api/FetchUseSessionNames.ts';
import { useImageViewerStore } from '../../features/session_viewer/store/imageViewerStore';

export interface ImageColumnState {
    selectedImage: ImageInfoDto | null;
    caption: string;
    level: number;
    images: InfiniteData<PagedImageResponse> | null;
}

const initialImageColumns: ImageColumnState[] = [
    {
        caption: "GR",
        level: 0,
        images: null,
        selectedImage: null,
    },
    {
        caption: "SQ",
        level: 1,
        images: null,
        selectedImage: null,
    },
    {
        caption: "HL",
        level: 2,
        images: null,
        selectedImage: null,
    },
    {
        caption: "EX",
        level: 3,
        images: null,
        selectedImage: null,
    },
];

export const ImagesPageView = () => {
    // Theme and responsive breakpoints
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Local state (will gradually be replaced with store state)
    const [level, setLevel] = useState<number>(0);
    const [parentId, setParentId] = useState<string | null>(null);
    const [currentSession, setCurrentSession] = useState<SessionDto | null>(null);
    const [imageColumns, setImageColumns] = useState<(ImageColumnState)[]>(initialImageColumns);
    const [currentImage, setCurrentImage] = useState<ImageInfoDto | null>(null);

    // Get store state and actions
    const {
        currentSession: storeCurrentSession,
        currentImage: storeCurrentImage,
        imageColumns: storeImageColumns,
        viewMode,
        setCurrentSession: storeSetCurrentSession,
        setCurrentImage: storeSetCurrentImage,
        selectImageInColumn,
        updateImageColumn,
        setAtlasImages: storeSetAtlasImages
    } = useImageViewerStore();

    const pageSize = 100;
    let sessionName = currentSession?.name;

    // Fetch session data
    const { data: sessionData, isLoading: isSessionDataLoading, isError: isSessionError } = useSessionNames();

    // Fetch atlas images
    const {
        data: atlasImages,
        isLoading: isAtlasLoading,
        isError: isAtlasError
    } = useAtlasImages(sessionName, currentSession !== null);

    // Calculate number of active columns for layout
    const activeColumnsCount = React.useMemo(() => {
        if (viewMode !== 'grid') return 1;

        // Count columns with data
        return imageColumns.filter(col =>
            col.images && col.images.pages && col.images.pages.length > 0
        ).length;
    }, [imageColumns, viewMode]);

    // Calculate the width ratio for the navigation panel
    const getLayoutRatio = React.useMemo(() => {
        // For mobile, use full width
        if (isMobile) return { nav: 12, viewer: 12 };

        // For tablet with multiple columns, adjust ratio
        if (isTablet) {
            if (activeColumnsCount > 1) {
                return { nav: 8, viewer: 12 }; // Stack them vertically
            }
            return { nav: 5, viewer: 7 };
        }

        // For desktop, adjust based on number of columns
        if (activeColumnsCount > 2) {
            return { nav: 8, viewer: 4 }; // Give more space to navigation
        }
        if (activeColumnsCount > 1) {
            return { nav: 6, viewer: 6 }; // Equal space
        }

        // Default ratio
        return { nav: 5, viewer: 7 };
    }, [activeColumnsCount, isMobile, isTablet]);

    // Sync atlas images with store when they change
    useEffect(() => {
        if (atlasImages) {
            storeSetAtlasImages(atlasImages);
        }
    }, [atlasImages, storeSetAtlasImages]);

    // Keep store and local state in sync for current session
    useEffect(() => {
        if (currentSession !== storeCurrentSession) {
            storeSetCurrentSession(currentSession);
        }
    }, [currentSession, storeCurrentSession, storeSetCurrentSession]);

    // Keep store and local state in sync for current image
    useEffect(() => {
        if (currentImage !== storeCurrentImage) {
            storeSetCurrentImage(currentImage);
        }
    }, [currentImage, storeCurrentImage, storeSetCurrentImage]);

    // Handle image selection in a column
    const OnCurrentImageChanged = (image: ImageInfoDto, column: number) => {
        if (column === imageColumns.length) {
            return; // This is the last column; when an image is selected, nothing needs to be done
        }

        // Update local state
        const updatedImageColumns = imageColumns.map((selectedColumn, index) => {
            if (index === column) {
                // Update the selectedImage property for the specified column
                return {
                    ...selectedColumn,
                    selectedImage: image,
                };
            } else if (index > column) {
                // Clear selectedImage for columns to the right
                return {
                    ...selectedColumn,
                    selectedImage: null, images: null
                };
            } else {
                // Keep the rest of the properties unchanged
                return selectedColumn;
            }
        });

        setImageColumns(updatedImageColumns);
        setCurrentImage(image);

        // Update store state
        selectImageInColumn(image, column);
    };

    // Handle session selection
    const OnSessionSelected = (event: SelectChangeEvent) => {
        const selectedValue = event.target.value;
        const sessionDto: SessionDto = {
            Oid: selectedValue,
            name: selectedValue,
        };

        // Update local state
        setCurrentSession(sessionDto);
        setImageColumns(initialImageColumns);
        setCurrentImage(null);

        // Update store state
        storeSetCurrentSession(sessionDto);
    };

    // Fetch paged images
    const {
        data, error, isLoading, isSuccess, isError, refetch,
        fetchNextPage, hasNextPage, isFetching, isFetchingNextPage,
        status,
    } = usePagedImages({ sessionName, parentId: parentId, pageSize, level });

    // Update image columns when data changes
    useEffect(() => {
        // If there is selected image in current column, it would fetch data for next column using this column's oid as parent
        const getImageColumnsData = async (columnIndex) => {
            if (columnIndex == -1) {
                setParentId(null);
                setLevel(0);
                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    const updatedImageColumns = [...imageColumns];
                    updatedImageColumns[0] = {
                        ...updatedImageColumns[0], // Copy the existing properties
                        images: data, // Update the images property
                    };
                    setImageColumns(updatedImageColumns);

                    // Update store
                    updateImageColumn(0, { images: data });
                }

            } else if (imageColumns[columnIndex].selectedImage && imageColumns[columnIndex].selectedImage?.children_count > 0) {
                setParentId(imageColumns[columnIndex].selectedImage?.oid);
                setLevel(columnIndex + 1);

                // Refetch the data
                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    const updatedImageColumns = [...imageColumns];
                    updatedImageColumns[columnIndex + 1] = {
                        ...updatedImageColumns[columnIndex + 1], // Copy the existing properties
                        images: data, // Update the images property
                    };
                    setImageColumns(updatedImageColumns);

                    // Update store
                    updateImageColumn(columnIndex + 1, { images: data });
                }
            }
        };

        // Handle the root column
        if (currentSession !== null) {
            getImageColumnsData(-1);
        }

        // Loop through other columns
        for (let i = 0; i < imageColumns.length - 1; i++) {
            if (imageColumns[i].selectedImage !== null && imageColumns[i].selectedImage?.oid !== null) {
                getImageColumnsData(i);
            }
        }
    }, [currentImage?.oid, level, data, isSuccess, currentSession]);

    // Restore session from store on initial load if available
    useEffect(() => {
        if (!currentSession && storeCurrentSession) {
            setCurrentSession(storeCurrentSession);
        }
    }, []);

    // For mobile, stack the components vertically
    if (isMobile) {
        return (
            <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ width: '100%' }}>
                    <SessionNavigatorComponent
                        onImageClick={OnCurrentImageChanged}
                        selectedSession={currentSession}
                        OnSessionSelected={OnSessionSelected}
                        selectedImage={currentImage}
                        ImageColumns={imageColumns}
                        Sessions={sessionData}
                        Atlases={atlasImages}
                    />
                </Box>
                {currentImage && (
                    <Box sx={{ width: '100%', mt: 2 }}>
                        <SoloImageViewerComponent selectedImage={currentImage} />
                    </Box>
                )}
            </Box>
        );
    }

    // For tablet and desktop, use a responsive layout
    return (
        <Box sx={{
            width: '100%',
            display: 'flex',
            flexDirection: isTablet && activeColumnsCount > 1 ? 'column' : 'row',
            gap: 2,
            overflow: 'hidden',
            height: 'calc(100vh - 120px)'
        }}>
            <Box sx={{
                width: isTablet && activeColumnsCount > 1 ? '100%' : `${(getLayoutRatio.nav / 12) * 100}%`,
                flexShrink: 0,
                overflow: 'auto'
            }}>
                <SessionNavigatorComponent
                    onImageClick={OnCurrentImageChanged}
                    selectedSession={currentSession}
                    OnSessionSelected={OnSessionSelected}
                    selectedImage={currentImage}
                    ImageColumns={imageColumns}
                    Sessions={sessionData}
                    Atlases={atlasImages}
                />
            </Box>
            <Box sx={{
                width: isTablet && activeColumnsCount > 1 ? '100%' : `${(getLayoutRatio.viewer / 12) * 100}%`,
                flexGrow: 1,
                overflow: 'auto',
                mt: isTablet && activeColumnsCount > 1 ? 2 : 0
            }}>
                <SoloImageViewerComponent selectedImage={currentImage} />
            </Box>
        </Box>
    );
};