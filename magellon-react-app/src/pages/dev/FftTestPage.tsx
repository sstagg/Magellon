import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Container,
    FormControlLabel,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import { Folder, X } from 'lucide-react';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { useJobStepEvents } from '../../shared/lib/useJobStepEvents.ts';
import { ImagePickerDialog } from '../../features/plugin-runner/ui/ImagePickerDialog.tsx';
import { DispatchTrace, DispatchedTask } from '../../features/plugin-runner/ui/DispatchTrace.tsx';

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
    tasks: DispatchedTask[];
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
    const [batchSelected, setBatchSelected] = useState<string[]>([]);

    // Picker state
    const [pickerOpen, setPickerOpen] = useState(false);
    const [singlePickerOpen, setSinglePickerOpen] = useState(false);
    const [lastPickedDir, setLastPickedDir] = useState<string | undefined>(undefined);

    const [dispatch, setDispatch] = useState<DispatchView | null>(null);
    const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [cancelling, setCancelling] = useState(false);

    const pollRef = useRef<number | null>(null);

    const client = getAxiosClient(settings.ConfigData.SERVER_API_URL);

    // Live step-event stream — drives the per-task DispatchTrace below.
    // Hook lazily-subscribes when dispatch?.job_id is set, dedupes by ce-id.
    const { events: stepEvents, connected: socketConnected } = useJobStepEvents(dispatch?.job_id ?? null);

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
        const res = await client.post<SingleDispatchResponse>('/image/fft/dispatch', payload);
        setDispatch({
            job_id: res.data.job_id,
            queue_name: res.data.queue_name,
            tasks: [{
                task_id: res.data.task_id,
                label: res.data.image_path.split(/[/\\]/).pop() ?? res.data.image_path,
                subtitle: `target: ${res.data.target_path}`,
                queueName: res.data.queue_name,
            }],
            mode: 'single',
        });
    };

    const handleDispatchBatch = async () => {
        if (batchSelected.length === 0) {
            setError('Pick at least one image to dispatch.');
            return;
        }
        const res = await client.post<BatchDispatchResponse>('/image/fft/batch_dispatch', {
            image_paths: batchSelected,
            name: `FFT batch x${batchSelected.length}`,
        });
        const tasks: DispatchedTask[] = res.data.task_ids.map((tid, i) => ({
            task_id: tid,
            label: batchSelected[i].split(/[/\\]/).pop() ?? batchSelected[i],
            subtitle: `target: ${res.data.target_paths[i]}`,
            queueName: res.data.queue_name,
        }));
        setDispatch({
            job_id: res.data.job_id,
            queue_name: res.data.queue_name,
            tasks,
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
        setBatchSelected([]);
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
                                <Stack direction="row" spacing={1}>
                                    <TextField
                                        label="image_path (absolute path on CoreService host)"
                                        value={imagePath}
                                        onChange={(e) => setImagePath(e.target.value)}
                                        placeholder="C:/magellon/gpfs/session/sample.mrc"
                                        fullWidth
                                        size="small"
                                        disabled={busy || !!dispatch}
                                    />
                                    <Button
                                        variant="outlined"
                                        startIcon={<Folder size={16} />}
                                        onClick={() => setSinglePickerOpen(true)}
                                        disabled={busy || !!dispatch}
                                    >
                                        Pick
                                    </Button>
                                </Stack>
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
                            <Stack spacing={1}>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    <Button
                                        variant="outlined"
                                        startIcon={<Folder size={16} />}
                                        onClick={() => setPickerOpen(true)}
                                        disabled={busy || !!dispatch}
                                    >
                                        Pick images
                                    </Button>
                                    <Typography variant="body2" color="text.secondary">
                                        {batchSelected.length === 0
                                            ? 'No images selected.'
                                            : `${batchSelected.length} image${batchSelected.length === 1 ? '' : 's'} selected.`}
                                    </Typography>
                                    {batchSelected.length > 0 && !dispatch && (
                                        <Button
                                            size="small"
                                            onClick={() => setBatchSelected([])}
                                            disabled={busy}
                                        >
                                            Clear
                                        </Button>
                                    )}
                                </Stack>
                                {batchSelected.length > 0 && (
                                    <Paper
                                        variant="outlined"
                                        sx={{
                                            maxHeight: 180,
                                            overflow: 'auto',
                                            p: 1,
                                            display: 'flex',
                                            flexWrap: 'wrap',
                                            gap: 0.5,
                                        }}
                                    >
                                        {batchSelected.map((p) => (
                                            <Chip
                                                key={p}
                                                size="small"
                                                label={p.split(/[/\\]/).pop()}
                                                title={p}
                                                onDelete={dispatch ? undefined : () =>
                                                    setBatchSelected((prev) => prev.filter((x) => x !== p))}
                                                deleteIcon={<X size={14} />}
                                            />
                                        ))}
                                    </Paper>
                                )}
                            </Stack>
                        )}

                        <Stack direction="row" spacing={1}>
                            <Button
                                variant="contained"
                                onClick={handleDispatch}
                                disabled={
                                    busy ||
                                    !!dispatch ||
                                    (batchMode ? batchSelected.length === 0 : !imagePath)
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
                    <Paper sx={{ p: 2, mb: 2 }} variant="outlined">
                        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
                            <Typography variant="subtitle2">
                                Job {dispatch.job_id.slice(0, 8)}…
                            </Typography>
                            <Chip size="small" label={dispatch.queue_name} />
                            <Chip size="small" label={`${dispatch.tasks.length} task(s)`} />
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
                            <Chip
                                size="small"
                                label={socketConnected ? 'socket: live' : 'socket: offline'}
                                color={socketConnected ? 'success' : 'default'}
                                variant="outlined"
                            />
                        </Stack>
                    </Paper>
                )}

                {dispatch && (
                    <DispatchTrace tasks={dispatch.tasks} events={stepEvents} />
                )}
            </Box>

            <ImagePickerDialog
                open={pickerOpen}
                onClose={() => setPickerOpen(false)}
                multiple
                onPick={(paths) => setBatchSelected(paths)}
                onPathChange={setLastPickedDir}
                title="Pick images for batch FFT"
                initialPath={lastPickedDir}
                storageKey="fftTestPage:lastPath"
            />

            <ImagePickerDialog
                open={singlePickerOpen}
                onClose={() => setSinglePickerOpen(false)}
                onPick={(path) => setImagePath(path)}
                onPathChange={setLastPickedDir}
                title="Pick an image"
                initialPath={lastPickedDir}
                storageKey="fftTestPage:lastPath"
            />
        </Container>
    );
};

export default FftTestPage;
