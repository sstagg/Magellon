import React from 'react';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import { Panel, Group, Separator } from 'react-resizable-panels';
import { ImageWorkspace } from '../../features/image-viewer/ui/ImageWorkspace.tsx';
import { useSessionNames } from '../../features/image-viewer/api/FetchUseSessionNames.ts';
import { useImageViewerStore } from '../../features/image-viewer/model/imageViewerStore.ts';
import { ImageInspector } from "../../features/image-viewer/ui/ImageInspector.tsx";
import { usePanelLayout } from '../../features/image-viewer/lib/usePanelLayout.ts';
import { useImageNavigation } from '../../features/image-viewer/lib/useImageNavigation.ts';
import { useImageDataFetching } from '../../features/image-viewer/lib/useImageDataFetching.ts';
import { useAtlasData } from '../../features/image-viewer/lib/useAtlasData.ts';
import { ImageViewerErrorBoundary } from '../../features/image-viewer/ui/ImageViewerErrorBoundary.tsx';
import { ImageNavigationProvider } from '../../features/image-viewer/lib/ImageNavigationContext.tsx';
import { useSidePanelStore } from '../../app/layouts/PanelLayout/useBottomPanelStore.ts';
import '../../panel/pages/styles/resizablePanels.module.css';

const CustomResizeHandle = () => {
    const theme = useTheme();
    return (
        <Separator className="resize-handle-horizontal">
            <Box sx={{
                width: '100%', height: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative',
                '&::before': {
                    content: '""', position: 'absolute', top: '50%', left: '50%',
                    transform: 'translate(-50%, -50%)', width: '3px', height: '40px',
                    background: `repeating-linear-gradient(to bottom, ${theme.palette.text.secondary} 0px, ${theme.palette.text.secondary} 3px, transparent 3px, transparent 7px)`,
                    borderRadius: '1.5px', opacity: 0.4, transition: 'opacity 0.2s ease',
                },
                '&:hover::before': { opacity: 0.8 },
            }} />
        </Separator>
    );
};

export const ImagesPageView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const { leftPanelSize, handleResize, leftMargin } = usePanelLayout({
        defaultSize: 35, minSize: 25, maxSize: 50,
        storageKey: 'images-page-left-panel-size',
    });

    const { handleImageClick, handleSessionSelect } = useImageNavigation();
    const { currentSession, currentImage, imageColumns } = useImageViewerStore();
    const { data: sessionData } = useSessionNames();
    const { atlasImages } = useAtlasData({
        sessionName: currentSession?.name,
        enabled: currentSession !== null,
    });

    useImageDataFetching({ sessionName: currentSession?.name, pageSize: 100 });

    const { activePanel, panelWidth } = useSidePanelStore();
    const rightOffset = activePanel ? panelWidth : 0;

    const workspaceProps = {
        onImageClick: handleImageClick,
        selectedSession: currentSession,
        OnSessionSelected: handleSessionSelect,
        selectedImage: currentImage,
        ImageColumns: imageColumns,
        Sessions: sessionData,
        Atlases: atlasImages,
    };

    if (isMobile) {
        return (
            <ImageViewerErrorBoundary>
                <ImageNavigationProvider>
                    <Box sx={{
                        position: 'fixed', top: 40, left: leftMargin, right: rightOffset, bottom: 0,
                        zIndex: 1050, backgroundColor: 'background.default',
                        display: 'flex', flexDirection: 'column', overflow: 'hidden',
                        transition: theme.transitions.create(['left', 'right']),
                    }}>
                        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: '0.5%', overflow: 'hidden' }}>
                            <Box sx={{
                                height: currentImage ? '65%' : '100%', minHeight: 500,
                                overflow: 'auto', borderRadius: 2, backgroundColor: 'background.paper', boxShadow: 1,
                                mb: currentImage ? 2 : 0,
                            }}>
                                <ImageWorkspace {...workspaceProps} />
                            </Box>
                            {currentImage && (
                                <Box sx={{ height: '35%', minHeight: 250, overflow: 'auto', borderRadius: 2, backgroundColor: 'background.paper', boxShadow: 1 }}>
                                    <ImageInspector selectedImage={currentImage} />
                                </Box>
                            )}
                        </Box>
                    </Box>
                </ImageNavigationProvider>
            </ImageViewerErrorBoundary>
        );
    }

    return (
        <ImageViewerErrorBoundary>
            <ImageNavigationProvider>
                <Box sx={{
                    position: 'fixed', top: 64, left: leftMargin, right: rightOffset, bottom: 0,
                    zIndex: 1050, backgroundColor: 'background.default',
                    overflow: 'hidden', display: 'flex',
                    transition: theme.transitions.create(['left', 'right']),
                }}>
                    <Box sx={{ flex: 1, display: 'flex', p: '0.5%', overflow: 'hidden' }}>
                        <Box sx={{
                            width: '100%', height: '100%', borderRadius: 3,
                            backgroundColor: 'background.paper', boxShadow: 3, overflow: 'hidden',
                            border: `1px solid ${theme.palette.divider}`,
                        }}>
                            <Group
                                orientation="horizontal"
                                onLayoutChange={handleResize}
                                style={{ width: '100%', height: '100%', minWidth: 0 }}
                            >
                                <Panel
                                    id="session-navigator"
                                    defaultSize={`${leftPanelSize}%`}
                                    minSize="25%" maxSize="50%"
                                    style={{ minWidth: 0, overflow: 'hidden' }}
                                >
                                    <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: 'background.paper' }}>
                                        <ImageWorkspace {...workspaceProps} />
                                    </Box>
                                </Panel>

                                <CustomResizeHandle />

                                <Panel id="image-viewer" minSize="50%" style={{ minWidth: 500, overflow: 'hidden' }}>
                                    <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: 'background.paper' }}>
                                        <ImageInspector selectedImage={currentImage} />
                                    </Box>
                                </Panel>
                            </Group>
                        </Box>
                    </Box>
                </Box>
            </ImageNavigationProvider>
        </ImageViewerErrorBoundary>
    );
};
