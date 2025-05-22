import React, { useEffect, useState } from 'react';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import { SelectChangeEvent } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { ImageWorkspace } from '../../features/session_viewer/ImageWorkspace.tsx';
import ImageInfoDto, { PagedImageResponse, SessionDto } from '../../features/session_viewer/ImageInfoDto.ts';
import { InfiniteData } from 'react-query';
import { useImageListQuery } from '../../../services/api/usePagedImagesHook.ts';
import { useAtlasImages } from '../../../services/api/FetchSessionAtlasImages.ts';
import { useSessionNames } from '../../../services/api/FetchUseSessionNames.ts';
import { useImageViewerStore } from '../../features/session_viewer/store/imageViewerStore';
import {ImageInspector} from "../../features/session_viewer/ImageInspector.tsx";

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

// Inline CSS styles for resizable panels
const resizablePanelsStyles = `
/* Styling for react-resizable-panels */
[data-panel-resize-handle-enabled] {
  cursor: col-resize;
  transition: all 0.2s ease;
}

[data-panel-resize-handle-enabled]:hover {
  background: rgba(25, 118, 210, 0.1) !important;
}

[data-panel-resize-handle-active] {
  background: rgba(25, 118, 210, 0.2) !important;
}

.resize-handle-horizontal {
  width: 8px !important;
  cursor: col-resize !important;
  background: transparent !important;
  border-left: 1px solid rgba(0, 0, 0, 0.12);
  border-right: 1px solid rgba(0, 0, 0, 0.12);
  transition: all 0.2s ease;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resize-handle-horizontal:hover {
  background: rgba(25, 118, 210, 0.1) !important;
  border-left-color: rgba(25, 118, 210, 0.3);
  border-right-color: rgba(25, 118, 210, 0.3);
}

.resize-handle-horizontal[data-resize-handle-active] {
  background: rgba(25, 118, 210, 0.2) !important;
  border-left-color: rgba(25, 118, 210, 0.5);
  border-right-color: rgba(25, 118, 210, 0.5);
}
`;

// Add styles to head if not already added
if (typeof document !== 'undefined' && !document.getElementById('resizable-panels-styles')) {
    const styleElement = document.createElement('style');
    styleElement.id = 'resizable-panels-styles';
    styleElement.textContent = resizablePanelsStyles;
    document.head.appendChild(styleElement);
}

// Custom styled resize handle
const CustomResizeHandle = () => {
    const theme = useTheme();

    return (
        <PanelResizeHandle
            className="resize-handle-horizontal"
        >
            <Box
                sx={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    '&::before': {
                        content: '""',
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: '3px',
                        height: '40px',
                        background: `repeating-linear-gradient(
                            to bottom,
                            ${theme.palette.text.secondary} 0px,
                            ${theme.palette.text.secondary} 3px,
                            transparent 3px,
                            transparent 7px
                        )`,
                        borderRadius: '1.5px',
                        opacity: 0.4,
                        transition: 'opacity 0.2s ease'
                    },
                    '&:hover::before': {
                        opacity: 0.8,
                    }
                }}
            />
        </PanelResizeHandle>
    );
};

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

    // Panel size persistence
    const [leftPanelSize, setLeftPanelSize] = useState(() => {
        const saved = localStorage.getItem('images-page-left-panel-size');
        return saved ? parseInt(saved, 10) : (isMobile ? 100 : 40);
    });

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

    // Save panel size to localStorage
    const handlePanelResize = (sizes: number[]) => {
        if (sizes[0] !== undefined) {
            setLeftPanelSize(sizes[0]);
            localStorage.setItem('images-page-left-panel-size', sizes[0].toString());
        }
    };

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
    } = useImageListQuery({ sessionName, parentId: parentId, pageSize, level });

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
            <Box sx={{
                width: '100%',
                height: 'calc(100vh - 120px)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
            }}>
                <Box sx={{
                    height: '50%',
                    overflow: 'auto',
                    borderBottom: `1px solid ${theme.palette.divider}`
                }}>
                    <ImageWorkspace
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
                    <Box sx={{
                        height: '50%',
                        overflow: 'auto'
                    }}>
                        <ImageInspector selectedImage={currentImage} />
                    </Box>
                )}
            </Box>
        );
    }

    // For tablet and desktop, use resizable panels
    return (
        <Box sx={{
            width: '100%',
            height: 'calc(100vh - 120px)',
            overflow: 'hidden',
            display: 'flex'
        }}>
            <PanelGroup
                direction="horizontal"
                onLayout={handlePanelResize}
                style={{ width: '100%', height: '100%' }}
            >
                {/* Left Panel - Session Navigator */}
                <Panel
                    id="session-navigator"
                    defaultSize={leftPanelSize}
                    minSize={25}
                    maxSize={75}
                >
                    <Box sx={{
                        height: '100%',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: 'background.paper'
                    }}>
                        <ImageWorkspace
                            onImageClick={OnCurrentImageChanged}
                            selectedSession={currentSession}
                            OnSessionSelected={OnSessionSelected}
                            selectedImage={currentImage}
                            ImageColumns={imageColumns}
                            Sessions={sessionData}
                            Atlases={atlasImages}
                        />
                    </Box>
                </Panel>

                {/* Resize Handle */}
                <CustomResizeHandle />

                {/* Right Panel - Solo Image Viewer */}
                <Panel
                    id="image-viewer"
                    minSize={25}
                >
                    <Box sx={{
                        height: '100%',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: 'background.paper'
                    }}>
                        <ImageInspector selectedImage={currentImage} />
                    </Box>
                </Panel>
            </PanelGroup>
        </Box>
    );
};