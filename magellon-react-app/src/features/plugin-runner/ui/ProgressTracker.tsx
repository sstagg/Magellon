/**
 * Lightweight per-job step-event progress UI for production plugin pages.
 *
 * Mounts under :class:`RunStatusBanner` and adds the bits the banner
 * can't get from polling: live step-name + percent + message from the
 * Socket.IO ``step_event`` stream, and a clear error message on failure.
 * Stays silent until events arrive so it doesn't duplicate the banner's
 * "queued" indicator.
 *
 * For the verbose, debug-flavored version (per-task ledger, raw event
 * JSON, expandable detail rows) see :file:`./DispatchTrace.tsx` —
 * intended for ``/dev/*`` test pages, not end-user surfaces.
 */
import React, { useMemo } from 'react';
import { Alert, Box, LinearProgress, Stack, Typography } from '@mui/material';
import { useJobStepEvents } from '../../../shared/lib/useJobStepEvents.ts';
import type { StepEvent, StepEventType } from '../../../shared/types/StepEvent.ts';

interface JobRollup {
    latestType: StepEventType | null;
    latestStep: string | null;
    progressPercent: number | null;
    progressMessage: string | null;
    error: string | null;
    eventCount: number;
}

const PHASE_RANK: Record<StepEventType, number> = {
    'magellon.step.started': 1,
    'magellon.step.progress': 2,
    'magellon.step.completed': 3,
    'magellon.step.failed': 3,
};

function rollupJob(events: StepEvent[]): JobRollup {
    let latest: StepEventType | null = null;
    let latestStep: string | null = null;
    let percent: number | null = null;
    let message: string | null = null;
    let error: string | null = null;

    for (const e of events) {
        if (latest === null || PHASE_RANK[e.type] >= PHASE_RANK[latest]) {
            latest = e.type;
            latestStep = e.data?.step ?? latestStep;
        }
        if (e.type === 'magellon.step.progress') {
            const d = e.data as { percent?: number; message?: string | null };
            if (typeof d.percent === 'number') percent = d.percent;
            if (d.message != null) message = d.message;
        }
        if (e.type === 'magellon.step.failed') {
            error = (e.data as { error: string }).error;
        }
    }
    return { latestType: latest, latestStep, progressPercent: percent, progressMessage: message, error, eventCount: events.length };
}

export const ProgressTracker: React.FC<{ jobId: string | null | undefined }> = ({ jobId }) => {
    const { events } = useJobStepEvents(jobId ?? null);
    const rollup = useMemo(() => rollupJob(events), [events]);

    // Stay silent until the first event lands — RunStatusBanner already
    // shows "queued"; we don't duplicate it.
    if (!jobId || rollup.eventCount === 0) return null;

    if (rollup.error) {
        return (
            <Alert severity="error" sx={{ mt: 1 }}>
                Step <strong>{rollup.latestStep ?? '—'}</strong> failed: {rollup.error}
            </Alert>
        );
    }

    const inProgress = rollup.latestType === 'magellon.step.started'
        || rollup.latestType === 'magellon.step.progress';

    if (!inProgress) {
        // Completed — let RunStatusBanner own the success display.
        return null;
    }

    return (
        <Box sx={{ mt: 1 }}>
            <Stack
                direction="row"
                sx={{
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 0.5
                }}>
                <Typography variant="caption" sx={{
                    color: "text.secondary"
                }}>
                    Step <strong>{rollup.latestStep ?? '—'}</strong>
                    {rollup.progressMessage ? ` · ${rollup.progressMessage}` : ''}
                </Typography>
                {rollup.progressPercent != null && (
                    <Typography variant="caption" sx={{
                        color: "text.secondary"
                    }}>
                        {rollup.progressPercent.toFixed(0)}%
                    </Typography>
                )}
            </Stack>
            <LinearProgress
                variant={rollup.progressPercent != null ? 'determinate' : 'indeterminate'}
                value={rollup.progressPercent ?? undefined}
            />
        </Box>
    );
};

export default ProgressTracker;
