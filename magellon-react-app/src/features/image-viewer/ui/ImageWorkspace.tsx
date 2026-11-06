import React, { useEffect, useMemo, useState } from 'react';
import type {
    SelectChangeEvent} from "@mui/material";
import {
    Badge,
    Box,
    Chip,
    Fab,
    IconButton,
    FormControl,
    Select,
    MenuItem,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme
} from "@mui/material";
import {
    Visibility,
    VisibilityOff,
    ViewColumn,
    AccountTreeRounded,
    GridOnRounded,
    FilterList,
} from "@mui/icons-material";
import { TableProperties } from "lucide-react";
import type { AtlasImageDto, SessionDto } from "../../../entities/image/types.ts";
import type ImageInfoDto from "../../../entities/image/types.ts";
import type { ViewMode } from '../model/imageViewerStore.ts';
import { useImageViewerStore } from '../model/imageViewerStore.ts';
import type { ImageColumn as ImageColumnState } from "../model/imageViewerStore.ts";
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import ColumnBrowser from "./ColumnBrowser.tsx";
import ImageTable from "./ImageTable.tsx";
import { AtlasSection } from './AtlasSection.tsx';
import { DeleteSessionButton } from './DeleteSessionButton.tsx';
import ImageFilterDialog from './ImageFilterDialog.tsx';
import { useAllSessionImages } from '../api/usePagedImagesHook.ts';
import { EMPTY_FILTER, countActiveFilters, describeFilter } from '../lib/imageFilter.ts';

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
    selectedImage: _selectedImage,
    selectedSession,
    ImageColumns,
    Atlases,
    Sessions,
    OnSessionSelected
}) => {
    const theme = useTheme();

    const {
        isAtlasVisible,
        viewMode,
        currentAtlas,
        currentSession,
        toggleAtlasVisibility,
        setViewMode,
        setCurrentAtlas,
        imageFilter,
        setImageFilter,
    } = useImageViewerStore();

    const sessionName = currentSession?.name || selectedSession?.name || '';

    // One filter for the whole session, whichever layout shows it.
    const [filterOpen, setFilterOpen] = useState(false);
    const filterCount = countActiveFilters(imageFilter);
    const filterText = useMemo(() => describeFilter(imageFilter), [imageFilter]);
    const { images: sessionImages } = useAllSessionImages(sessionName, filterOpen || filterCount > 0);

    // The selected session was deleted elsewhere (another tab or user, or its
    // import was stopped): once the refreshed list no longer has it, let it go.
    useEffect(() => {
        if (selectedSession?.name && Sessions?.length && !Sessions.some((s) => s.name === selectedSession.name)) {
            OnSessionSelected({ target: { value: '' } } as SelectChangeEvent);
        }
    }, [Sessions, selectedSession?.name]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleViewModeChange = (
        _event: React.MouseEvent<HTMLElement>,
        newMode: ViewMode | null,
    ) => {
        if (newMode !== null) setViewMode(newMode);
    };

    const renderNavView = () => {
        switch (viewMode) {
            case 'grid':
                return (
                    <ColumnBrowser
                        imageColumns={ImageColumns}
                        onImageClick={onImageClick}
                        sessionName={sessionName}
                        showSettings={true}
                        initialSettingsCollapsed={true}
                        height="100%"
                    />
                );
            case 'tree':
                return (
                    <HierarchyBrowser
                        key={sessionName}
                        sessionName={sessionName}
                        onImageClick={onImageClick}
                        title="Image Hierarchy"
                    />
                );
            case 'flat':
                return (
                    <GridGallery
                        key={sessionName}
                        sessionName={sessionName}
                        onImageClick={onImageClick}
                        title="All Images"
                    />
                );
            case 'table':
                return <ImageTable key={sessionName} sessionName={sessionName} onImageClick={onImageClick} />;
            default:
                return null;
        }
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            position: 'relative',
        }}>
            {/* ─── Header: Session dropdown | View mode icons ─── */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                px: 1,
                py: 0.5,
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: theme.palette.background.paper,
                flexShrink: 0,
            }}>
                {/* Session dropdown */}
                <FormControl size="small" sx={{ minWidth: 180, flex: 1 }}>
                    <Select
                        displayEmpty
                        value={selectedSession?.name || ""}
                        onChange={OnSessionSelected}
                        sx={{
                            height: 32,
                            fontSize: '0.85rem',
                            '& .MuiSelect-select': { py: 0.5 },
                        }}
                    >
                        <MenuItem value="">
                            <em>Select Collection...</em>
                        </MenuItem>
                        {Sessions?.map((session) => (
                            <MenuItem key={session.name} value={session.name}>
                                {session.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
                <DeleteSessionButton
                    sessionName={selectedSession?.name || ''}
                    onDeleted={() => OnSessionSelected({ target: { value: '' } } as SelectChangeEvent)}
                />

                <Tooltip title="Filter the session's images">
                    <span>
                        <IconButton
                            size="small"
                            aria-label="Filter images"
                            disabled={!sessionName}
                            onClick={() => setFilterOpen(true)}
                            color={filterCount > 0 ? 'primary' : 'default'}
                        >
                            <Badge badgeContent={filterCount} color="primary">
                                <FilterList fontSize="small" />
                            </Badge>
                        </IconButton>
                    </span>
                </Tooltip>

                {/* View mode toggle (center) */}
                <ToggleButtonGroup
                    size="small"
                    value={viewMode}
                    exclusive
                    onChange={handleViewModeChange}
                    sx={{
                        height: 30,
                        '& .MuiToggleButton-root': {
                            px: 1,
                            border: 'none',
                            borderRadius: '6px !important',
                            mx: 0.25,
                        },
                    }}
                >
                    <ToggleButton value="grid">
                        <Tooltip title="Columns"><ViewColumn fontSize="small" /></Tooltip>
                    </ToggleButton>
                    <ToggleButton value="flat">
                        <Tooltip title="Grid"><GridOnRounded fontSize="small" /></Tooltip>
                    </ToggleButton>
                    <ToggleButton value="tree">
                        <Tooltip title="Tree"><AccountTreeRounded fontSize="small" /></Tooltip>
                    </ToggleButton>
                    <ToggleButton value="table">
                        <Tooltip title="Table"><TableProperties size={18} /></Tooltip>
                    </ToggleButton>
                </ToggleButtonGroup>
            </Box>

            {filterCount > 0 && (
                <Box sx={{ px: 1, py: 0.5, borderBottom: `1px solid ${theme.palette.divider}`, flexShrink: 0 }}>
                    <Chip
                        data-testid="active-filter"
                        icon={<FilterList fontSize="small" />}
                        label={filterText}
                        title={filterText}
                        color="primary"
                        variant="outlined"
                        size="small"
                        onClick={() => setFilterOpen(true)}
                        onDelete={() => setImageFilter(EMPTY_FILTER)}
                        sx={{ maxWidth: '100%' }}
                    />
                </Box>
            )}

            <ImageFilterDialog
                open={filterOpen}
                onClose={() => setFilterOpen(false)}
                onApplyFilter={setImageFilter}
                currentFilter={imageFilter}
                images={sessionImages}
            />

            {/* ─── Atlas section ─── */}
            <AtlasSection
                atlases={Atlases}
                currentAtlas={currentAtlas}
                sessionName={sessionName}
                isVisible={isAtlasVisible}
                onAtlasChange={setCurrentAtlas}
                onImageClick={onImageClick}
            />

            {/* ─── Main content (includes its own Column View Settings) ─── */}
            <Box sx={{
                flex: 1,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
            }}>
                {renderNavView()}
            </Box>

            {/* ─── Atlas toggle FAB ─── */}
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
                    '&:hover': { boxShadow: 6, transform: 'scale(1.05)' },
                    transition: 'all 0.2s ease-in-out',
                }}
                aria-label={isAtlasVisible ? "Hide Atlas" : "Show Atlas"}
            >
                {isAtlasVisible ? <VisibilityOff /> : <Visibility />}
            </Fab>
        </Box>
    );
};
