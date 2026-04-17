import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    Container,
    Divider,
    FormControlLabel,
    IconButton,
    LinearProgress,
    Paper,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import { Folder, X, ChevronDown, ChevronRight } from 'lucide-react';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { useJobStepEvents } from '../../shared/lib/useJobStepEvents.ts';
import type { StepEvent, StepEventType } from '../../shared/types/StepEvent.ts';
import { ImagePickerDialog } from '../../features/plugin-runner/ui/ImagePickerDialog.tsx';

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

interface DispatchedTask {
    task_id: string;
    image_path: string;
    target_path: string;
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
                image_path: res.data.image_path,
                target_path: res.data.target_path,
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
            image_path: batchSelected[i],
            target_path: res.data.target_paths[i],
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

// ---------- DispatchTrace: per-task lifecycle from step events ----------

interface TaskRollup {
    image_path: string;
    target_path: string;
    events: StepEvent[];
    latestType: StepEventType | null;
    startedAt: string | null;
    completedAt: string | null;
    progressPercent: number | null;
    progressMessage: string | null;
    error: string | null;
    outputFiles: string[] | null;
}

const TYPE_TO_TONE: Record<StepEventType, 'info' | 'warning' | 'success' | 'error'> = {
    'magellon.step.started': 'info',
    'magellon.step.progress': 'info',
    'magellon.step.completed': 'success',
    'magellon.step.failed': 'error',
};

const TYPE_LABEL: Record<StepEventType, string> = {
    'magellon.step.started': 'started',
    'magellon.step.progress': 'progress',
    'magellon.step.completed': 'completed',
    'magellon.step.failed': 'failed',
};

const PHASE_RANK: Record<StepEventType, number> = {
    'magellon.step.started': 1,
    'magellon.step.progress': 2,
    'magellon.step.completed': 3,
    'magellon.step.failed': 3,
};

function rollupForTask(task: DispatchedTask, events: StepEvent[]): TaskRollup {
    const mine = events.filter((e) => e.data?.task_id === task.task_id);
    let latest: StepEventType | null = null;
    let started: string | null = null;
    let completed: string | null = null;
    let percent: number | null = null;
    let message: string | null = null;
    let error: string | null = null;
    let outputs: string[] | null = null;

    for (const e of mine) {
        if (latest === null || PHASE_RANK[e.type] >= PHASE_RANK[latest]) {
            latest = e.type;
        }
        if (e.type === 'magellon.step.started' && !started) started = e.time;
        if (e.type === 'magellon.step.completed' || e.type === 'magellon.step.failed') {
            completed = e.time;
        }
        if (e.type === 'magellon.step.progress') {
            const d = e.data as { percent?: number; message?: string | null };
            if (typeof d.percent === 'number') percent = d.percent;
            if (d.message != null) message = d.message;
        }
        if (e.type === 'magellon.step.failed') {
            error = (e.data as { error: string }).error;
        }
        if (e.type === 'magellon.step.completed') {
            const d = e.data as { output_files?: string[] | null };
            outputs = d.output_files ?? null;
        }
    }

    return {
        image_path: task.image_path,
        target_path: task.target_path,
        events: mine,
        latestType: latest,
        startedAt: started,
        completedAt: completed,
        progressPercent: percent,
        progressMessage: message,
        error,
        outputFiles: outputs,
    };
}

function fmtDuration(startISO: string | null, endISO: string | null): string {
    if (!startISO) return '—';
    const start = new Date(startISO).getTime();
    const end = endISO ? new Date(endISO).getTime() : Date.now();
    const ms = Math.max(0, end - start);
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

const TaskRow: React.FC<{ task: DispatchedTask; rollup: TaskRollup }> = ({ task, rollup }) => {
    const [expanded, setExpanded] = useState(false);
    const tone = rollup.latestType ? TYPE_TO_TONE[rollup.latestType] : 'default';
    const label = rollup.latestType ? TYPE_LABEL[rollup.latestType] : 'queued';
    const filename = task.image_path.split(/[/\\]/).pop() ?? task.image_path;
    const inProgress = rollup.latestType === 'magellon.step.started'
        || rollup.latestType === 'magellon.step.progress';

    return (
        <Paper
            variant="outlined"
            sx={{
                p: 1.5,
                mb: 1,
                borderColor: 'divider',
                bgcolor: 'background.paper',
            }}
        >
            <Stack direction="row" alignItems="center" spacing={1}>
                <IconButton size="small" onClick={() => setExpanded((v) => !v)}>
                    {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </IconButton>
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, wordBreak: 'break-all' }}>
                        {filename}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        task {task.task_id.slice(0, 8)}… · {rollup.events.length} event{rollup.events.length === 1 ? '' : 's'}
                        {' · '}{fmtDuration(rollup.startedAt, rollup.completedAt)}
                    </Typography>
                </Box>
                <Chip
                    size="small"
                    label={label}
                    color={tone === 'default' ? undefined : (tone as 'info' | 'success' | 'error' | 'warning')}
                    variant={rollup.latestType ? 'filled' : 'outlined'}
                />
            </Stack>

            {inProgress && rollup.progressPercent != null && (
                <Box sx={{ mt: 1 }}>
                    <LinearProgress variant="determinate" value={rollup.progressPercent} />
                    {rollup.progressMessage && (
                        <Typography variant="caption" color="text.secondary">
                            {rollup.progressPercent.toFixed(0)}% · {rollup.progressMessage}
                        </Typography>
                    )}
                </Box>
            )}

            {rollup.error && (
                <Alert severity="error" sx={{ mt: 1, py: 0.5 }}>{rollup.error}</Alert>
            )}

            <Collapse in={expanded} unmountOnExit>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" color="text.secondary">
                    target: <code>{task.target_path}</code>
                </Typography>
                {rollup.outputFiles && rollup.outputFiles.length > 0 && (
                    <Box sx={{ mt: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">output_files:</Typography>
                        <Box component="pre" sx={{ fontSize: 11, m: 0 }}>
                            {rollup.outputFiles.join('\n')}
                        </Box>
                    </Box>
                )}
                <Box sx={{ mt: 1 }}>
                    {rollup.events.length === 0 ? (
                        <Typography variant="caption" color="text.secondary">
                            No events yet — task is queued in <code>fft_tasks_queue</code>, waiting for the plugin to consume it.
                        </Typography>
                    ) : (
                        rollup.events.map((e) => (
                            <Box
                                key={e.id}
                                sx={{
                                    fontFamily: 'monospace',
                                    fontSize: 11,
                                    py: 0.25,
                                    borderBottom: '1px dashed',
                                    borderColor: 'divider',
                                    '&:last-child': { borderBottom: 'none' },
                                }}
                            >
                                <span style={{ opacity: 0.6 }}>{e.time?.slice(11, 23) ?? '—'}</span>
                                {' '}<strong>{TYPE_LABEL[e.type]}</strong>
                                {' '}<span style={{ opacity: 0.7 }}>{JSON.stringify(e.data)}</span>
                            </Box>
                        ))
                    )}
                </Box>
            </Collapse>
        </Paper>
    );
};

const DispatchTrace: React.FC<{ tasks: DispatchedTask[]; events: StepEvent[] }> = ({ tasks, events }) => {
    const rollups = useMemo(
        () => tasks.map((t) => ({ task: t, rollup: rollupForTask(t, events) })),
        [tasks, events],
    );

    const counts = useMemo(() => {
        const c = { queued: 0, running: 0, completed: 0, failed: 0 };
        for (const r of rollups) {
            const t = r.rollup.latestType;
            if (t == null) c.queued++;
            else if (t === 'magellon.step.completed') c.completed++;
            else if (t === 'magellon.step.failed') c.failed++;
            else c.running++;
        }
        return c;
    }, [rollups]);

    return (
        <Paper sx={{ p: 2 }} variant="outlined">
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>Tasks</Typography>
                <Stack direction="row" spacing={0.5}>
                    {counts.queued > 0 && <Chip size="small" label={`queued ${counts.queued}`} variant="outlined" />}
                    {counts.running > 0 && <Chip size="small" label={`running ${counts.running}`} color="info" />}
                    {counts.completed > 0 && <Chip size="small" label={`done ${counts.completed}`} color="success" />}
                    {counts.failed > 0 && <Chip size="small" label={`failed ${counts.failed}`} color="error" />}
                </Stack>
            </Stack>

            {rollups.map(({ task, rollup }) => (
                <TaskRow key={task.task_id} task={task} rollup={rollup} />
            ))}
        </Paper>
    );
};

export default FftTestPage;
