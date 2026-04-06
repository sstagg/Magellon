import React from 'react';
import {
    Box,
    Slider,
    Switch,
    ToggleButton,
    ToggleButtonGroup,
    Typography,
    useTheme,
} from '@mui/material';
import { LayoutGrid, List, Layers } from 'lucide-react';
import { useImageViewerStore, ViewMode } from '../model/imageViewerStore.ts';

export const ColumnSettingsPanel: React.FC = () => {
    const theme = useTheme();

    const {
        thumbnailSize,
        autoHideEmpty,
        viewMode,
        setThumbnailSize,
        setAutoHideEmpty,
        setViewMode,
    } = useImageViewerStore();

    const handleViewModeChange = (
        _event: React.MouseEvent<HTMLElement>,
        newMode: ViewMode | null,
    ) => {
        if (newMode !== null) {
            setViewMode(newMode);
        }
    };

    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                px: 1.5,
                py: 0.5,
                maxHeight: 40,
                backgroundColor: theme.palette.background.default,
                borderBottom: `1px solid ${theme.palette.divider}`,
            }}
        >
            {/* Thumbnail size slider */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 160 }}>
                <Typography variant="caption" color="text.secondary" noWrap>
                    Size
                </Typography>
                <Slider
                    size="small"
                    value={thumbnailSize}
                    min={80}
                    max={200}
                    step={20}
                    onChange={(_e, value) => setThumbnailSize(value as number)}
                    sx={{ flex: 1 }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 24 }}>
                    {thumbnailSize}
                </Typography>
            </Box>

            {/* View mode toggle */}
            <ToggleButtonGroup
                size="small"
                value={viewMode}
                exclusive
                onChange={handleViewModeChange}
                sx={{ height: 28 }}
            >
                <ToggleButton value="grid" sx={{ px: 1 }}>
                    <LayoutGrid size={16} />
                </ToggleButton>
                <ToggleButton value="tree" sx={{ px: 1 }}>
                    <List size={16} />
                </ToggleButton>
                <ToggleButton value="flat" sx={{ px: 1 }}>
                    <Layers size={16} />
                </ToggleButton>
            </ToggleButtonGroup>

            {/* Auto-hide empty switch */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 'auto' }}>
                <Typography variant="caption" color="text.secondary" noWrap>
                    Hide empty
                </Typography>
                <Switch
                    size="small"
                    checked={autoHideEmpty}
                    onChange={(_e, checked) => setAutoHideEmpty(checked)}
                />
            </Box>
        </Box>
    );
};
