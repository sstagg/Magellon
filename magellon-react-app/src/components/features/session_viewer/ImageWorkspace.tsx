import {
    Box,
    Fab,
    useTheme,
} from "@mui/material";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "./ImageInfoDto.ts";
import {
    Visibility,
    VisibilityOff,
} from "@mui/icons-material";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import ColumnBrowser from "./ColumnBrowser.tsx";
import { ImageColumnState } from "../../../panel/pages/ImagesPageView.tsx";
import { SelectChangeEvent } from '@mui/material';
import { SessionSelector } from './components/SessionSelector.tsx';
import { ViewModeSelector } from './components/ViewModeSelector.tsx';
import { EnhancedAtlasSection } from './components/EnhancedAtlasSection.tsx';

interface ImageNavigatorProps {
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void,
    selectedImage: ImageInfoDto | null,
    selectedSession: SessionDto | null,
    ImageColumns: ImageColumnState[],
    Atlases: AtlasImageDto[],
    Sessions: SessionDto[],
    OnSessionSelected: (event: SelectChangeEvent) => void
}

export const ImageWorkspace: React.FC<ImageNavigatorProps> = ({
    onImageClick,
    selectedImage,
    selectedSession,
    ImageColumns,
    Atlases,
    Sessions,
    OnSessionSelected
}) => {
    const theme = useTheme();

    // Get store state and actions
    const {
        isAtlasVisible,
        viewMode,
        currentAtlas,
        currentSession,
        toggleAtlasVisibility,
        setViewMode,
        setCurrentAtlas
    } = useImageViewerStore();

    // Get session name from store or props
    const sessionName = currentSession?.name || selectedSession?.name || '';

    // Render the appropriate view based on viewMode
    const renderNavView = () => {
        switch (viewMode) {
            case 'grid':
                return renderGridView();
            case 'tree':
                return renderTreeView();
            case 'flat':
                return renderFlatView();
            default:
                return null;
        }
    };

    // Render the tree view
    const renderTreeView = () => {
        return (
            <HierarchyBrowser
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="Image Hierarchy"
            />
        );
    };

    // Render the grid/stacked view
    const renderGridView = () => {
        return (
            <ColumnBrowser
                imageColumns={ImageColumns}
                onImageClick={onImageClick}
                sessionName={sessionName}
                showSettings={true}
                initialSettingsCollapsed={false}
                height="100%"
            />
        );
    };

    // Render the flat view
    const renderFlatView = () => {
        return (
            <GridGallery
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="All Images"
            />
        );
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            position: 'relative'
        }}>
            {/* Header with session selector */}
            <Box sx={{
                flexShrink: 0,
                p: 1,
                borderBottom: `1px solid ${theme.palette.divider}`
            }}>
                <Box sx={{
                    display: 'flex',
                    gap: 2,
                    alignItems: 'center',
                    mb: 1
                }}>
                    {/* Session selector */}
                    <Box sx={{ flex: 1 }}>
                        <SessionSelector
                            selectedSession={selectedSession}
                            sessions={Sessions}
                            onSessionChange={OnSessionSelected}
                        />
                    </Box>
                </Box>

                {/* Enhanced Atlas section */}
                <EnhancedAtlasSection
                    atlases={Atlases}
                    currentAtlas={currentAtlas}
                    sessionName={sessionName}
                    isVisible={isAtlasVisible}
                    onAtlasChange={setCurrentAtlas}
                    onImageClick={onImageClick}
                />

                {/* View mode selector */}
                <Box>
                    <ViewModeSelector
                        viewMode={viewMode}
                        onViewModeChange={setViewMode}
                    />
                </Box>
            </Box>

            {/* Main image navigation view */}
            <Box sx={{
                flex: 1,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
            }}>
                {renderNavView()}
            </Box>

            {/* Floating Action Button for Atlas Toggle */}
            <Fab
                color="primary"
                size="small"
                onClick={toggleAtlasVisibility}
                sx={{
                    position: 'absolute',
                    bottom: 16,
                    right: 16,
                    zIndex: 1000,
                    boxShadow: 3,
                    '&:hover': {
                        boxShadow: 6,
                        transform: 'scale(1.05)'
                    },
                    transition: 'all 0.2s ease-in-out'
                }}
                aria-label={isAtlasVisible ? "Hide Atlas" : "Show Atlas"}
            >
                {isAtlasVisible ? <VisibilityOff /> : <Visibility />}
            </Fab>
        </Box>
    );
};
