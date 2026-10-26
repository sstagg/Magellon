import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { Box, Chip, CircularProgress, IconButton, Tooltip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import CloseIcon from '@mui/icons-material/Close';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useImportJobProgress } from '../lib/useImportJobProgress.ts';
import { ImportProgressDialog } from './ImportProgressDialog.tsx';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const DISCOVER_EVERY_MS = 10_000;
const MAX_CHIPS = 3;

const shortTime = (ms: number) => {
    const minutes = Math.round(ms / 60000);
    if (minutes < 1) return '<1 min';
    if (minutes < 60) return `${minutes} min`;
    return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
};

/** One import's chip; it follows that import until the user dismisses it. */
const ImportChip = ({ jobId, onDismiss }: { jobId: string; onDismiss: () => void }) => {
    // "" disables the hook's own resume-on-mount: this chip names its job.
    const progress = useImportJobProgress('');
    const [open, setOpen] = useState(false);

    useEffect(() => {
        progress.start(jobId);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [jobId]);

    const { summary, status } = progress;
    // "EPU Import: epudata1" → "epudata1"
    const name = summary?.name?.replace(/^.*Import:\s*/i, '') || progress.sessionName || 'Import';
    const queuePosition = summary?.derived_status === 'queued' ? summary.queue_position ?? null : null;
    const pct = summary && summary.total_tasks > 0
        ? Math.round((summary.terminal_tasks / summary.total_tasks) * 100)
        : null;

    let label: string;
    let icon: ReactElement;
    let color: 'default' | 'success' | 'warning' | 'error' = 'default';
    const problemCount = summary?.problems?.reduce((n, p) => n + p.count, 0) ?? 0;
    if (status === 'success' && problemCount > 0) {
        label = `Imported ${name} · ${problemCount} ${problemCount === 1 ? 'problem' : 'problems'}`;
        icon = <WarningIcon fontSize="small" />;
        color = 'warning';
    } else if (status === 'success') {
        label = `Imported ${name}`;
        icon = <CheckCircleIcon fontSize="small" />;
        color = 'success';
    } else if (status === 'error' && summary?.derived_status === 'cancelled') {
        label = `Stopped: ${name}`;
        icon = <ErrorIcon fontSize="small" />;
    } else if (status === 'error') {
        label = `Import failed: ${name}`;
        icon = <ErrorIcon fontSize="small" />;
        color = 'error';
    } else if (queuePosition !== null) {
        label = `${name} · queued #${queuePosition}`;
        icon = <CircularProgress size={14} color="inherit" />;
    } else if (summary && summary.total_tasks === 0) {
        // Running, but still reading the session before creating its tasks.
        label = `${name} · preparing`;
        icon = <CircularProgress size={14} color="inherit" />;
    } else {
        const eta = progress.etaMs !== null ? ` · ${shortTime(progress.etaMs)} left` : '';
        label = `${name}${pct !== null ? ` · ${pct}%` : ''}${eta}`;
        icon = <CircularProgress size={14} color="inherit" variant={pct !== null ? 'determinate' : 'indeterminate'} value={pct ?? undefined} />;
    }

    const finished = status === 'success' || status === 'error';

    return (
        <Box sx={{ display: 'flex', alignItems: 'center', mr: 1 }}>
            <Tooltip title="Import progress: click for details">
                <Chip
                    icon={icon}
                    label={label}
                    color={color}
                    variant={finished ? 'filled' : 'outlined'}
                    size="small"
                    onClick={() => setOpen(true)}
                    sx={{
                        color: finished ? undefined : 'inherit',
                        borderColor: 'rgba(255,255,255,0.4)',
                        maxWidth: 260,
                        '& .MuiChip-icon': { color: 'inherit' },
                    }}
                />
            </Tooltip>
            {finished && (
                <Tooltip title="Dismiss">
                    <IconButton size="small" color="inherit" onClick={() => { setOpen(false); onDismiss(); }}>
                        <CloseIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Tooltip>
            )}
            <ImportProgressDialog
                open={open}
                onClose={() => setOpen(false)}
                status={status}
                error={progress.error}
                jobId={progress.jobId}
                summary={summary}
                stepCounts={progress.stepCounts}
                stepTotals={progress.stepTotals}
                elapsedMs={progress.elapsedMs}
                etaMs={progress.etaMs}
                onCancelQueued={progress.cancelQueued}
                onStop={progress.stop}
                stopping={progress.stopping}
                connectionIssue={progress.connectionIssue}
                sessionName={progress.sessionName}
                titleFallback="Import"
            />
        </Box>
    );
};

type ActiveJobs = { job_id: string; jobs?: { job_id: string }[] };

/**
 * Top-bar chips for the user's imports, on every page — one per import.
 * Imports run in the background (the progress window can be closed); this
 * keeps their live progress in view and reopens the full window on click.
 * It finds the user's imports itself (/export/jobs/active), so it also picks
 * up imports started on another page or before a reload. A finished import's
 * chip stays until dismissed.
 */
export const ActiveImportIndicator = () => {
    const [jobIds, setJobIds] = useState<string[]>([]);

    useEffect(() => {
        let cancelled = false;
        const discover = () => {
            apiClient.get<ActiveJobs>('/export/jobs/active')
                .then(({ data }) => {
                    if (cancelled || !data?.job_id) return;
                    // Oldest first, so chips keep their places as new ones arrive.
                    const active = (data.jobs?.map((j) => j.job_id) ?? [data.job_id]).reverse();
                    setJobIds((known) => {
                        const added = active.filter((id) => !known.includes(id));
                        return added.length ? [...known, ...added] : known;
                    });
                })
                .catch(() => { /* 404 = no active import */ });
        };
        discover();
        const timer = window.setInterval(discover, DISCOVER_EVERY_MS);
        return () => { cancelled = true; window.clearInterval(timer); };
    }, []);

    if (jobIds.length === 0) return null;

    const hidden = jobIds.length - MAX_CHIPS;
    return (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {jobIds.slice(0, MAX_CHIPS).map((id) => (
                <ImportChip key={id} jobId={id} onDismiss={() => setJobIds((ids) => ids.filter((x) => x !== id))} />
            ))}
            {hidden > 0 && (
                <Tooltip title="More imports: see the Jobs panel">
                    <Chip label={`+${hidden} more`} size="small" variant="outlined"
                          sx={{ color: 'inherit', borderColor: 'rgba(255,255,255,0.4)', mr: 1 }} />
                </Tooltip>
            )}
        </Box>
    );
};

export default ActiveImportIndicator;
