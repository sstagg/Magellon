import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import {
    CheckCircle as ValidIcon,
    Check as AcceptIcon,
    Close as DiscardIcon,
} from '@mui/icons-material';

interface ResultsActionsProps {
    count: number;
    onDiscard: () => void;
    onAccept: () => void;
}

/** RESULTS-state toolbar: pick count + discard/accept actions. */
export const ResultsActions: React.FC<ResultsActionsProps> = ({ count, onDiscard, onAccept }) => (
    <>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <ValidIcon sx={{ fontSize: 16, color: 'success.main' }} />
            <Typography variant="caption">
                <strong>{count}</strong> particles picked
            </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon sx={{ fontSize: 12 }} />}
                onClick={onDiscard} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                Discard
            </Button>
            <Button variant="contained" size="small" startIcon={<AcceptIcon sx={{ fontSize: 12 }} />}
                onClick={onAccept} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                Accept
            </Button>
        </Box>
    </>
);
