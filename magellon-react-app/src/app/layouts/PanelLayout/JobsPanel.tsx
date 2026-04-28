import React, { useEffect } from 'react';
import {
    Box,
    Typography,
    Chip,
    LinearProgress,
    IconButton,
    Tooltip,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Refresh,
    CheckCircle,
    Error as ErrorIcon,
    HourglassEmpty,
    PlayArrow,
} from '@mui/icons-material';
import { Cpu } from 'lucide-react';
import { useJobStore, Job } from './useJobStore.ts';
import { settings } from '../../../shared/config/settings.ts';

const statusConfig = {
    running: { icon: <PlayArrow sx={{ fontSize: 14 }} />, color: 'info', label: 'Running' },
    completed: { icon: <CheckCircle sx={{ fontSize: 14 }} />, color: 'success', label: 'Done' },
    failed: { icon: <ErrorIcon sx={{ fontSize: 14 }} />, color: 'error', label: 'Failed' },
    queued: { icon: <HourglassEmpty sx={{ fontSize: 14 }} />, color: 'default', label: 'Queued' },
} as const;

const JOBS_URL = `${settings.ConfigData.SERVER_API_URL}/plugins/jobs`;

async function fetchJobs(): Promise<Job[]> {
    try {
        const res = await fetch(JOBS_URL);
        if (!res.ok) return [];
        return await res.json();
    } catch {
        return [];
    }
}

export const JobsPanel: React.FC = () => {
    const theme = useTheme();
    const jobs = useJobStore((s) => s.jobs);
    const upsertJob = useJobStore((s) => s.upsertJob);

    useEffect(() => {
        fetchJobs().then((list) => list.forEach(upsertJob));
    }, [upsertJob]);

    const handleRefresh = async () => {
        const list = await fetchJobs();
        list.forEach(upsertJob);
    };

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
                                        variant="determinate"
                                        value={job.progress}
                                        sx={{ height: 3, borderRadius: 1, mt: 0.5 }}
                                    />
                                )}
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
                                {job.started_at && (
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: "text.secondary",
                                            fontSize: '0.65rem'
                                        }}>
                                        {new Date(job.started_at).toLocaleTimeString('en-US', { hour12: false })}
                                    </Typography>
                                )}
                                <Chip
                                    label={config.label}
                                    size="small"
                                    color={config.color as any}
                                    variant="outlined"
                                    sx={{ height: 18, fontSize: '0.6rem', '& .MuiChip-label': { px: 0.5 } }}
                                />
                            </Box>
                        </Box>
                    );
                })}
            </Box>
        </Box>
    );
};
