import React from 'react';
import { Box, Typography, Chip, Stack, LinearProgress, Paper } from '@mui/material';
import { useJobStepEvents } from '../../../shared/lib/useJobStepEvents.ts';
import { StepEvent } from '../../../shared/types/StepEvent.ts';

interface Props {
    jobId: string | null | undefined;
}

const TYPE_COLORS: Record<string, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    'magellon.step.started': 'info',
    'magellon.step.progress': 'default',
    'magellon.step.completed': 'success',
    'magellon.step.failed': 'error',
};

function shortType(t: string): string {
    return t.replace('magellon.step.', '');
}

function renderLine(ev: StepEvent): React.ReactNode {
    const data: any = ev.data || {};
    if (ev.type === 'magellon.step.progress' && typeof data.percent === 'number') {
        return (
            <Box sx={{ flex: 1 }}>
                <Typography variant="body2">
                    {data.step} — {data.percent.toFixed(0)}%
                    {data.message ? ` · ${data.message}` : ''}
                </Typography>
                <LinearProgress variant="determinate" value={Math.min(100, data.percent)} />
            </Box>
        );
    }
    if (ev.type === 'magellon.step.failed') {
        return (
            <Typography variant="body2" color="error">
                {data.step} — {data.error}
            </Typography>
        );
    }
    return <Typography variant="body2">{data.step}</Typography>;
}

export const StepEventsPanel: React.FC<Props> = ({ jobId }) => {
    const { events, connected } = useJobStepEvents(jobId);

    if (!jobId) {
        return (
            <Paper sx={{ p: 2 }}>
                <Typography variant="body2" sx={{
                    color: "text.secondary"
                }}>
                    Select a job to see live events.
                </Typography>
            </Paper>
        );
    }

    return (
        <Paper sx={{ p: 2 }} data-testid="step-events-panel">
            <Stack
                direction="row"
                spacing={1}
                sx={{
                    alignItems: "center",
                    mb: 1
                }}>
                <Typography variant="subtitle1">Live events</Typography>
                <Chip
                    size="small"
                    label={connected ? 'connected' : 'disconnected'}
                    color={connected ? 'success' : 'default'}
                />
                <Chip size="small" label={`${events.length} events`} />
            </Stack>
            <Stack spacing={1}>
                {events.length === 0 ? (
                    <Typography variant="body2" sx={{
                        color: "text.secondary"
                    }}>
                        Waiting for events…
                    </Typography>
                ) : (
                    events.map((ev) => (
                        <Stack
                            key={ev.id}
                            direction="row"
                            spacing={1}
                            data-testid={`step-event-${shortType(ev.type)}`}
                            sx={{
                                alignItems: "center"
                            }}
                        >
                            <Chip
                                size="small"
                                label={shortType(ev.type)}
                                color={TYPE_COLORS[ev.type] ?? 'default'}
                            />
                            {renderLine(ev)}
                        </Stack>
                    ))
                )}
            </Stack>
        </Paper>
    );
};
