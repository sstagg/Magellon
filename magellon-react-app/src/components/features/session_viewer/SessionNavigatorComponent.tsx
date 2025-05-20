import {
    Box,
    ButtonGroup,
    Card,
    CardContent,
    FormControl,
    Grid,
    ImageList,
    ImageListItem,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    SelectChangeEvent,
    Stack,
    Tooltip,
    Typography,
    useTheme
} from "@mui/material";
import { ImagesStackComponent } from "./ImagesStackComponent.tsx";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "./ImageInfoDto.ts";
import IconButton from "@mui/material/IconButton";
import { EyeOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { ImageColumnState } from "../../panel/pages/ImagesPageView.tsx";
import AtlasImage from "./AtlasImage.tsx";
import { settings } from "../../../core/settings.ts";
import { AccountTreeRounded, GridViewRounded, GridOnRounded, TableRowsRounded } from "@mui/icons-material";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import FlatImageViewerComponent from "./FlatImageViewerComponent.tsx";
import TreeViewer from "./TreeViewer.tsx";

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

    // View mode selector component
    const renderViewModeSelector = () => {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                <ButtonGroup size="small" fullWidth>
                    <Tooltip title="Column View">
                        <IconButton
                            onClick={() => setViewMode('grid')}
                            color={viewMode === 'grid' ? 'primary' : 'default'}
                        >
                            <GridViewRounded />
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
            <Box sx={{ mt: 2, height: 'calc(100% - 130px)', overflow: 'auto' }}>
                <TreeViewer
                    images={ImageColumns[0].images}
                    onImageClick={onImageClick}
                    title="Image Hierarchy"
                />
            </Box>
        );
    };

    // Render the column view (original)
    const renderGridView = () => {
        return (
            <Box sx={{
                mt: 2,
                display: 'flex',
                flexWrap: 'nowrap',
                overflowX: 'auto',
                height: 'calc(100% - 130px)'
            }}>
                <ImagesStackComponent caption={ImageColumns[0].caption} images={ImageColumns[0].images} level={0} onImageClick={(image) => onImageClick(image, 0)} />
                <ImagesStackComponent caption={ImageColumns[1].caption} images={ImageColumns[1].images} level={1} onImageClick={(image) => onImageClick(image, 1)} />
                <ImagesStackComponent caption={ImageColumns[2].caption} images={ImageColumns[2].images} level={2} onImageClick={(image) => onImageClick(image, 2)} />
                <ImagesStackComponent caption={ImageColumns[3].caption} images={ImageColumns[3].images} level={3} onImageClick={(image) => onImageClick(image, 3)} />
            </Box>
        );
    };

    // Render the flat view (non-hierarchical)
    const renderFlatView = () => {
        return (
            <Box sx={{ mt: 2, height: 'calc(100% - 130px)', overflow: 'auto' }}>
                <FlatImageViewerComponent
                    images={ImageColumns[0].images}
                    onImageClick={onImageClick}
                    title="All Images"
                />
            </Box>
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
            {/* Header with session selector and atlas toggle */}
            <Box sx={{ p: 1 }}>
                <Box sx={{
                    display: 'flex',
                    gap: 2,
                    alignItems: 'center', // Changed from 'flex-start' to 'center'
                    mb: 1
                }}>
                    {/* Session selector - takes more space */}
                    <Box sx={{ flex: 2 }}>
                        {renderSessionSelector()}
                    </Box>

                    {/* Atlas visibility toggle - same height as session selector */}
                    <Paper
                        elevation={0}
                        variant="outlined"
                        sx={{
                            height: 56, // Match height of session selector
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
                                <AtlasImage
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

                {/* View mode selector moved below atlas section */}
                <Box sx={{ mb: 1 }}>
                    {renderViewModeSelector()}
                </Box>
            </Box>

            {/* Main image navigation view - fills remaining space */}
            <Box sx={{ flex: 1, overflow: 'hidden' }}>
                {renderNavView()}
            </Box>
        </Box>
    );
};