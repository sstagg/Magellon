import React, { useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Container,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { StepEventsPanel } from '../../app/layouts/PanelLayout/StepEventsPanel.tsx';

interface DispatchResponse {
    job_id: string;
    task_id: string;
    queue_name: string;
    image_path: string;
    target_path: string;
    status: string;
}

/**
 * Dev page: dispatches an FFT task at CoreService's /fft/dispatch
 * endpoint, then subscribes to the resulting job:<uuid> Socket.IO
 * room via the shared useJobStepEvents hook. The FFT plugin emits
 * started → completed (or failed), which stream back into the panel.
 *
 * Intentionally simple — this is a test bed for the messaging stack,
 * not a production feature.
 */
export const FftTestPage: React.FC = () => {
    const [imagePath, setImagePath] = useState('');
    const [targetPath, setTargetPath] = useState('');
    const [dispatch, setDispatch] = useState<DispatchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const handleDispatch = async () => {
        setError(null);
        setBusy(true);
        try {
            const client = getAxiosClient(settings.ConfigData.SERVER_API_URL);
            const payload: Record<string, unknown> = { image_path: imagePath };
            if (targetPath) payload.target_path = targetPath;

            const res = await client.post<DispatchResponse>('/fft/dispatch', payload);
            setDispatch(res.data);
        } catch (e: any) {
            setError(e?.response?.data?.detail || e?.message || 'Dispatch failed');
            setDispatch(null);
        } finally {
            setBusy(false);
        }
    };

    const handleReset = () => {
        setDispatch(null);
        setError(null);
    };

    return (
        <Container maxWidth="md">
            <Box sx={{ my: 4 }}>
                <Typography variant="h4" gutterBottom>
                    FFT plugin test bed
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                    Dispatches an FFT task to <code>fft_tasks_queue</code>, subscribes to
                    the resulting job room, and renders live step events. Use this to
                    exercise the full RMQ → NATS → Socket.IO → UI path without needing
                    a GPU or ctffind.
                </Typography>

                <Paper sx={{ p: 3, mb: 3 }}>
                    <Stack spacing={2}>
                        <TextField
                            label="image_path (absolute path on CoreService host)"
                            value={imagePath}
                            onChange={(e) => setImagePath(e.target.value)}
                            placeholder="/data/gpfs/sample.mrc"
                            fullWidth
                            size="small"
                            disabled={busy || !!dispatch}
                        />
                        <TextField
                            label="target_path (optional — defaults to sibling _FFT.png)"
                            value={targetPath}
                            onChange={(e) => setTargetPath(e.target.value)}
                            placeholder="/data/gpfs/ffts/sample_FFT.png"
                            fullWidth
                            size="small"
                            disabled={busy || !!dispatch}
                        />
                        <Stack direction="row" spacing={1}>
                            <Button
                                variant="contained"
                                onClick={handleDispatch}
                                disabled={busy || !imagePath || !!dispatch}
                            >
                                {busy ? 'Dispatching…' : 'Dispatch FFT'}
                            </Button>
                            {dispatch && (
                                <Button variant="outlined" onClick={handleReset}>
                                    New dispatch
                                </Button>
                            )}
                        </Stack>
                    </Stack>
                </Paper>

                {error && (
                    <Alert severity="error" sx={{ mb: 3 }}>
                        {error}
                    </Alert>
                )}

                {dispatch && (
                    <Paper sx={{ p: 2, mb: 3 }} variant="outlined">
                        <Typography variant="subtitle2" gutterBottom>
                            Dispatched
                        </Typography>
                        <Typography variant="caption" component="pre" sx={{ m: 0 }}>
                            {JSON.stringify(dispatch, null, 2)}
                        </Typography>
                    </Paper>
                )}

                <StepEventsPanel jobId={dispatch?.job_id ?? null} />
            </Box>
        </Container>
    );
};

export default FftTestPage;
