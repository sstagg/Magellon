import React, { useState, useMemo } from 'react';
import {
    Box,
    Paper,
    Typography,
    Collapse,
    IconButton,
    Tooltip,
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

interface StackedViewProps {
    /**
     * Array of image columns to display
     */
    imageColumns: ImageColumnState[];
    /**
     * Callback when an image is clicked
     */
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    /**
     * Current session name
     */
    sessionName: string;
    /**
     * Whether to show the settings panel
     */
    showSettings?: boolean;
    /**
     * Initial column settings
     */
    initialSettings?: Partial<ColumnSettings>;
    /**
     * Whether settings panel is initially collapsed
     */
    initialSettingsCollapsed?: boolean;
    /**
     * Custom height for the view
     */
    height?: string | number;
    /**
     * Custom styling
     */
    sx?: object;
}

/**
 * StackedView component that manages the column view display with settings
 */
export const ColumnBrowser: React.FC<StackedViewProps> = ({
                                                              imageColumns = [], // Add default value
                                                              onImageClick,
                                                              sessionName,
                                                              showSettings = true,
                                                              initialSettings = {},
                                                              initialSettingsCollapsed = false,
                                                              height = '100%',
                                                              sx = {}
                                                          }) => {
    // Column settings state
    const [columnSettings, setColumnSettings] = useState<ColumnSettings>({
        ...defaultColumnSettings,
        ...initialSettings
    });

    // Settings panel state
    const [settingsCollapsed, setSettingsCollapsed] = useState(initialSettingsCollapsed);

    // Calculate which columns should be visible based on settings
    const visibleColumns = useMemo(() => {
        // Guard against undefined imageColumns
        if (!imageColumns || !Array.isArray(imageColumns)) {
            return [];
        }

        return imageColumns.filter((col, index) => {
            if (!columnSettings.autoHideEmptyColumns) return true;

            // Always show the first column
            if (index === 0) return true;

            // Show column if it has data or if the previous column has a selected image
            return col.images && col.images.pages && col.images.pages.length > 0;
        });
    }, [imageColumns, columnSettings.autoHideEmptyColumns]);

    // Get statistics for display
    const statistics = useMemo(() => {
        // Guard against undefined imageColumns
        if (!imageColumns || !Array.isArray(imageColumns)) {
            return {
                totalColumns: 0,
                visibleCount: 0,
                totalImages: 0
            };
        }

        const totalColumns = imageColumns.length;
        const visibleCount = visibleColumns.length;
        const totalImages = imageColumns.reduce((sum, col) => {
            const imageCount = col.images?.pages?.reduce((pageSum, page) => pageSum + page.result.length, 0) || 0;
            return sum + imageCount;
        }, 0);

        return {
            totalColumns,
            visibleCount,
            totalImages
        };
    }, [imageColumns, visibleColumns]);

    // Render the settings panel
    const renderSettingsPanel = () => {
        if (!showSettings) return null;

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
                {/* Settings header */}
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        backgroundColor: 'grey.50',
                        cursor: 'pointer'
                    }}
                    onClick={() => setSettingsCollapsed(!settingsCollapsed)}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Settings sx={{ fontSize: 16 }} />
                        <Typography variant="subtitle2" sx={{ fontWeight: 500 }}>
                            Column View Settings
                        </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {/* Statistics */}
                        <Typography variant="caption" color="text.secondary">
                            {statistics.visibleCount}/{statistics.totalColumns} columns • {statistics.totalImages} images
                        </Typography>

                        <IconButton size="small">
                            {settingsCollapsed ? <ExpandMore /> : <ExpandLess />}
                        </IconButton>
                    </Box>
                </Box>

                {/* Settings content */}
                <Collapse in={!settingsCollapsed}>
                    <Box sx={{ p: 1 }}>
                        <ColumnPreferences
                            settings={columnSettings}
                            onSettingsChange={setColumnSettings}
                            visible={true}
                            showEnhancedToggle={true}
                            paper={false}
                        />
                    </Box>
                </Collapse>
            </Paper>
        );
    };

    // Render enhanced columns view
    const renderEnhancedView = () => {
        const isHorizontal = columnSettings.columnDirection === 'horizontal';

        return (
            <Box sx={{
                display: 'flex',
                flexDirection: isHorizontal ? 'column' : 'row',
                gap: 1,
                overflow: isHorizontal ? 'auto' : 'auto',
                height: '100%',
                pb: 1,
                flex: 1
            }}>
                {visibleColumns.map((column, index) => {
                    // Find the original index in the full imageColumns array
                    const originalIndex = imageColumns.findIndex(col => col === column);

                    return (
                        <InteractiveColumn
                            key={`enhanced-column-${originalIndex}`}
                            caption={column.caption}
                            level={originalIndex}
                            parentImage={originalIndex === 0 ? null : imageColumns[originalIndex - 1]?.selectedImage || null}
                            sessionName={sessionName}
                            width={isHorizontal ? undefined : columnSettings.columnWidth}
                            height={isHorizontal ? columnSettings.columnWidth : undefined} // Use columnWidth as height for horizontal
                            onImageClick={onImageClick}
                            showControls={columnSettings.showColumnControls}
                            collapsible={originalIndex > 0}
                            sx={{
                                flexShrink: 0,
                                ...(isHorizontal ? {
                                    width: '100%',
                                    height: columnSettings.columnWidth
                                } : {
                                    height: '100%',
                                    width: columnSettings.columnWidth
                                })
                            }}
                        />
                    );
                })}

                {/* Placeholder when no columns are visible */}
                {visibleColumns.length === 0 && (
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
                )}
            </Box>
        );
    };

    // Render legacy stack view
    const renderLegacyView = () => {
        const isHorizontal = columnSettings.columnDirection === 'horizontal';

        return (
            <Box sx={{
                display: 'flex',
                flexDirection: isHorizontal ? 'column' : 'row',
                flexWrap: 'nowrap',
                overflow: 'auto',
                height: '100%',
                flex: 1
            }}>
                {imageColumns.map((column, index) => (
                    <Box
                        key={`stack-column-${index}`}
                        sx={{
                            flexShrink: 0,
                            ...(isHorizontal && {
                                width: '100%',
                                height: columnSettings.columnWidth
                            })
                        }}
                    >
                        <ImageColumn
                            caption={column.caption}
                            images={column.images}
                            level={index}
                            onImageClick={(image) => onImageClick(image, index)}
                        />
                    </Box>
                ))}

                {/* Placeholder when no columns have data */}
                {imageColumns.every(col => !col.images || !col.images.pages || col.images.pages.length === 0) && (
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
                            No images to display
                        </Typography>
                        <Typography variant="body2">
                            Select a session to view images
                        </Typography>
                    </Box>
                )}
            </Box>
        );
    };

    return (
        <Box sx={{
            height,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            ...sx
        }}>
            {/* Settings panel */}
            {renderSettingsPanel()}

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
                {columnSettings.useEnhancedColumns
                    ? renderEnhancedView()
                    : renderLegacyView()
                }
            </Box>
        </Box>
    );
};

export default ColumnBrowser;