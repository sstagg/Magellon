import React from 'react';
import {
    Paper,
    Box,
    ButtonGroup,
    IconButton,
    Tooltip,
    Chip
} from '@mui/material';
import {
    AccountTreeRounded,
    GridOnRounded,
    ViewColumn
} from '@mui/icons-material';
import { ViewMode } from '../store/imageViewerStore';

interface ViewModeSelectorProps {
    viewMode: ViewMode;
    onViewModeChange: (mode: ViewMode) => void;
}

export const ViewModeSelector: React.FC<ViewModeSelectorProps> = ({
    viewMode,
    onViewModeChange
}) => {
    const getViewModeLabel = () => {
        switch (viewMode) {
            case 'grid':
                return 'Columns';
            case 'tree':
                return 'Tree';
            case 'flat':
                return 'Flat';
            default:
                return viewMode;
        }
    };

    return (
        <Paper elevation={0} variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <ButtonGroup size="small">
                    <Tooltip title="Column View">
                        <IconButton
                            onClick={() => onViewModeChange('grid')}
                            color={viewMode === 'grid' ? 'primary' : 'default'}
                        >
                            <ViewColumn />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Tree View">
                        <IconButton
                            onClick={() => onViewModeChange('tree')}
                            color={viewMode === 'tree' ? 'primary' : 'default'}
                        >
                            <AccountTreeRounded />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Flat View">
                        <IconButton
                            onClick={() => onViewModeChange('flat')}
                            color={viewMode === 'flat' ? 'primary' : 'default'}
                        >
                            <GridOnRounded />
                        </IconButton>
                    </Tooltip>
                </ButtonGroup>

                <Chip
                    label={getViewModeLabel()}
                    size="small"
                    color="primary"
                    variant="outlined"
                />
            </Box>
        </Paper>
    );
};
