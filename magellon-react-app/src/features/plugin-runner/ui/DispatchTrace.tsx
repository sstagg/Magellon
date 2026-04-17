/**
 * Per-task lifecycle ledger driven by step events from CoreService.
 *
 * One row per dispatched task. Each row shows the latest status chip
 * (queued → started → progress → completed/failed), a LinearProgress
 * bar driven by ``magellon.step.progress.percent``, error text on
 * failure, and an expandable detail with the raw event stream.
 *
 * This is the **debug/dev flavor** of progress UI — it exposes raw
 * CloudEvents data and is intended for the FFT test page and any
 * future ``/dev/*`` scratch pages. Production plugin pages should
 * prefer the lighter ``ProgressTracker``.
 */
import React, { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Chip,
    Collapse,
    Divider,
    IconButton,
    LinearProgress,
    Paper,
    Stack,
    Typography,
} from '@mui/material';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { StepEvent, StepEventType } from '../../../shared/types/StepEvent.ts';

export interface DispatchedTask {
    task_id: string;
    /** Primary display, e.g. the input filename. */
    label: string;
    /** Optional secondary display, e.g. the output target path. */
    subtitle?: string;
    /** Optional hint shown when no events have arrived yet ("queued in <name>"). */
    queueName?: string;
}

interface TaskRollup {
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

function rollupForTask(taskId: string, events: StepEvent[]): TaskRollup {
    const mine = events.filter((e) => e.data?.task_id === taskId);
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
                        {task.label}
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
                {task.subtitle && (
                    <Typography variant="caption" color="text.secondary">
                        {task.subtitle}
                    </Typography>
                )}
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
                            No events yet — task is queued{task.queueName ? ` in ${task.queueName}` : ''}, waiting for the plugin to consume it.
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

export const DispatchTrace: React.FC<{ tasks: DispatchedTask[]; events: StepEvent[] }> = ({ tasks, events }) => {
    const rollups = useMemo(
        () => tasks.map((t) => ({ task: t, rollup: rollupForTask(t.task_id, events) })),
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

export default DispatchTrace;
