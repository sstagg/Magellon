import React from 'react';
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
import { Clock, Cpu } from 'lucide-react';

interface Job {
    id: string;
    name: string;
    type: string;
    status: 'running' | 'completed' | 'failed' | 'queued';
    progress?: number;
    startedAt?: string;
    duration?: string;
}

const MOCK_JOBS: Job[] = [
    { id: '1', name: 'CTF Estimation', type: 'ctf', status: 'running', progress: 65, startedAt: '2 min ago' },
    { id: '2', name: 'Motion Correction', type: 'motioncor', status: 'completed', duration: '1m 23s' },
    { id: '3', name: 'Particle Picking', type: 'picking', status: 'queued' },
    { id: '4', name: 'CTF Estimation', type: 'ctf', status: 'failed', duration: '0m 12s' },
];

const statusConfig = {
    running: { icon: <PlayArrow sx={{ fontSize: 14 }} />, color: 'info', label: 'Running' },
    completed: { icon: <CheckCircle sx={{ fontSize: 14 }} />, color: 'success', label: 'Done' },
    failed: { icon: <ErrorIcon sx={{ fontSize: 14 }} />, color: 'error', label: 'Failed' },
    queued: { icon: <HourglassEmpty sx={{ fontSize: 14 }} />, color: 'default', label: 'Queued' },
} as const;

export const JobsPanel: React.FC = () => {
    const theme = useTheme();

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
                    <Typography variant="caption" fontWeight={600}>Jobs</Typography>
                    <Chip label={MOCK_JOBS.length} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
                </Box>
                <Tooltip title="Refresh">
                    <IconButton size="small" sx={{ p: 0.25 }}>
                        <Refresh sx={{ fontSize: 14 }} />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Job list */}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
                {MOCK_JOBS.map((job) => {
                    const config = statusConfig[job.status];
                    return (
                        <Box
                            key={job.id}
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
                                <Typography variant="caption" fontWeight={500} noWrap display="block">
                                    {job.name}
                                </Typography>
                                {job.status === 'running' && job.progress !== undefined && (
                                    <LinearProgress
                                        variant="determinate"
                                        value={job.progress}
                                        sx={{ height: 3, borderRadius: 1, mt: 0.5 }}
                                    />
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                                {(job.duration || job.startedAt) && (
                                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                                        {job.duration || job.startedAt}
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
