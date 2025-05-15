import {
    ButtonGroup,
    Card,
    CardContent,
    FormControl,
    Grid,
    ImageList,
    ImageListItem,
    InputLabel,
    MenuItem,
    Select,
    SelectChangeEvent,
    Stack,
    Tooltip
} from "@mui/material";
import Typography from "@mui/material/Typography";
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
            <Grid item container sx={{ marginTop: 3 }}>
                <TreeViewer
                    images={ImageColumns[0].images}
                    onImageClick={onImageClick}
                    title="Image Hierarchy"
                />
            </Grid>
        );
    };

    // Render the column view (original)
    const renderGridView = () => {
        return (
            <Grid item container sx={{ marginTop: 3 }}>
                <ImagesStackComponent caption={ImageColumns[0].caption} images={ImageColumns[0].images} level={0} onImageClick={(image) => onImageClick(image, 0)} />
                <ImagesStackComponent caption={ImageColumns[1].caption} images={ImageColumns[1].images} level={1} onImageClick={(image) => onImageClick(image, 1)} />
                <ImagesStackComponent caption={ImageColumns[2].caption} images={ImageColumns[2].images} level={2} onImageClick={(image) => onImageClick(image, 2)} />
                <ImagesStackComponent caption={ImageColumns[3].caption} images={ImageColumns[3].images} level={3} onImageClick={(image) => onImageClick(image, 3)} />
            </Grid>
        );
    };

    // Render the flat view (non-hierarchical)
    const renderFlatView = () => {
        return (
            <Grid item container sx={{ marginTop: 3 }}>
                <FlatImageViewerComponent
                    images={ImageColumns[0].images}
                    onImageClick={onImageClick}
                    title="All Images"
                />
            </Grid>
        );
    };

    return (
        <Grid container direction="column">
            <Grid item container>
                <Stack>
                    <FormControl sx={{ m: 1, minWidth: 120 }} size="small" variant="standard">
                        <InputLabel id="demo-select-small-label">Session</InputLabel>
                        <Select
                            labelId="demo-select-small-label"
                            id="demo-select-small"
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

                    <ButtonGroup size="small">
                        <IconButton key="one" onClick={toggleAtlasVisibility}>
                            <EyeOutlined />
                        </IconButton>
                        <Tooltip title="Column View">
                            <IconButton
                                key="two"
                                onClick={() => setViewMode('grid')}
                                color={viewMode === 'grid' ? 'primary' : 'default'}
                            >
                                <GridViewRounded />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Tree View">
                            <IconButton
                                key="three"
                                onClick={() => setViewMode('tree')}
                                color={viewMode === 'tree' ? 'primary' : 'default'}
                            >
                                <AccountTreeRounded />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Flat View">
                            <IconButton
                                key="four"
                                onClick={() => setViewMode('flat')}
                                color={viewMode === 'flat' ? 'primary' : 'default'}
                            >
                                <GridOnRounded />
                            </IconButton>
                        </Tooltip>
                    </ButtonGroup>
                    {isAtlasVisible ? (
                        <Grid container>
                            <Grid item>
                                <ImageList cols={1} rowHeight={170} sx={{ width: 170, height: 400, display: 'block' }}>
                                    {Atlases?.map((atlas, index) => (
                                        <ImageListItem key={index} onClick={() => handleAtlasClick(atlas)}>
                                            {/* Add sessionName parameter to the atlas image URL */}
                                            <img
                                                src={`${BASE_URL}/atlas-image?name=${atlas?.name}&sessionName=${sessionName}`}
                                                alt="atlas"
                                                className={"thumb-image"}
                                                style={{ cursor: 'pointer' }}
                                            />
                                        </ImageListItem>
                                    ))}
                                </ImageList>
                            </Grid>
                            <Grid item>
                                {currentAtlas && (
                                    <Card sx={{ maxWidth: 345, marginLeft: 2 }}>
                                        <AtlasImage
                                            imageMapJson={currentAtlas?.meta}
                                            finalWidth={300}
                                            finalHeight={300}
                                            name={currentAtlas?.name}
                                            backgroundColor={"black"}
                                            onImageClick={onImageClick}
                                        />
                                        <CardContent>
                                            <Typography gutterBottom variant="h5" component="div">
                                                Name: {currentAtlas?.name}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                )}
                            </Grid>
                        </Grid>
                    ) : null}
                </Stack>
            </Grid>
            {renderNavView()}
        </Grid>
    );
};