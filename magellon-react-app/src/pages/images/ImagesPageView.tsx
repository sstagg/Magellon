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
import { useSidePanelStore } from '../../shared/lib/stores/useBottomPanelStore.ts';
import '../../shared/ui/resizablePanels.module.css';

// ColumnBrowser default column width (see ColumnBrowser.tsx — clamps to >= 175).
const DEFAULT_COLUMN_PX = 175;
// Gap between columns + container padding + scrollbar gutter.
const COLUMN_GUTTER_PX = 16;
// Header chrome: session-select + view-mode toggle + Column View Settings strip.
const HEADER_CHROME_PX = 80;

const widthForColumns = (count: number, columnPx: number = DEFAULT_COLUMN_PX): number =>
    HEADER_CHROME_PX + count * (columnPx + COLUMN_GUTTER_PX);

export const ImagesPageView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const { initialUserWidthPx, persistWidth, leftMargin, minPx, maxPx } = usePanelLayout({
        storageKey: 'images-page-left-panel-px',
        minPx: 280,
        maxPx: 1200,
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

    // Default the left panel to fit the standard 4-column layout (GR / SQ /
    // HL / EX). The operator can drag narrower for small monitors or wider
    // for higher-res displays; their choice is persisted in localStorage.
    //
    // We pass the initial width via `defaultSize` and never re-render in
    // response to a drag — the library owns the size after mount.
    // Re-renders mid-drag disrupt the pointer-tracking and prevent the
    // panel from growing past its starting size (see commit history).
    const autoFitPx = Math.max(minPx, Math.min(maxPx, widthForColumns(4)));
    const defaultPx = initialUserWidthPx ?? autoFitPx;

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
                                style={{ width: '100%', height: '100%', minWidth: 0 }}
                            >
                                <Panel
                                    id="session-navigator"
                                    defaultSize={`${defaultPx}px`}
                                    minSize={`${minPx}px`}
                                    maxSize={`${maxPx}px`}
                                    // Persist via a ref-only path so we don't
                                    // re-render mid-drag — re-renders break the
                                    // library's pointer-tracking and prevent
                                    // the panel from growing past its initial
                                    // size.
                                    onResize={(panelSize) => persistWidth(panelSize.inPixels)}
                                    style={{ minWidth: 0, overflow: 'hidden' }}
                                >
                                    <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: 'background.paper' }}>
                                        <ImageWorkspace {...workspaceProps} />
                                    </Box>
                                </Panel>

                                <Separator />

                                <Panel id="image-viewer" minSize="320px" style={{ minWidth: 0, overflow: 'hidden' }}>
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
