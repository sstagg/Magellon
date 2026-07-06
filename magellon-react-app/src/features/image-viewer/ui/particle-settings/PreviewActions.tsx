import React from 'react';
import { Box, Button, CircularProgress, Typography } from '@mui/material';
import {
    PlayArrow as RunIcon,
    Check as AcceptIcon,
    Close as DiscardIcon,
    Tune as TuneIcon,
} from '@mui/icons-material';

interface PreviewActionsProps {
    previewCount: number;
    retuning: boolean;
    onDiscard: () => void;
    onRun: () => void;
    onAccept: () => void;
}

/** PREVIEW-state toolbar: pick count + discard/run/accept actions. */
export const PreviewActions: React.FC<PreviewActionsProps> = ({
    previewCount,
    retuning,
    onDiscard,
    onRun,
    onAccept,
}) => (
    <>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <TuneIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
            <Typography variant="caption"><strong>{previewCount}</strong> particles</Typography>
            {retuning && <CircularProgress size={12} />}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Button variant="outlined" size="small" color="error" startIcon={<DiscardIcon sx={{ fontSize: 12 }} />}
                onClick={onDiscard} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                Discard
            </Button>
            <Button variant="outlined" size="small" startIcon={<RunIcon sx={{ fontSize: 12 }} />}
                onClick={onRun} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                Run
            </Button>
            <Button variant="contained" size="small" startIcon={<AcceptIcon sx={{ fontSize: 12 }} />}
                onClick={onAccept} sx={{ textTransform: 'none', fontSize: '0.7rem', py: 0.25, flex: 1 }}>
                Accept
            </Button>
        </Box>
    </>
);
