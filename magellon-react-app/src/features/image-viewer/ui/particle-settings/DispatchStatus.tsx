import React from 'react';
import { Box, Chip, LinearProgress, Typography } from '@mui/material';

interface DispatchStatusProps {
    /** 'toolbar' renders the compact header block; 'body' the larger panel block. */
    variant: 'toolbar' | 'body';
    selectedBackend: string;
    dispatchPercent: number | undefined;
    dispatchMessage: string;
    dispatchCompleted: boolean;
    dispatchFailed: boolean;
    socketConnected: boolean;
}

/** DISPATCHED-state progress — task sent to RMQ, polling for result. */
export const DispatchStatus: React.FC<DispatchStatusProps> = ({
    variant,
    selectedBackend,
    dispatchPercent,
    dispatchMessage,
    dispatchCompleted,
    dispatchFailed,
    socketConnected,
}) => {
    if (variant === 'toolbar') {
        return (
            <Box sx={{ mt: 0.5 }}>
                <LinearProgress
                    variant={typeof dispatchPercent === 'number' ? 'determinate' : 'indeterminate'}
                    value={typeof dispatchPercent === 'number' ? dispatchPercent : undefined}
                    color={dispatchFailed ? 'error' : dispatchCompleted ? 'success' : 'primary'}
                    sx={{ height: 4, borderRadius: 1 }}
                />
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        mt: 0.5,
                        display: 'block',
                        fontSize: '0.7rem'
                    }}>
                    {dispatchFailed
                        ? `Failed: ${dispatchMessage}`
                        : dispatchCompleted
                            ? 'Plugin finished - loading saved picks...'
                            : dispatchMessage}
                    {typeof dispatchPercent === 'number' ? ` (${Math.round(dispatchPercent)}%)` : ''}
                </Typography>
                <Chip
                    size="small"
                    variant="outlined"
                    label={socketConnected ? 'socket live' : 'socket connecting'}
                    sx={{ mt: 0.5, height: 18, fontSize: '0.62rem' }}
                />
            </Box>
        );
    }
    return (
        <Box sx={{ py: 3 }}>
            <LinearProgress
                variant={typeof dispatchPercent === 'number' ? 'determinate' : 'indeterminate'}
                value={typeof dispatchPercent === 'number' ? dispatchPercent : undefined}
                color={dispatchFailed ? 'error' : dispatchCompleted ? 'success' : 'primary'}
                sx={{ height: 6, borderRadius: 1 }}
            />
            <Typography
                variant="caption"
                sx={{
                    color: "text.secondary",
                    mt: 1,
                    display: 'block'
                }}>
                <strong>{selectedBackend}</strong><br />
                {dispatchFailed
                    ? `Failed: ${dispatchMessage}`
                    : dispatchCompleted
                        ? 'Plugin finished. Waiting for the saved IPP record to appear.'
                        : dispatchMessage}
                {typeof dispatchPercent === 'number' ? ` (${Math.round(dispatchPercent)}%)` : ''}
            </Typography>
            <Chip
                size="small"
                variant="outlined"
                label={socketConnected ? 'socket live' : 'socket connecting'}
                sx={{ mt: 1, height: 20, fontSize: '0.68rem' }}
            />
        </Box>
    );
};
