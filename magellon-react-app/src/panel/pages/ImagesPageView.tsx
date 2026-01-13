import React from 'react';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import { Panel, Group, Separator } from 'react-resizable-panels';
import { ImageWorkspace } from '../../components/features/session_viewer/ImageWorkspace.tsx';
import { useSessionNames } from '../../services/api/FetchUseSessionNames.ts';
import { useImageViewerStore } from '../../components/features/session_viewer/store/imageViewerStore.ts';
import { ImageInspector } from "../../components/features/session_viewer/ImageInspector.tsx";
import { usePanelLayout } from '../../components/features/session_viewer/hooks/usePanelLayout.ts';
import { useImageNavigation } from '../../components/features/session_viewer/hooks/useImageNavigation.ts';
import { useImageDataFetching } from '../../components/features/session_viewer/hooks/useImageDataFetching.ts';
import { useAtlasData } from '../../components/features/session_viewer/hooks/useAtlasData.ts';
import '../../panel/pages/styles/resizablePanels.module.css';

const DRAWER_WIDTH = 240;

// Custom styled resize handle
const CustomResizeHandle = () => {
    const theme = useTheme();

    return (
        <Separator
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
        </Separator>
    );
};

export const ImagesPageView = () => {
    // Theme and responsive breakpoints
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Use custom hooks for panel layout management
    const { leftPanelSize, handleResize, leftMargin } = usePanelLayout({
        defaultSize: 35,
        minSize: 25,
        maxSize: 50,
        storageKey: 'images-page-left-panel-size'
    });

    // Use custom hook for image navigation
    const { handleImageClick, handleSessionSelect } = useImageNavigation();

    // Get state from Zustand store (single source of truth)
    const {
        currentSession,
        currentImage,
        imageColumns
    } = useImageViewerStore();

    // Fetch session data
    const { data: sessionData } = useSessionNames();

    // Fetch and manage atlas images
    const { atlasImages } = useAtlasData({
        sessionName: currentSession?.name,
        enabled: currentSession !== null
    });

    // Fetch and manage image data with hierarchy
    useImageDataFetching({
        sessionName: currentSession?.name,
        pageSize: 100
    });

    // Calculate padding values
    const paddingValue = isMobile ? '0.5%' : '0.5%';
    const topBottomPadding = isMobile ? '0.5%' : '0.5%';

    // Mobile layout - stack components vertically with proper height allocation
    const renderMobileLayout = () => {
        return (
            <Box sx={{
                position: 'fixed',
                top: 40, // Account for header
                left: leftMargin,
                right: 0,
                bottom: 0,
                zIndex: 1050, // Below drawer but above content
                backgroundColor: 'background.default',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                transition: theme.transitions.create(['left'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
            }}>
                {/* Container with padding for beautiful layout */}
                <Box sx={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    p: paddingValue,
                    pt: topBottomPadding,
                    pb: topBottomPadding,
                    overflow: 'hidden'
                }}>
                    {/* ImageWorkspace - Fixed height to ensure adequate space */}
                    <Box sx={{
                        height: currentImage ? '65%' : '100%', // Give more space when image selected
                        minHeight: '500px', // Ensure substantial minimum height
                        overflow: 'auto',
                        borderRadius: 2,
                        backgroundColor: 'background.paper',
                        boxShadow: 1,
                        mb: currentImage ? 2 : 0
                    }}>
                        <ImageWorkspace
                            onImageClick={handleImageClick}
                            selectedSession={currentSession}
                            OnSessionSelected={handleSessionSelect}
                            selectedImage={currentImage}
                            ImageColumns={imageColumns}
                            Sessions={sessionData}
                            Atlases={atlasImages}
                        />
                    </Box>

                    {/* ImageInspector - Only show when image is selected */}
                    {currentImage && (
                        <Box sx={{
                            height: '35%',
                            minHeight: '250px', // Adequate minimum for image details
                            overflow: 'auto',
                            borderRadius: 2,
                            backgroundColor: 'background.paper',
                            boxShadow: 1
                        }}>
                            <ImageInspector selectedImage={currentImage} />
                        </Box>
                    )}
                </Box>
            </Box>
        );
    };

    // Desktop layout - resizable panels with full screen, beautiful padding and rounded corners
    const renderDesktopLayout = () => {
        return (
            <Box sx={{
                position: 'fixed',
                top: 64, // Account for header
                left: leftMargin,
                right: 0,
                bottom: 0,
                zIndex: 1050, // Below drawer but above content
                backgroundColor: 'background.default',
                overflow: 'hidden',
                display: 'flex',
                transition: theme.transitions.create(['left'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
            }}>
                {/* Container with padding for beautiful layout */}
                <Box sx={{
                    flex: 1,
                    display: 'flex',
                    p: paddingValue,
                    pt: topBottomPadding,
                    pb: topBottomPadding,
                    overflow: 'hidden'
                }}>
                    {/* Main content area with rounded corners and shadow */}
                    <Box sx={{
                        width: '100%',
                        height: '100%',
                        borderRadius: 3,
                        backgroundColor: 'background.paper',
                        boxShadow: 3,
                        overflow: 'hidden',
                        border: `1px solid ${theme.palette.divider}`
                    }}>
                        <Group
                            orientation="horizontal"
                            onLayoutChange={handleResize}
                            style={{
                                width: '100%',
                                height: '100%',
                                minWidth: 0
                            }}
                        >
                            {/* Left Panel - Session Navigator (ImageWorkspace) */}
                            <Panel
                                id="session-navigator"
                                defaultSize={leftPanelSize}
                                minSize={25}        // Minimum 25% of total width (more space for images)
                                maxSize={50}        // Maximum 50% of total width
                                style={{
                                    minWidth: 0,
                                    overflow: 'hidden'
                                }}
                            >
                                <Box sx={{
                                    height: '100%',
                                    overflow: 'hidden',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    backgroundColor: 'background.paper',
                                    borderTopLeftRadius: 3,
                                    borderBottomLeftRadius: 3
                                }}>
                                    <ImageWorkspace
                                        onImageClick={handleImageClick}
                                        selectedSession={currentSession}
                                        OnSessionSelected={handleSessionSelect}
                                        selectedImage={currentImage}
                                        ImageColumns={imageColumns}
                                        Sessions={sessionData}
                                        Atlases={atlasImages}
                                    />
                                </Box>
                            </Panel>

                            {/* Resize Handle */}
                            <CustomResizeHandle />

                            {/* Right Panel - Solo Image Viewer (ImageInspector) - Gets more space */}
                            <Panel
                                id="image-viewer"
                                minSize={50}        // Minimum 50% of total width - more space for detailed viewing
                                style={{
                                    minWidth: '500px', // Reduced minimum - let it be more flexible
                                    overflow: 'hidden'
                                }}
                            >
                                <Box sx={{
                                    height: '100%',
                                    overflow: 'hidden',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    backgroundColor: 'background.paper',
                                    borderTopRightRadius: 3,
                                    borderBottomRightRadius: 3
                                }}>
                                    <ImageInspector selectedImage={currentImage} />
                                </Box>
                            </Panel>
                        </Group>
                    </Box>
                </Box>
            </Box>
        );
    };

    // Main component return - responsive layout selection
    if (isMobile) {
        return renderMobileLayout();
    } else {
        return renderDesktopLayout();
    }
};
