import React from 'react';
import { Alert, Box, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import type { ChipProps } from '@mui/material';

interface RunStatusBannerProps {
    job: {
        job_id?: string;
        status: string;
        progress?: number;
        error?: string;
        started_at?: string;
        finished_at?: string;
        result?: { num_particles?: number };
    };
}

/** Status chip + elapsed-time ticker + progress bar for the current job. */
export const RunStatusBanner: React.FC<RunStatusBannerProps> = ({ job }) => {
    const statusColor =
        job.status === 'completed' ? 'success' :
        job.status === 'failed' ? 'error' :
        job.status === 'cancelled' ? 'warning' :
        job.status === 'running' ? 'info' :
        job.status === 'queued' ? 'warning' : 'default';

    const startedAt = job.started_at ? new Date(job.started_at).getTime() : null;
    const finishedAt = job.finished_at ? new Date(job.finished_at).getTime() : null;
    const [now, setNow] = React.useState(() => Date.now());
    const active = job.status === 'running' || job.status === 'queued';

    React.useEffect(() => {
        if (!active) return;
        const id = setInterval(() => setNow(Date.now()), 500);
        return () => clearInterval(id);
    }, [active]);

    const elapsedMs = startedAt
        ? (finishedAt ?? now) - startedAt
        : null;

    const particles = job.result?.num_particles;

    return (
        <Box
            sx={{
                mb: 2,
                p: 1.25,
                borderRadius: 1,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: (t) => t.palette.mode === 'dark' ? 'background.paper' : 'grey.50',
            }}
        >
            <Stack
                direction="row"
                spacing={1}
                sx={{
                    alignItems: "center",
                    mb: active ? 1 : 0,
                    flexWrap: 'wrap',
                    rowGap: 0.5
                }}>
                <Chip size="small" color={statusColor as ChipProps['color']} label={job.status} sx={{ textTransform: 'capitalize' }} />
                {elapsedMs != null && (
                    <Typography
                        variant="caption"
                        sx={{
                            color: "text.secondary",
                            fontVariantNumeric: 'tabular-nums'
                        }}>
                        {formatDuration(elapsedMs)}
                    </Typography>
                )}
                {job.status === 'completed' && typeof particles === 'number' && (
                    <Chip size="small" variant="outlined" color="success" label={`${particles} particle${particles === 1 ? '' : 's'}`} />
                )}
                <Box sx={{ flex: 1 }} />
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        fontFamily: 'monospace'
                    }}>
                    {String(job.job_id).slice(0, 8)}
                </Typography>
            </Stack>
            {active && (
                <LinearProgress
                    variant={typeof job.progress === 'number' ? 'determinate' : 'indeterminate'}
                    value={job.progress ?? 0}
                    sx={{ height: 4, borderRadius: 1 }}
                />
            )}
            {job.status === 'failed' && job.error && (
                <Alert severity="error" sx={{ mt: 1 }}>{job.error}</Alert>
            )}
        </Box>
    );
};

function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms} ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = Math.round(s - m * 60);
    return `${m}m ${rem}s`;
}
