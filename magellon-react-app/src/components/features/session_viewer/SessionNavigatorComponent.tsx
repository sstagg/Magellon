import {
    Box,
    ButtonGroup,
    FormControl,
    ImageList,
    ImageListItem,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    SelectChangeEvent,
    Tooltip,
    Typography,
    useTheme,
    Chip
} from "@mui/material";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "./ImageInfoDto.ts";
import IconButton from "@mui/material/IconButton";
import { EyeOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { ImageColumnState } from "../../panel/pages/ImagesPageView.tsx";
import AtlasViewer from "./AtlasViewer.tsx";
import { settings } from "../../../core/settings.ts";
import {
    AccountTreeRounded,
    GridOnRounded,
    ViewColumn
} from "@mui/icons-material";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import StackedView from "./StackedView.tsx";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

interface ImageNavigatorProps {
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void,
    selectedImage: ImageInfoDto | null,
    selectedSession: SessionDto | null,
    ImageColumns: ImageColumnState[],
    Atlases: AtlasImageDto[],
    Sessions: SessionDto[],
    OnSessionSelected: (event: SelectChangeEvent) => void
}

export const SessionNavigatorComponent: React.FC<ImageNavigatorProps> = ({
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

    // Initialize atlas on component mount
    useEffect(() => {
        if (Atlases && Atlases.length > 0 && !currentAtlas) {
            setCurrentAtlas(Atlases[0]);
        }
    }, [Atlases, currentAtlas, setCurrentAtlas]);

    const handleAtlasClick = (atlas: AtlasImageDto) => {
        setCurrentAtlas(atlas);
    };

    // Session selector component
    const renderSessionSelector = () => {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
                <FormControl fullWidth size="small" variant="outlined">
                    <InputLabel id="session-select-label">Session</InputLabel>
                    <Select
                        labelId="session-select-label"
                        id="session-select"
                        value={selectedSession?.name || ""}
                        label="Session"
                        onChange={OnSessionSelected}
                    >
                        <MenuItem value="">
                            <em>None</em>
                        </MenuItem>
                        {Sessions?.map((session) => (
                            <MenuItem key={session.Oid} value={session.name}>
                                {session.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Paper>
        );
    };

    // Enhanced view mode selector component (simplified)
    const renderViewModeSelector = () => {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <ButtonGroup size="small">
                        <Tooltip title="Column View">
                            <IconButton
                                onClick={() => setViewMode('grid')}
                                color={viewMode === 'grid' ? 'primary' : 'default'}
                            >
                                <ViewColumn />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Tree View">
                            <IconButton
                                onClick={() => setViewMode('tree')}
                                color={viewMode === 'tree' ? 'primary' : 'default'}
                            >
                                <AccountTreeRounded />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Flat View">
                            <IconButton
                                onClick={() => setViewMode('flat')}
                                color={viewMode === 'flat' ? 'primary' : 'default'}
                            >
                                <GridOnRounded />
                            </IconButton>
                        </Tooltip>
                    </ButtonGroup>

                    <Chip
                        label={viewMode === 'grid' ? 'Columns' : viewMode === 'tree' ? 'Tree' : 'Flat'}
                        size="small"
                        color="primary"
                        variant="outlined"
                    />
                </Box>
            </Paper>
        );
    };

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

    // Render the tree view (hierarchical)
    const renderTreeView = () => {
        return (
            <HierarchyBrowser
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="Image Hierarchy"
            />
        );
    };

    // Render the grid/stacked view using the new StackedView component
    const renderGridView = () => {
        return (
            <StackedView
                imageColumns={ImageColumns}
                onImageClick={onImageClick}
                sessionName={sessionName}
                showSettings={true}
                initialSettingsCollapsed={false}
                height="100%"
            />
        );
    };

    // Render the flat view (non-hierarchical)
    const renderFlatView = () => {
        return (
            <GridGallery
                images={ImageColumns[0].images}
                onImageClick={onImageClick}
                title="All Images"
            />
        );
    };

    // Atlas thumbnail list
    const renderAtlasList = () => {
        if (!Atlases || Atlases.length === 0) {
            return (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                    No atlas images available
                </Typography>
            );
        }

        return (
            <ImageList cols={1} rowHeight={80} sx={{ width: '100%', maxHeight: 120, m: 0 }}>
                {Atlases?.map((atlas, index) => (
                    <ImageListItem
                        key={index}
                        onClick={() => handleAtlasClick(atlas)}
                        sx={{
                            cursor: 'pointer',
                            border: atlas.oid === currentAtlas?.oid ? `2px solid ${theme.palette.primary.main}` : 'none',
                            borderRadius: 1,
                            overflow: 'hidden'
                        }}
                    >
                        <img
                            src={`${BASE_URL}/atlas-image?name=${atlas?.name}&sessionName=${sessionName}`}
                            alt="atlas"
                            style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover'
                            }}
                        />
                    </ImageListItem>
                ))}
            </ImageList>
        );
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            {/* Header with session selector and atlas toggle - Fixed height */}
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
                    {/* Session selector - takes more space */}
                    <Box sx={{ flex: 2 }}>
                        {renderSessionSelector()}
                    </Box>

                    {/* Atlas visibility toggle */}
                    <Paper
                        elevation={0}
                        variant="outlined"
                        sx={{
                            height: 56,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            p: 2,
                            borderRadius: 1,
                            flex: '0 0 auto'
                        }}
                    >
                        <Tooltip title={isAtlasVisible ? "Hide Atlas" : "Show Atlas"}>
                            <IconButton onClick={toggleAtlasVisibility} size="small">
                                <EyeOutlined />
                            </IconButton>
                        </Tooltip>
                    </Paper>
                </Box>

                {/* Atlas section */}
                {isAtlasVisible && (
                    <Box sx={{
                        display: 'flex',
                        gap: 2,
                        mb: 1,
                        borderRadius: 1,
                        border: `1px solid ${theme.palette.divider}`,
                        p: 1
                    }}>
                        {/* Atlas thumbnails list */}
                        <Box sx={{ flex: 1 }}>
                            {renderAtlasList()}
                        </Box>

                        {/* Current atlas view */}
                        {currentAtlas && (
                            <Box sx={{ flex: 2 }}>
                                <AtlasViewer
                                    imageMapJson={currentAtlas?.meta}
                                    finalWidth={180}
                                    finalHeight={120}
                                    name={currentAtlas?.name}
                                    backgroundColor="black"
                                    onImageClick={onImageClick}
                                />
                            </Box>
                        )}
                    </Box>
                )}

                {/* View mode selector */}
                <Box>
                    {renderViewModeSelector()}
                </Box>
            </Box>

            {/* Main image navigation view - Fills remaining space */}
            <Box sx={{
                flex: 1,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
            }}>
                {renderNavView()}
            </Box>
        </Box>
    );
};