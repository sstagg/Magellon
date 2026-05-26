/**
 * PluginActivityPanel — per-plugin Activity tab content.
 *
 * Two sections:
 *   1. Queue snapshot — depth + consumer count for the plugin's
 *      ``<category>_tasks_queue`` and ``<category>_out_tasks_queue``.
 *      Live via GET /admin/plugins/{id}/activity (4s poll) which
 *      proxies the RabbitMQ Management API server-side. Each queue
 *      links into the management UI for deep inspection.
 *   2. Recent tasks — last N ``image_job_task`` rows scoped to this
 *      plugin (by provenance plugin_id or category stage). Carries
 *      status, image_name, plugin_version, subject for a quick scan.
 *
 * Step-event live tail is left to the Logs tab — the logs already
 * carry the step lines and a second live channel here would just
 * duplicate them with no extra signal.
 */
import React from 'react';
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import { ExternalLink, Inbox, Server } from 'lucide-react';
import {
    usePluginActivity,
    type ActivityQueueStats,
    type ActivityRecentTask,
} from '../api/installerApi.ts';

/** RabbitMQ Management URL builder — same convention as the runner
 *  page header pills, kept local to avoid a cross-feature import. */
const rmqMgmtUrl = (queueName: string): string => {
    const base =
        ((window as any).__MAGELLON_CONFIG__?.RMQ_MGMT_URL as string | undefined) ??
        'http://localhost:15672';
    return `${base.replace(/\/$/, '')}/#/queues/%2F/${encodeURIComponent(queueName)}`;
};

const statusChipColor = (
    status: string,
): 'success' | 'error' | 'warning' | 'default' => {
    if (status === 'completed') return 'success';
    if (status === 'failed' || status === 'cancelled') return 'error';
    if (status === 'running' || status === 'processing') return 'warning';
    return 'default';
};

const QueueRow: React.FC<{ q: ActivityQueueStats }> = ({ q }) => {
    if (!q.available) {
        return (
            <Stack
                direction="row"
                spacing={1.5}
                useFlexGap
                sx={{ alignItems: 'center', py: 0.75, flexWrap: 'wrap' }}
            >
                <Chip
                    size="small"
                    variant="outlined"
                    label={q.direction === 'in' ? 'in' : 'out'}
                    sx={{ fontFamily: 'monospace' }}
                />
                <Typography
                    variant="body2"
                    component="a"
                    href={rmqMgmtUrl(q.name)}
                    target="_blank"
                    rel="noreferrer"
                    sx={{ fontFamily: 'monospace', flex: 1, minWidth: 240 }}
                >
                    {q.name} <ExternalLink size={12} style={{ verticalAlign: 'middle' }} />
                </Typography>
                <Alert severity="warning" sx={{ py: 0, px: 1, flex: 'none' }}>
                    {q.error ?? 'broker unreachable'}
                </Alert>
            </Stack>
        );
    }
    return (
        <Stack
            direction="row"
            spacing={1.5}
            useFlexGap
            sx={{ alignItems: 'center', py: 0.75, flexWrap: 'wrap' }}
        >
            <Chip
                size="small"
                variant="outlined"
                label={q.direction === 'in' ? 'in' : 'out'}
                sx={{ fontFamily: 'monospace' }}
            />
            <Typography
                variant="body2"
                component="a"
                href={rmqMgmtUrl(q.name)}
                target="_blank"
                rel="noreferrer"
                sx={{ fontFamily: 'monospace', flex: 1, minWidth: 240 }}
            >
                {q.name} <ExternalLink size={12} style={{ verticalAlign: 'middle' }} />
            </Typography>
            <Tooltip
                title={
                    q.depth_unacked != null && q.depth_unacked > 0
                        ? `${q.depth_ready ?? q.depth ?? 0} ready · ${q.depth_unacked} unacked`
                        : 'Messages pending dispatch'
                }
            >
                <Chip
                    size="small"
                    color={(q.depth ?? 0) > 0 ? 'warning' : 'default'}
                    variant={(q.depth ?? 0) > 0 ? 'filled' : 'outlined'}
                    label={`${q.depth ?? 0} pending`}
                />
            </Tooltip>
            <Tooltip
                title={
                    (q.consumers ?? 0) === 0
                        ? 'No consumer is attached — dispatched tasks will queue up'
                        : 'Plugin replica count attached to this queue'
                }
            >
                <Chip
                    size="small"
                    color={(q.consumers ?? 0) > 0 ? 'success' : 'error'}
                    variant={(q.consumers ?? 0) > 0 ? 'filled' : 'outlined'}
                    label={`${q.consumers ?? 0} consumer${(q.consumers ?? 0) === 1 ? '' : 's'}`}
                />
            </Tooltip>
        </Stack>
    );
};

const TaskRow: React.FC<{ t: ActivityRecentTask }> = ({ t }) => (
    <TableRow>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>
            <Tooltip title={t.oid}>
                <span>{t.oid.slice(0, 8)}…</span>
            </Tooltip>
        </TableCell>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>
            {t.image_name ?? (t.image_id ? `${t.image_id.slice(0, 8)  }…` : '—')}
        </TableCell>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 11 }}>
            {t.subject_kind && t.subject_kind !== 'image' ? t.subject_kind : '—'}
        </TableCell>
        <TableCell>
            <Chip
                size="small"
                color={statusChipColor(t.status)}
                variant={t.status === 'completed' ? 'filled' : 'outlined'}
                label={t.status}
            />
        </TableCell>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: 'text.secondary' }}>
            {t.plugin_version ?? ''}
        </TableCell>
    </TableRow>
);

interface PluginActivityPanelProps {
    /** Manifest plugin_id — the activity endpoint keys on this. */
    pluginId: string;
}

export const PluginActivityPanel: React.FC<PluginActivityPanelProps> = ({
    pluginId,
}) => {
    const { data, isLoading, isError, error } = usePluginActivity(pluginId, 50);

    if (isLoading && !data) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={20} />
            </Box>
        );
    }
    if (isError && !data) {
        return (
            <Alert severity="warning">
                Could not load activity: {(error as Error)?.message ?? 'unknown error'}
            </Alert>
        );
    }
    if (!data) return null;

    return (
        <Stack spacing={3}>
            <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
                    <Server size={16} />
                    <Typography variant="subtitle2">Queues</Typography>
                    {data.category && (
                        <Chip
                            size="small"
                            variant="outlined"
                            label={data.category}
                            sx={{ fontFamily: 'monospace' }}
                        />
                    )}
                    <Typography
                        variant="caption"
                        sx={{ color: 'text.secondary', ml: 1 }}
                    >
                        live · polled every 4s
                    </Typography>
                </Stack>
                {data.queues.length === 0 ? (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        No queues for this plugin's category.
                    </Typography>
                ) : (
                    <Box
                        sx={{
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: 1,
                            px: 1.5,
                            py: 0.5,
                        }}
                    >
                        {data.queues.map((q) => (
                            <QueueRow key={q.name} q={q} />
                        ))}
                    </Box>
                )}
            </Box>

            <Box>
                <Stack
                    direction="row"
                    spacing={1}
                    sx={{ alignItems: 'center', mb: 1 }}
                >
                    <Inbox size={16} />
                    <Typography variant="subtitle2">
                        Recent tasks ({data.recent_tasks.length})
                    </Typography>
                </Stack>
                {data.recent_tasks.length === 0 ? (
                    <Alert severity="info" sx={{ py: 0.5 }}>
                        No tasks have been dispatched to this plugin yet. Run
                        the plugin from the Workspace tab — completed tasks
                        will appear here.
                    </Alert>
                ) : (
                    <TableContainer
                        sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
                    >
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>task</TableCell>
                                    <TableCell>subject</TableCell>
                                    <TableCell>subject_kind</TableCell>
                                    <TableCell>status</TableCell>
                                    <TableCell>plugin v.</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {data.recent_tasks.map((t) => (
                                    <TaskRow key={t.oid} t={t} />
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </Box>
        </Stack>
    );
};
