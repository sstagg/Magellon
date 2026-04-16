import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Container,
    Divider,
    FormControlLabel,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { StepEventsPanel } from '../../app/layouts/PanelLayout/StepEventsPanel.tsx';

interface SingleDispatchResponse {
    job_id: string;
    task_id: string;
    queue_name: string;
    image_path: string;
    target_path: string;
    status?: string;
}

interface BatchDispatchResponse {
    job_id: string;
    task_ids: string[];
    queue_name: string;
    target_paths: string[];
}

interface DispatchView {
    job_id: string;
    queue_name: string;
    targets: string[];
    mode: 'single' | 'batch';
}

interface JobStatus {
    job_id: string;
    status: string;
    plugin_id?: string;
    name?: string;
    cancel_requested?: boolean;
    [k: string]: unknown;
}

const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    queued: 'info',
    running: 'info',
    completed: 'success',
    failed: 'error',
    cancelled: 'warning',
};

export const FftTestPage: React.FC = () => {
    const [batchMode, setBatchMode] = useState(false);
    const [imagePath, setImagePath] = useState('');
    const [targetPath, setTargetPath] = useState('');
    const [batchPaths, setBatchPaths] = useState('');

    const [dispatch, setDispatch] = useState<DispatchView | null>(null);
    const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [cancelling, setCancelling] = useState(false);

    const pollRef = useRef<number | null>(null);

    const client = getAxiosClient(settings.ConfigData.SERVER_API_URL);

    useEffect(() => {
        if (!dispatch?.job_id) return;
        const poll = async () => {
            try {
                const r = await client.get<JobStatus>(`/plugins/jobs/${dispatch.job_id}`);
                setJobStatus(r.data);
                if (['completed', 'failed', 'cancelled'].includes(r.data.status)) {
                    if (pollRef.current) {
                        window.clearInterval(pollRef.current);
                        pollRef.current = null;
                    }
                }
            } catch {
                /* keep polling */
            }
        };
        poll();
        pollRef.current = window.setInterval(poll, 2000);
        return () => {
            if (pollRef.current) {
                window.clearInterval(pollRef.current);
                pollRef.current = null;
            }
        };
    }, [dispatch?.job_id]);

    const handleDispatchSingle = async () => {
        const payload: Record<string, unknown> = { image_path: imagePath };
        if (targetPath) payload.target_path = targetPath;
        const res = await client.post<SingleDispatchResponse>('/fft/dispatch', payload);
        setDispatch({
            job_id: res.data.job_id,
            queue_name: res.data.queue_name,
            targets: [res.data.target_path],
            mode: 'single',
        });
    };

    const handleDispatchBatch = async () => {
        const paths = batchPaths
            .split(/\r?\n/)
            .map((p) => p.trim())
            .filter(Boolean);
        if (paths.length === 0) {
            setError('At least one image path is required for batch dispatch.');
            return;
        }
        const res = await client.post<BatchDispatchResponse>('/fft/batch_dispatch', {
            image_paths: paths,
            name: `FFT batch x${paths.length}`,
        });
        setDispatch({
            job_id: res.data.job_id,
            queue_name: res.data.queue_name,
            targets: res.data.target_paths,
            mode: 'batch',
        });
    };

    const handleDispatch = async () => {
        setError(null);
        setBusy(true);
        try {
            if (batchMode) {
                await handleDispatchBatch();
            } else {
                await handleDispatchSingle();
            }
        } catch (e: any) {
            setError(e?.response?.data?.detail || e?.message || 'Dispatch failed');
            setDispatch(null);
        } finally {
            setBusy(false);
        }
    };

    const handleCancel = async () => {
        if (!dispatch?.job_id) return;
        setCancelling(true);
        setError(null);
        try {
            await client.delete(`/plugins/jobs/${dispatch.job_id}`);
        } catch (e: any) {
            setError(e?.response?.data?.detail || e?.message || 'Cancel failed');
        } finally {
            setCancelling(false);
        }
    };

    const handleReset = () => {
        setDispatch(null);
        setJobStatus(null);
        setError(null);
        if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    const terminal =
        jobStatus && ['completed', 'failed', 'cancelled'].includes(jobStatus.status);

    return (
        <Container maxWidth="md">
            <Box sx={{ my: 4 }}>
                <Typography variant="h4" gutterBottom>
                    FFT plugin test bed
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                    Dispatch one or many FFT tasks, watch live step events stream back over
                    Socket.IO, poll the persisted <code>image_job</code> row, and cancel
                    cooperatively. Use this to verify the full RMQ → projector → DB → UI path
                    end to end.
                </Typography>

                <Paper sx={{ p: 3, mb: 3 }}>
                    <Stack spacing={2}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={batchMode}
                                    onChange={(e) => setBatchMode(e.target.checked)}
                                    disabled={busy || !!dispatch}
                                />
                            }
                            label="Batch dispatch (one job, N tasks)"
                        />

                        {!batchMode ? (
                            <>
                                <TextField
                                    label="image_path (absolute path on CoreService host)"
                                    value={imagePath}
                                    onChange={(e) => setImagePath(e.target.value)}
                                    placeholder="C:/magellon/gpfs/session/sample.mrc"
                                    fullWidth
                                    size="small"
                                    disabled={busy || !!dispatch}
                                />
                                <TextField
                                    label="target_path (optional — defaults to sibling _FFT.png)"
                                    value={targetPath}
                                    onChange={(e) => setTargetPath(e.target.value)}
                                    placeholder="C:/magellon/gpfs/session/ffts/sample_FFT.png"
                                    fullWidth
                                    size="small"
                                    disabled={busy || !!dispatch}
                                />
                            </>
                        ) : (
                            <TextField
                                label="image_paths (one absolute path per line)"
                                value={batchPaths}
                                onChange={(e) => setBatchPaths(e.target.value)}
                                placeholder={
                                    'C:/magellon/gpfs/session/sample_01.mrc\n' +
                                    'C:/magellon/gpfs/session/sample_02.mrc'
                                }
                                fullWidth
                                multiline
                                minRows={4}
                                size="small"
                                disabled={busy || !!dispatch}
                            />
                        )}

                        <Stack direction="row" spacing={1}>
                            <Button
                                variant="contained"
                                onClick={handleDispatch}
                                disabled={
                                    busy ||
                                    !!dispatch ||
                                    (batchMode ? !batchPaths.trim() : !imagePath)
                                }
                            >
                                {busy ? 'Dispatching…' : 'Dispatch FFT'}
                            </Button>
                            {dispatch && !terminal && (
                                <Button
                                    color="warning"
                                    variant="outlined"
                                    onClick={handleCancel}
                                    disabled={cancelling}
                                >
                                    {cancelling ? 'Cancelling…' : 'Cancel job'}
                                </Button>
                            )}
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
                        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                            <Typography variant="subtitle2">
                                Job {dispatch.job_id.slice(0, 8)}…
                            </Typography>
                            <Chip size="small" label={dispatch.queue_name} />
                            <Chip size="small" label={`${dispatch.targets.length} task(s)`} />
                            {jobStatus?.status && (
                                <Chip
                                    size="small"
                                    label={`db: ${jobStatus.status}`}
                                    color={STATUS_COLORS[jobStatus.status] ?? 'default'}
                                />
                            )}
                            {jobStatus?.cancel_requested && (
                                <Chip size="small" color="warning" label="cancel requested" />
                            )}
                        </Stack>

                        <Divider sx={{ mb: 1 }} />
                        <Typography variant="caption" color="text.secondary">
                            Expected output file{dispatch.targets.length > 1 ? 's' : ''}:
                        </Typography>
                        <Box component="pre" sx={{ fontSize: 12, m: 0, mt: 0.5 }}>
                            {dispatch.targets.join('\n')}
                        </Box>
                    </Paper>
                )}

                <StepEventsPanel jobId={dispatch?.job_id ?? null} />
            </Box>
        </Container>
    );
};

export default FftTestPage;
