import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Container,
    FormControl,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import { Folder } from 'lucide-react';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { useJobStepEvents } from '../../shared/lib/useJobStepEvents.ts';
import { ImagePickerDialog } from '../../features/plugin-runner/ui/ImagePickerDialog.tsx';
import { DispatchTrace, DispatchedTask } from '../../features/plugin-runner/ui/DispatchTrace.tsx';

type PtolemyMode = 'square' | 'hole';

interface PtolemyDispatchResponse {
    job_id: string;
    task_id: string;
    queue_name: string;
    image_path: string;
    category: string;
    status?: string;
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

const MODE_CONFIG: Record<PtolemyMode, { label: string; route: string; queue: string; blurb: string }> = {
    square: {
        label: 'Square Detection (low-mag)',
        route: '/image/ptolemy/square/dispatch',
        queue: 'square_detection_tasks_queue',
        blurb: 'Ranks squares in a low-mag MRC (2000–5000 Å/px) by pickability score. '
             + 'Each detection carries vertices, center, area, brightness and score.',
    },
    hole: {
        label: 'Hole Detection (med-mag)',
        route: '/image/ptolemy/hole/dispatch',
        queue: 'hole_detection_tasks_queue',
        blurb: 'Ranks holes in a med-mag MRC (100–1000 Å/px) by pickability score. '
             + 'Each detection carries vertices, center, area and score (no brightness).',
    },
};

export const PtolemyTestPage: React.FC = () => {
    const [mode, setMode] = useState<PtolemyMode>('square');
    const [imagePath, setImagePath] = useState('');
    const [pickerOpen, setPickerOpen] = useState(false);
    const [lastPickedDir, setLastPickedDir] = useState<string | undefined>(undefined);

    const [dispatch, setDispatch] = useState<{
        job_id: string;
        queue_name: string;
        task: DispatchedTask;
        category: string;
    } | null>(null);
    const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [cancelling, setCancelling] = useState(false);

    const pollRef = useRef<number | null>(null);
    const client = getAxiosClient(settings.ConfigData.SERVER_API_URL);
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

    const handleDispatch = async () => {
        setError(null);
        setBusy(true);
        try {
            const cfg = MODE_CONFIG[mode];
            const res = await client.post<PtolemyDispatchResponse>(cfg.route, {
                image_path: imagePath,
            });
            setDispatch({
                job_id: res.data.job_id,
                queue_name: res.data.queue_name,
                category: res.data.category,
                task: {
                    task_id: res.data.task_id,
                    label: res.data.image_path.split(/[/\\]/).pop() ?? res.data.image_path,
                    subtitle: `category: ${res.data.category}`,
                    queueName: res.data.queue_name,
                },
            });
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

    const terminal = jobStatus && ['completed', 'failed', 'cancelled'].includes(jobStatus.status);

    // If the plugin emitted a "completed" step event, its payload carries a
    // short message like "found N squares"/"found N holes". Surface that
    // inline so the operator gets closure without digging through DB rows.
    const completedMessage = React.useMemo(() => {
        const completed = [...stepEvents].reverse().find(
            (e) => e?.data?.kind === 'completed' || e?.data?.phase === 'completed',
        );
        if (!completed) return null;
        const d: any = completed.data;
        return d.message || d.result_summary || null;
    }, [stepEvents]);

    return (
        <Container maxWidth="md">
            <Box sx={{ my: 4 }}>
                <Typography variant="h4" gutterBottom>
                    Ptolemy plugin test bed
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                    Dispatch a ptolemy square- or hole-detection task against one MRC on
                    the CoreService host, watch live step events stream back over
                    Socket.IO, poll the persisted <code>image_job</code> row, and cancel
                    cooperatively. Detection results land in{' '}
                    <code>image_meta_data</code> via the in-process result consumer; this
                    page verifies dispatch + step-event flow, not the final storage write.
                </Typography>

                <Paper sx={{ p: 3, mb: 3 }}>
                    <Stack spacing={2}>
                        <FormControl size="small" disabled={busy || !!dispatch}>
                            <InputLabel id="ptolemy-mode-label">Mode</InputLabel>
                            <Select
                                labelId="ptolemy-mode-label"
                                label="Mode"
                                value={mode}
                                onChange={(e) => setMode(e.target.value as PtolemyMode)}
                            >
                                <MenuItem value="square">{MODE_CONFIG.square.label}</MenuItem>
                                <MenuItem value="hole">{MODE_CONFIG.hole.label}</MenuItem>
                            </Select>
                        </FormControl>
                        <Typography variant="caption" color="text.secondary">
                            {MODE_CONFIG[mode].blurb}
                        </Typography>

                        <Stack direction="row" spacing={1}>
                            <TextField
                                label="image_path (absolute path on CoreService host)"
                                value={imagePath}
                                onChange={(e) => setImagePath(e.target.value)}
                                placeholder="C:/magellon/gpfs/session/atlas.mrc"
                                fullWidth
                                size="small"
                                disabled={busy || !!dispatch}
                            />
                            <Button
                                variant="outlined"
                                startIcon={<Folder size={16} />}
                                onClick={() => setPickerOpen(true)}
                                disabled={busy || !!dispatch}
                            >
                                Pick
                            </Button>
                        </Stack>

                        <Stack direction="row" spacing={1}>
                            <Button
                                variant="contained"
                                onClick={handleDispatch}
                                disabled={busy || !!dispatch || !imagePath}
                            >
                                {busy ? 'Dispatching…' : `Dispatch ${mode === 'square' ? 'SquareDetection' : 'HoleDetection'}`}
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
                            <Chip size="small" label={dispatch.category} color="primary" />
                            <Chip size="small" label={dispatch.queue_name} />
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

                {completedMessage && (
                    <Alert severity="success" sx={{ mb: 2 }}>
                        {completedMessage}
                    </Alert>
                )}

                {dispatch && (
                    <DispatchTrace tasks={[dispatch.task]} events={stepEvents} />
                )}
            </Box>

            <ImagePickerDialog
                open={pickerOpen}
                onClose={() => setPickerOpen(false)}
                onPick={(path) => {
                    if (typeof path === 'string') setImagePath(path);
                }}
                onPathChange={setLastPickedDir}
                title="Pick an MRC"
                initialPath={lastPickedDir}
                storageKey="ptolemyTestPage:lastPath"
            />
        </Container>
    );
};

export default PtolemyTestPage;
