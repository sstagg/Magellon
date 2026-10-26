import React, { useEffect, useState } from 'react';
import type { ChipProps } from '@mui/material';
import {
    Box,
    Typography,
    Chip,
    LinearProgress,
    IconButton,
    Tooltip,
    alpha,
    useTheme,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
} from '@mui/material';
import {
    Refresh,
    CheckCircle,
    Error as ErrorIcon,
    HourglassEmpty,
    PlayArrow,
    Stop as StopIcon,
    Delete as DeleteIcon,
} from '@mui/icons-material';
import { Cpu } from 'lucide-react';
import type { Job } from '../../../shared/lib/stores/useJobStore.ts';
import { useJobStore } from '../../../shared/lib/stores/useJobStore.ts';
import { settings } from '../../../shared/config/settings.ts';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { apiErrorMessage } from '../../../shared/api/apiError.ts';
import { useAuth } from '../../../features/auth/model/AuthContext.tsx';
import { notify, updateNotice } from '../../../shared/ui/Notifications.tsx';
import { askDeleteSession, SESSION_DELETED_EVENT } from '../../../features/session-delete/DeleteSessionDialog.tsx';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

const statusConfig = {
    running: { icon: <PlayArrow sx={{ fontSize: 14 }} />, color: 'info', label: 'Running' },
    completed: { icon: <CheckCircle sx={{ fontSize: 14 }} />, color: 'success', label: 'Done' },
    failed: { icon: <ErrorIcon sx={{ fontSize: 14 }} />, color: 'error', label: 'Failed' },
    queued: { icon: <HourglassEmpty sx={{ fontSize: 14 }} />, color: 'default', label: 'Queued' },
} as const;

function timeLeft(seconds: number): string {
    const minutes = Math.round(seconds / 60);
    if (minutes < 1) return '<1 min';
    if (minutes < 60) return `${minutes} min`;
    return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

async function fetchJobs(): Promise<Job[]> {
    try {
        const res = await api.get<Job[]>('/plugins/jobs');
        return res.data;
    } catch {
        return [];
    }
}

export const JobsPanel: React.FC = () => {
    const theme = useTheme();
    const jobs = useJobStore((s) => s.jobs);
    const setJobs = useJobStore((s) => s.setJobs);

    // The server's list is the truth (queued imports start or get cancelled
    // without a push), so reload it while the panel is open.
    useEffect(() => {
        const load = () => fetchJobs().then(setJobs);
        load();
        const timer = window.setInterval(load, 10_000);
        return () => window.clearInterval(timer);
    }, [setJobs]);

    const handleRefresh = async () => {
        setJobs(await fetchJobs());
    };

    // Admins can stop or delete any import here, others only their own (the
    // server enforces the same rule).
    const { capabilities, user } = useAuth();
    const canManage = (job: Job) => /Import:/.test(job.name || '')
        && (capabilities.admin || (capabilities.import_sessions && !!user && job.owner_id === user.id));
    const [stopTarget, setStopTarget] = useState<Job | null>(null);

    const stopImport = async (job: Job) => {
        setStopTarget(null);
        const notice = notify(`Stopping ${job.name}…`, 'info', true);
        try {
            const { data } = await api.post(`/export/job/${job.job_id}/stop`);
            updateNotice(notice, data?.session_deleted
                ? `Stopped ${job.name}; session ${data.session_name} and its files deleted`
                : `Stopped ${job.name}`, 'success');
        } catch (err) {
            updateNotice(notice, `Could not stop ${job.name}: ${apiErrorMessage(err, 'unknown error')}`, 'error');
        }
        setJobs(await fetchJobs());
    };

    // A session deleted here or on the Images page: drop its job rows now.
    useEffect(() => {
        const reload = () => { fetchJobs().then(setJobs); };
        window.addEventListener(SESSION_DELETED_EVENT, reload);
        return () => window.removeEventListener(SESSION_DELETED_EVENT, reload);
    }, [setJobs]);

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 1.5,
                py: 0.5,
                borderBottom: `1px solid ${theme.palette.divider}`,
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Cpu size={14} />
                    <Typography variant="caption" sx={{
                        fontWeight: 600
                    }}>Jobs</Typography>
                    <Chip label={jobs.length} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
                </Box>
                <Tooltip title="Refresh">
                    <IconButton size="small" sx={{ p: 0.25 }} onClick={handleRefresh}>
                        <Refresh sx={{ fontSize: 14 }} />
                    </IconButton>
                </Tooltip>
            </Box>
            {/* Job list */}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
                {jobs.length === 0 && (
                    <Box sx={{ p: 2, textAlign: 'center' }}>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>No jobs yet</Typography>
                    </Box>
                )}
                {jobs.map((job) => {
                    const config = statusConfig[job.status] || statusConfig.queued;
                    return (
                        <Box
                            key={job.job_id}
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                px: 1.5,
                                py: 0.75,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
                                '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.04) },
                                cursor: 'pointer',
                            }}
                        >
                            <Box sx={{ color: `${config.color}.main`, display: 'flex' }}>
                                {config.icon}
                            </Box>
                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                <Typography
                                    variant="caption"
                                    noWrap
                                    sx={{
                                        fontWeight: 500,
                                        display: "block"
                                    }}>
                                    {job.name}
                                </Typography>
                                {job.plugin_id && (
                                    <Typography
                                        variant="caption"
                                        noWrap
                                        sx={{
                                            color: "text.secondary",
                                            display: "block",
                                            fontSize: '0.6rem'
                                        }}>
                                        {job.plugin_id}
                                    </Typography>
                                )}
                                {job.status === 'running' && job.progress !== undefined && (
                                    <LinearProgress
                                        variant={job.preparing ? 'indeterminate' : 'determinate'}
                                        value={job.progress}
                                        sx={{ height: 3, borderRadius: 1, mt: 0.5 }}
                                    />
                                )}
                                {job.status === 'running' && (job.preparing || job.tasks_total) ? (
                                    <Typography
                                        variant="caption"
                                        noWrap
                                        sx={{
                                            color: "text.secondary",
                                            display: "block",
                                            fontSize: '0.6rem'
                                        }}>
                                        {job.preparing
                                            ? 'Preparing: reading the session'
                                            : `${job.tasks_done}/${job.tasks_total} tasks`
                                              + (job.eta_seconds !== undefined ? ` · ~${timeLeft(job.eta_seconds)} left` : '')}
                                    </Typography>
                                ) : null}
                                {job.status === 'completed' && job.num_items !== undefined && job.num_items > 0 && (
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: "text.secondary",
                                            fontSize: '0.6rem'
                                        }}>
                                        {job.num_items} items
                                    </Typography>
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                                {(job.started_at || job.queued_at) && (
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: "text.secondary",
                                            fontSize: '0.65rem'
                                        }}>
                                        {new Date((job.started_at || job.queued_at) as string).toLocaleTimeString('en-US', { hour12: false })}
                                    </Typography>
                                )}
                                {canManage(job) && (job.status === 'running' || job.status === 'queued') && (
                                    <Tooltip title="Stop this import and delete what it created">
                                        <IconButton size="small" sx={{ p: 0.25 }} onClick={() => setStopTarget(job)}>
                                            <StopIcon sx={{ fontSize: 15 }} color="error" />
                                        </IconButton>
                                    </Tooltip>
                                )}
                                {canManage(job) && job.session_name
                                    && ['completed', 'failed', 'cancelled'].includes(job.status) && (
                                    <Tooltip title={`Delete session ${job.session_name}`}>
                                        <IconButton size="small" sx={{ p: 0.25 }} onClick={() => askDeleteSession(job.session_name as string)}>
                                            <DeleteIcon sx={{ fontSize: 15 }} />
                                        </IconButton>
                                    </Tooltip>
                                )}
                                <Chip
                                    label={job.status === 'queued' && job.queue_position ? `Queued #${job.queue_position}` : config.label}
                                    size="small"
                                    color={config.color as ChipProps['color']}
                                    variant="outlined"
                                    sx={{ height: 18, fontSize: '0.6rem', '& .MuiChip-label': { px: 0.5 } }}
                                />
                            </Box>
                        </Box>
                    );
                })}
            </Box>
            <Dialog open={!!stopTarget} onClose={() => setStopTarget(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Stop {stopTarget?.name}?</DialogTitle>
                <DialogContent>
                    <Typography variant="body2">
                        The import stops now. Everything it created so far (its session
                        {stopTarget?.session_name ? ` ${stopTarget.session_name}` : ''}, images and results) is
                        deleted. The original data in research storage is not touched.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setStopTarget(null)}>Keep running</Button>
                    <Button color="error" variant="contained" onClick={() => stopTarget && stopImport(stopTarget)}>
                        Stop and delete
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
