import React, { useState, useCallback } from 'react';
import {
    Box,
    Paper,
    Typography,
    Collapse,
    IconButton,
    Divider
} from '@mui/material';
import { ExpandLess, ExpandMore, Settings } from '@mui/icons-material';
import ImageInfoDto from './ImageInfoDto.ts';
import { ImageColumnState } from '../../panel/pages/ImagesPageView.tsx';
import InteractiveColumn from './InteractiveColumn.tsx';
import { ImageColumn } from './ImageColumn.tsx';
import ColumnPreferences, {
    ColumnSettings,
    defaultColumnSettings
} from './ColumnPreferences.tsx';
import { useVisibleColumns, useColumnStatistics } from './store/useVisibleColumns.ts';

interface StackedViewProps {
    imageColumns: ImageColumnState[];
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    sessionName: string;
    showSettings?: boolean;
    initialSettings?: Partial<ColumnSettings>;
    initialSettingsCollapsed?: boolean;
    height?: string | number;
    sx?: object;
}

// Settings Panel Component
const SettingsPanel: React.FC<{
    settings: ColumnSettings;
    onSettingsChange: (settings: ColumnSettings) => void;
    statistics: { totalColumns: number; visibleCount: number; totalImages: number };
    collapsed: boolean;
    onToggleCollapse: () => void;
}> = ({ settings, onSettingsChange, statistics, collapsed, onToggleCollapse }) => {
    const isHorizontal = settings.columnDirection === 'horizontal';

    return (
        <Paper
            elevation={0}
            variant="outlined"
            sx={{
                mb: 1,
                borderRadius: 1,
                overflow: 'hidden',
                flexShrink: 0
            }}
        >
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    px: 1.5,
                    py: 0.75,
                    backgroundColor: 'grey.50',
                    cursor: 'pointer',
                    minHeight: 36
                }}
                onClick={onToggleCollapse}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Settings sx={{ fontSize: 16 }} />
                    <Typography variant="subtitle2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
                        Column View Settings
                    </Typography>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                        {statistics.visibleCount}/{statistics.totalColumns} columns • {statistics.totalImages} images • {isHorizontal ? 'H' : 'V'}
                    </Typography>

                    <IconButton size="small" sx={{ p: 0.25 }}>
                        {collapsed ? <ExpandMore fontSize="small" /> : <ExpandLess fontSize="small" />}
                    </IconButton>
                </Box>
            </Box>

            <Collapse in={!collapsed}>
                <Box sx={{ p: 1.5 }}>
                    <ColumnPreferences
                        settings={settings}
                        onSettingsChange={onSettingsChange}
                        visible={true}
                        showEnhancedToggle={true}
                        paper={false}
                    />
                </Box>
            </Collapse>
        </Paper>
    );
};

// Column Layout Component
const ColumnLayout: React.FC<{
    columns: ImageColumnState[];
    allColumns: ImageColumnState[];
    settings: ColumnSettings;
    sessionName: string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
}> = ({ columns, allColumns, settings, sessionName, onImageClick }) => {
    const isHorizontal = settings.columnDirection === 'horizontal';

    // Render empty state
    if (columns.length === 0) {
        return (
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '100%',
                color: 'text.secondary'
            }}>
                <Typography variant="body1" gutterBottom>
                    No columns to display
                </Typography>
                <Typography variant="body2">
                    Adjust your settings or select a session to view images
                </Typography>
            </Box>
        );
    }

    // Render enhanced columns
    if (settings.useEnhancedColumns) {
        return (
            <Box sx={{
                display: 'flex',
                flexDirection: isHorizontal ? 'column' : 'row',
                gap: 1,
                overflow: 'auto',
                height: '100%',
                pb: 1,
                flex: 1
            }}>
                {columns.map((column, index) => {
                    const originalIndex = allColumns.findIndex(col => col === column);

                    return (
                        <InteractiveColumn
                            key={`enhanced-column-${originalIndex}`}
                            caption={column.caption}
                            level={originalIndex}
                            parentImage={originalIndex === 0 ? null : allColumns[originalIndex - 1]?.selectedImage || null}
                            sessionName={sessionName}
                            width={isHorizontal ? undefined : settings.columnWidth}
                            height={isHorizontal ? settings.columnWidth : undefined}
                            onImageClick={onImageClick}
                            showControls={settings.showColumnControls}
                            collapsible={originalIndex > 0}
                            sx={{
                                flexShrink: 0,
                                ...(isHorizontal ? {
                                    width: '100%',
                                    height: settings.columnWidth,
                                    minHeight: settings.columnWidth,
                                    maxHeight: settings.columnWidth
                                } : {
                                    height: '100%',
                                    width: settings.columnWidth,
                                    minWidth: settings.columnWidth,
                                    maxWidth: settings.columnWidth
                                })
                            }}
                        />
                    );
                })}
            </Box>
        );
    }

    // Render legacy columns
    return (
        <Box sx={{
            display: 'flex',
            flexDirection: isHorizontal ? 'column' : 'row',
            flexWrap: 'nowrap',
            overflow: 'auto',
            height: '100%',
            flex: 1
        }}>
            {allColumns.map((column, index) => (
                <Box
                    key={`stack-column-${index}`}
                    sx={{
                        flexShrink: 0,
                        ...(isHorizontal ? {
                            width: '100%',
                            height: settings.columnWidth,
                            minHeight: settings.columnWidth,
                            maxHeight: settings.columnWidth
                        } : {
                            width: settings.columnWidth,
                            minWidth: settings.columnWidth,
                            maxWidth: settings.columnWidth
                        })
                    }}
                >
                    <ImageColumn
                        caption={column.caption}
                        images={column.images}
                        level={index}
                        direction={settings.columnDirection}
                        width={isHorizontal ? undefined : settings.columnWidth}
                        height={isHorizontal ? settings.columnWidth : undefined}
                        onImageClick={(image) => onImageClick(image, index)}
                    />
                </Box>
            ))}
        </Box>
    );
};

// Main ColumnBrowser Component
export const ColumnBrowser: React.FC<StackedViewProps> = ({
                                                              imageColumns = [],
                                                              onImageClick,
                                                              sessionName,
                                                              showSettings = true,
                                                              initialSettings = {},
                                                              initialSettingsCollapsed = true,
                                                              height = '100%',
                                                              sx = {}
                                                          }) => {
    // State
    const [columnSettings, setColumnSettings] = useState<ColumnSettings>({
        ...defaultColumnSettings,
        columnWidth: Math.max(175, defaultColumnSettings.columnWidth),
        ...initialSettings
    });

    const [settingsCollapsed, setSettingsCollapsed] = useState(initialSettingsCollapsed);

    // Use custom hooks
    const visibleColumns = useVisibleColumns(imageColumns, columnSettings.autoHideEmptyColumns);
    const statistics = useColumnStatistics(imageColumns, visibleColumns);

    // Handlers
    const handleSettingsToggle = useCallback(() => {
        setSettingsCollapsed(prev => !prev);
    }, []);

    return (
        <Box sx={{
            height,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            ...sx
        }}>
            {/* Settings panel */}
            {showSettings && (
                <SettingsPanel
                    settings={columnSettings}
                    onSettingsChange={setColumnSettings}
                    statistics={statistics}
                    collapsed={settingsCollapsed}
                    onToggleCollapse={handleSettingsToggle}
                />
            )}

            {/* Main columns view */}
            <Box sx={{
                flex: 1,
                overflow: 'hidden',
                border: theme => `1px solid ${theme.palette.divider}`,
                borderRadius: 1,
                backgroundColor: 'background.paper',
                display: 'flex',
                flexDirection: 'column'
            }}>
                <ColumnLayout
                    columns={visibleColumns}
                    allColumns={imageColumns}
                    settings={columnSettings}
                    sessionName={sessionName}
                    onImageClick={onImageClick}
                />
            </Box>
        </Box>
    );
};

export default ColumnBrowser;