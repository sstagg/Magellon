import React from 'react';
import {
    Box,
    Paper,
    FormControlLabel,
    Switch,
    Typography,
    Slider,
    Collapse,
    Divider,
    ToggleButton,
    ToggleButtonGroup
} from '@mui/material';
import { AutoAwesome, Settings, ViewColumn, ViewAgenda } from '@mui/icons-material';

// Configuration interface for column settings
export interface ColumnSettings {
    columnWidth: number;
    showColumnControls: boolean;
    autoHideEmptyColumns: boolean;
    useEnhancedColumns: boolean;
    columnDirection: 'vertical' | 'horizontal'; // Add direction property
}

// Props for the ColumnSettingsComponent
interface ColumnSettingsProps {
    /**
     * Current column settings
     */
    settings: ColumnSettings;
    /**
     * Callback when settings change
     */
    onSettingsChange: (newSettings: ColumnSettings) => void;
    /**
     * Whether the settings panel is visible
     */
    visible?: boolean;
    /**
     * Whether to show the enhanced columns toggle
     */
    showEnhancedToggle?: boolean;
    /**
     * Minimum column width
     */
    minWidth?: number;
    /**
     * Maximum column width
     */
    maxWidth?: number;
    /**
     * Whether to show in a paper container
     */
    paper?: boolean;
    /**
     * Custom styling
     */
    sx?: object;
}

/**
 * Reusable component for configuring column view settings
 */
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
    // Helper function to update settings
    const updateSetting = <K extends keyof ColumnSettings>(
        key: K,
        value: ColumnSettings[K]
    ) => {
        onSettingsChange({
            ...settings,
            [key]: value
        });
    };

    // Handle direction change
    const handleDirectionChange = (
        event: React.MouseEvent<HTMLElement>,
        newDirection: 'vertical' | 'horizontal' | null,
    ) => {
        if (newDirection !== null) {
            updateSetting('columnDirection', newDirection);
        }
    };

    // Main content
    const content = (
        <Box sx={{ px: 1, ...(!paper ? sx : {}) }}>
            {showEnhancedToggle && (
                <>
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
                                <AutoAwesome sx={{ fontSize: 16 }} />
                                <Typography variant="caption">Enhanced Columns</Typography>
                            </Box>
                        }
                    />

                    {settings.useEnhancedColumns && <Divider sx={{ my: 1 }} />}
                </>
            )}

            <Collapse in={!showEnhancedToggle || settings.useEnhancedColumns}>
                <Box sx={{ mt: showEnhancedToggle ? 1 : 0 }}>
                    {/* Column Direction Toggle */}
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="caption" gutterBottom sx={{ display: 'block' }}>
                            Layout Direction
                        </Typography>
                        <ToggleButtonGroup
                            value={settings.columnDirection}
                            exclusive
                            onChange={handleDirectionChange}
                            size="small"
                            fullWidth
                        >
                            <ToggleButton value="vertical">
                                <ViewColumn sx={{ mr: 0.5, fontSize: 16 }} />
                                <Typography variant="caption">Vertical</Typography>
                            </ToggleButton>
                            <ToggleButton value="horizontal">
                                <ViewAgenda sx={{ mr: 0.5, fontSize: 16 }} />
                                <Typography variant="caption">Horizontal</Typography>
                            </ToggleButton>
                        </ToggleButtonGroup>
                    </Box>

                    {/* Column Width/Height Slider */}
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="caption" gutterBottom sx={{ display: 'block' }}>
                            {settings.columnDirection === 'horizontal' ? 'Column Height' : 'Column Width'}: {settings.columnWidth}px
                        </Typography>
                        <Slider
                            value={settings.columnWidth}
                            onChange={(_, value) => updateSetting('columnWidth', value as number)}
                            min={minWidth}
                            max={maxWidth}
                            size="small"
                            valueLabelDisplay="auto"
                            step={10}
                            marks={[
                                { value: minWidth, label: `${minWidth}px` },
                                { value: Math.round((minWidth + maxWidth) / 2), label: 'Medium' },
                                { value: maxWidth, label: `${maxWidth}px` }
                            ]}
                        />
                    </Box>

                    {/* Auto-hide Empty Columns */}
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
                                Auto-hide empty columns
                            </Typography>
                        }
                        sx={{ mb: 1 }}
                    />

                    {/* Show Column Controls */}
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
                                Show column controls
                            </Typography>
                        }
                    />
                </Box>
            </Collapse>
        </Box>
    );

    if (!visible) {
        return null;
    }

    if (paper) {
        return (
            <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1, ...sx }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                    <Settings sx={{ fontSize: 16 }} />
                    <Typography variant="caption" sx={{ fontWeight: 500 }}>
                        Column Settings
                    </Typography>
                </Box>
                {content}
            </Paper>
        );
    }

    return (
        <Box sx={sx}>
            {content}
        </Box>
    );
};

// Default settings - updated to include direction
export const defaultColumnSettings: ColumnSettings = {
    columnWidth: 200,
    showColumnControls: true,
    autoHideEmptyColumns: true,
    useEnhancedColumns: true,
    columnDirection: 'vertical' // Default to vertical layout
};

export default ColumnPreferences;