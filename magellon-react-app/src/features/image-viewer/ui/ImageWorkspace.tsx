import React from 'react';
import {
    Box,
    Fab,
    FormControl,
    Select,
    MenuItem,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme,
    SelectChangeEvent,
} from "@mui/material";
import {
    Visibility,
    VisibilityOff,
    ViewColumn,
    AccountTreeRounded,
    GridOnRounded,
} from "@mui/icons-material";
import { TableProperties } from "lucide-react";
import ImageInfoDto, { AtlasImageDto, SessionDto } from "../../../entities/image/types.ts";
import { useImageViewerStore, ViewMode } from '../model/imageViewerStore.ts';
import { ImageColumn as ImageColumnState } from "../model/imageViewerStore.ts";
import GridGallery from "./GridGallery.tsx";
import HierarchyBrowser from "./HierarchyBrowser.tsx";
import ColumnBrowser from "./ColumnBrowser.tsx";
import { AtlasSection } from './AtlasSection.tsx';

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

    const {
        isAtlasVisible,
        viewMode,
        currentAtlas,
        currentSession,
        toggleAtlasVisibility,
        setViewMode,
        setCurrentAtlas,
    } = useImageViewerStore();

    const sessionName = currentSession?.name || selectedSession?.name || '';

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
                        initialSettingsCollapsed={false}
                        height="100%"
                    />
                );
            case 'tree':
                return (
                    <HierarchyBrowser
                        images={ImageColumns[0].images}
                        onImageClick={onImageClick}
                        title="Image Hierarchy"
                    />
                );
            case 'flat':
                return (
                    <GridGallery
                        images={ImageColumns[0].images}
                        onImageClick={onImageClick}
                        title="All Images"
                    />
                );
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
                            <MenuItem key={session.Oid} value={session.name}>
                                {session.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

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
