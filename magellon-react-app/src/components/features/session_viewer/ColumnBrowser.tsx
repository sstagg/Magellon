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
import { useImageListQuery } from '../../../services/api/usePagedImagesHook.ts';

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

    // Determine layout properties
    const isHorizontal = columnSettings.columnDirection === 'horizontal';

    // Calculate responsive column height for horizontal mode
    const getResponsiveColumnHeight = () => {
        if (!isHorizontal) return columnSettings.columnWidth;

        // In horizontal mode, calculate available height and divide by number of visible columns
        const availableHeight = typeof window !== 'undefined' ? window.innerHeight - 200 : 600; // Subtract header/footer space
        const maxHeightPerColumn = Math.floor(availableHeight / Math.max(visibleColumns.length, 1));

        // Use the smaller of the configured height or the calculated responsive height
        return Math.min(columnSettings.columnWidth, Math.max(120, maxHeightPerColumn)); // Min 120px per column
    };

    const responsiveColumnHeight = getResponsiveColumnHeight();

    // Helper function to get pagination props for a specific column
    const getPaginationProps = (columnIndex: number) => {
        const column = imageColumns[columnIndex];
        const parentId = columnIndex === 0 ? null : column.selectedImage?.oid;

        const {
            fetchNextPage,
            hasNextPage,
            isFetchingNextPage
        } = useImageListQuery({
            sessionName,
            parentId,
            pageSize: 50,
            level: columnIndex,
            enabled: columnIndex === 0 || column.selectedImage !== null
        });

        return {
            fetchNextPage,
            hasNextPage,
            isFetchingNextPage
        };
    };

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
                            {statistics.visibleCount}/{statistics.totalColumns} columns • {statistics.totalImages} images • {isHorizontal ? 'Horizontal' : 'Vertical'}
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

    // Render column view
    const renderColumnView = () => {
        return (
            <Box sx={{
                display: 'flex',
                flexDirection: isHorizontal ? 'column' : 'row',
                gap: 1,
                overflow: 'auto',
                height: '100%',
                pb: 1,
                flex: 1,
            }}>
                {visibleColumns.map((column, index) => {
                    // Find the original index in the full imageColumns array
                    const originalIndex = imageColumns.findIndex(col => col === column);

                    // Get pagination props for this column
                    const paginationProps = getPaginationProps(originalIndex);

                    return columnSettings.useEnhancedColumns ? (
                        <InteractiveColumn
                            key={`enhanced-column-${originalIndex}`}
                            caption={column.caption}
                            level={originalIndex}
                            parentImage={originalIndex === 0 ? null : imageColumns[originalIndex - 1]?.selectedImage || null}
                            sessionName={sessionName}
                            width={isHorizontal ? undefined : columnSettings.columnWidth}
                            height={isHorizontal ? columnSettings.columnWidth : undefined}
                            onImageClick={onImageClick}
                            showControls={columnSettings.showColumnControls}
                            collapsible={originalIndex > 0}
                            sx={{
                                flexShrink: 0,
                                ...(isHorizontal ? {
                                    width: '100%',
                                    height: columnSettings.columnWidth,
                                    minHeight: columnSettings.columnWidth,
                                    maxHeight: columnSettings.columnWidth
                                } : {
                                    height: '100%',
                                    width: columnSettings.columnWidth,
                                    minWidth: columnSettings.columnWidth,
                                    maxWidth: columnSettings.columnWidth
                                })
                            }}
                        />
                    ) : (
                        <ImageColumn
                            key={`legacy-column-${originalIndex}`}
                            caption={column.caption}
                            images={column.images}
                            level={originalIndex}
                            direction={columnSettings.columnDirection}
                            width={isHorizontal ? undefined : columnSettings.columnWidth}
                            height={isHorizontal ? columnSettings.columnWidth : undefined}
                            onImageClick={onImageClick}
                            {...paginationProps}
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
                {renderColumnView()}
            </Box>
        </Box>
    );
};

export default ColumnBrowser;