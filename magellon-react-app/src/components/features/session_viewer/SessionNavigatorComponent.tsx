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
    useTheme,
    Chip
} from "@mui/material";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "./ImageInfoDto.ts";
import IconButton from "@mui/material/IconButton";
import { EyeOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { ImageColumnState } from "../../panel/pages/ImagesPageView.tsx";
import AtlasImage from "./AtlasImage.tsx";
import { settings } from "../../../core/settings.ts";
import {
    AccountTreeRounded,
    GridViewRounded,
    GridOnRounded,
    ViewColumn
} from "@mui/icons-material";
import { useImageViewerStore } from './store/imageViewerStore.ts';
import FlatImageViewerComponent from "./FlatImageViewerComponent.tsx";
import TreeViewer from "./TreeViewer.tsx";
import ImageColumnComponent from "./ImageColumnComponent.tsx";
import { ImagesStackComponent } from "./ImagesStackComponent.tsx";
import ColumnSettingsComponent, {
    ColumnSettings,
    defaultColumnSettings
} from "./ColumnSettingsComponent.tsx";

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

    // Local state for enhanced column view using the new component
    const [columnSettings, setColumnSettings] = useState<ColumnSettings>(defaultColumnSettings);

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

    // Calculate which columns should be visible
    const visibleColumns = ImageColumns.filter((col, index) => {
        if (!columnSettings.autoHideEmptyColumns) return true;

        // Always show the first column
        if (index === 0) return true;

        // Show column if it has data or if the previous column has a selected image
        return col.images && col.images.pages && col.images.pages.length > 0;
    });

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

    // Enhanced view mode selector component
    const renderViewModeSelector = () => {
        return (
            <>
                <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <ButtonGroup size="small">
                            <Tooltip title="Enhanced Column View">
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

                {/* Column-specific settings using the new reusable component */}
                {viewMode === 'grid' && (
                    <ColumnSettingsComponent
                        settings={columnSettings}
                        onSettingsChange={setColumnSettings}
                        visible={true}
                        showEnhancedToggle={true}
                        minWidth={150}
                        maxWidth={300}
                    />
                )}
            </>
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
            <Box sx={{ mt: 2, height: 'calc(100% - 160px)', overflow: 'auto' }}>
                <TreeViewer
                    images={ImageColumns[0].images}
                    onImageClick={onImageClick}
                    title="Image Hierarchy"
                />
            </Box>
        );
    };

    // Enhanced grid view with new ImageColumnComponent
    const renderGridView = () => {
        if (columnSettings.useEnhancedColumns) {
            return (
                <Box sx={{
                    mt: 2,
                    display: 'flex',
                    gap: 1,
                    overflowX: 'auto',
                    height: 'calc(100% - 160px)',
                    pb: 1
                }}>
                    {visibleColumns.map((column, index) => (
                        <ImageColumnComponent
                            key={`enhanced-column-${index}`}
                            caption={column.caption}
                            level={index}
                            parentImage={index === 0 ? null : ImageColumns[index - 1]?.selectedImage || null}
                            sessionName={sessionName}
                            width={columnSettings.columnWidth}
                            height={undefined} // Let it fill available height
                            onImageClick={onImageClick}
                            showControls={columnSettings.showColumnControls}
                            collapsible={index > 0}
                            sx={{
                                flexShrink: 0,
                                height: '100%'
                            }}
                        />
                    ))}
                </Box>
            );
        }

        // Fallback to original stack components
        return (
            <Box sx={{
                mt: 2,
                display: 'flex',
                flexWrap: 'nowrap',
                overflowX: 'auto',
                height: 'calc(100% - 160px)'
            }}>
                {ImageColumns.map((column, index) => (
                    <Box key={`stack-column-${index}`} sx={{ flexShrink: 0 }}>
                        <ImagesStackComponent
                            caption={column.caption}
                            images={column.images}
                            level={index}
                            onImageClick={(image) => onImageClick(image, index)}
                        />
                    </Box>
                ))}
            </Box>
        );
    };

    // Render the flat view (non-hierarchical)
    const renderFlatView = () => {
        return (
            <Box sx={{ mt: 2, height: 'calc(100% - 160px)', overflow: 'auto' }}>
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

                {/* Enhanced view mode selector */}
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