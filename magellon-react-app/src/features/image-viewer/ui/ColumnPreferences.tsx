import React from 'react';
import {
    Box,
    Paper,
    FormControlLabel,
    Switch,
    Typography,
    Slider,
    Divider,
    ToggleButton,
    ToggleButtonGroup
} from '@mui/material';
import { AutoAwesome, ViewColumn, ViewAgenda } from '@mui/icons-material';

export interface ColumnSettings {
    columnWidth: number;
    showColumnControls: boolean;
    autoHideEmptyColumns: boolean;
    useEnhancedColumns: boolean;
    columnDirection: 'vertical' | 'horizontal';
}

interface ColumnSettingsProps {
    settings: ColumnSettings;
    onSettingsChange: (newSettings: ColumnSettings) => void;
    visible?: boolean;
    showEnhancedToggle?: boolean;
    minWidth?: number;
    maxWidth?: number;
    paper?: boolean;
    sx?: object;
}

export const ColumnPreferences: React.FC<ColumnSettingsProps> = ({
                                                                     settings,
                                                                     onSettingsChange,
                                                                     visible = true,
                                                                     showEnhancedToggle = true,
                                                                     minWidth = 150,
                                                                     maxWidth = 600,
                                                                     paper = true,
                                                                     sx = {}
                                                                 }) => {
    const updateSetting = <K extends keyof ColumnSettings>(
        key: K,
        value: ColumnSettings[K]
    ) => {
        onSettingsChange({
            ...settings,
            [key]: value
        });
    };

    const handleDirectionChange = (
        event: React.MouseEvent<HTMLElement>,
        newDirection: 'vertical' | 'horizontal' | null,
    ) => {
        if (newDirection !== null) {
            updateSetting('columnDirection', newDirection);
        }
    };

    const content = (
        <Box sx={{ ...(!paper ? sx : {}) }}>
            {/* Row 1: All toggle switches in one line */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                flexWrap: 'wrap',
                mb: 1.5
            }}>
                {showEnhancedToggle && (
                    <FormControlLabel
                        control={
                            <Switch
                                size="small"
                                checked={settings.useEnhancedColumns}
                                onChange={(e) => updateSetting('useEnhancedColumns', e.target.checked)}
                            />
                        }
                        label={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <AutoAwesome sx={{ fontSize: 14 }} />
                                <Typography variant="caption">Enhanced</Typography>
                            </Box>
                        }
                        sx={{ m: 0 }}
                    />
                )}

                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={settings.autoHideEmptyColumns}
                            onChange={(e) => updateSetting('autoHideEmptyColumns', e.target.checked)}
                        />
                    }
                    label={
                        <Typography variant="caption">
                            Auto-hide empty
                        </Typography>
                    }
                    sx={{ m: 0 }}
                />

                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={settings.showColumnControls}
                            onChange={(e) => updateSetting('showColumnControls', e.target.checked)}
                        />
                    }
                    label={
                        <Typography variant="caption">
                            Show controls
                        </Typography>
                    }
                    sx={{ m: 0 }}
                />
            </Box>

            <Divider sx={{ my: 1 }} />

            {/* Row 2: Slider and Direction Toggle in one line */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                flexWrap: 'wrap'
            }}>
                {/* Column Width/Height Slider */}
                <Box sx={{ flex: 1, minWidth: 200 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography variant="caption" sx={{ fontWeight: 500 }}>
                            {settings.columnDirection === 'horizontal' ? 'Height' : 'Width'}: {settings.columnWidth}px
                        </Typography>
                    </Box>
                    <Slider
                        value={settings.columnWidth}
                        onChange={(_, value) => updateSetting('columnWidth', value as number)}
                        min={minWidth}
                        max={maxWidth}
                        size="small"
                        valueLabelDisplay="auto"
                        step={10}
                        sx={{
                            '& .MuiSlider-thumb': {
                                width: 14,
                                height: 14,
                            }
                        }}
                    />
                </Box>

                {/* Column Direction Toggle */}
                <Box>
                    <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 500 }}>
                        Layout
                    </Typography>
                    <ToggleButtonGroup
                        value={settings.columnDirection}
                        exclusive
                        onChange={handleDirectionChange}
                        size="small"
                        sx={{
                            '& .MuiToggleButton-root': {
                                py: 0.25,
                                px: 1,
                                fontSize: '0.75rem'
                            }
                        }}
                    >
                        <ToggleButton value="vertical">
                            <ViewColumn sx={{ mr: 0.5, fontSize: 16 }} />
                            <Typography variant="caption">V</Typography>
                        </ToggleButton>
                        <ToggleButton value="horizontal">
                            <ViewAgenda sx={{ mr: 0.5, fontSize: 16 }} />
                            <Typography variant="caption">H</Typography>
                        </ToggleButton>
                    </ToggleButtonGroup>
                </Box>
            </Box>
        </Box>
    );

    if (!visible) {
        return null;
    }

    if (paper) {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 1.5, borderRadius: 1, ...sx }}>
                {content}
            </Paper>
        );
    }

    return content;
};

export const defaultColumnSettings: ColumnSettings = {
    columnWidth: 150,
    showColumnControls: true,
    autoHideEmptyColumns: true,
    useEnhancedColumns: true,
    columnDirection: 'vertical'
};

export default ColumnPreferences;