import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Container,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Divider,
    Drawer,
    FormControlLabel,
    IconButton,
    Link as MuiLink,
    Paper,
    Snackbar,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import { RefreshCw, ExternalLink, Activity, AlertTriangle, CheckCircle2, XCircle, Eye, Trash2, X, Copy, Check } from 'lucide-react';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';

// ---------- Types: shape returned by GET /admin/broker/health ----------

interface QueueTile {
    name: string | null;
    exists: boolean;
    depth: number;
    consumers: number;
    publish_rate: number;
    deliver_rate: number;
}

interface PipelineEntry {
    name: string;
    task_queue: QueueTile;
    result_queue: QueueTile;
}

interface PluginEntry {
    plugin_id: string;
    plugin_version: string;
    category: string;
    instance_id: string;
    status: string;
    last_heartbeat: string | null;
    last_heartbeat_age_seconds: number | null;
    manifest: unknown;
}

interface BrokerBlock {
    host: string;
    management_port: number;
    reachable: boolean;
    error: string | null;
}

interface BrokerHealth {
    as_of: string;
    broker: BrokerBlock;
    pipelines: PipelineEntry[];
    infrastructure: QueueTile[];
    plugins: PluginEntry[];
}

interface PeekedMessage {
    routing_key: string | null;
    exchange: string | null;
    redelivered: boolean;
    ce_id: string | null;
    ce_type: string | null;
    ce_subject: string | null;
    ce_source: string | null;
    ce_time: string | null;
    headers: Record<string, unknown>;
    payload: unknown;
}

interface PeekResponse {
    queue: string;
    as_of: string;
    count: number;
    messages: PeekedMessage[];
    error: string | null;
}

const POLL_INTERVAL_MS = 5_000;
const API_BASE = (settings.ConfigData as { SERVER_API_URL: string }).SERVER_API_URL;

// ---------- Helpers ----------

function formatRate(r: number): string {
    if (r === 0) return '0';
    if (r < 0.1) return r.toFixed(2);
    return r.toFixed(1);
}

function formatAge(seconds: number | null): string {
    if (seconds == null) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
}

// One question per page: "is my pipeline healthy?". The status mapping
// below is the dial — if it's wrong, the page is wrong. Keep narrow.
function pipelineStatus(p: PipelineEntry): { tone: 'ok' | 'warn' | 'bad'; label: string } {
    if (!p.task_queue.exists) return { tone: 'warn', label: 'queue not declared' };
    if (p.task_queue.consumers === 0) return { tone: 'bad', label: 'no consumers' };
    if (p.task_queue.depth > 100) return { tone: 'warn', label: `backlog ${p.task_queue.depth}` };
    return { tone: 'ok', label: 'healthy' };
}

function pluginStaleness(p: PluginEntry): { tone: 'ok' | 'warn' | 'bad'; label: string } {
    const age = p.last_heartbeat_age_seconds;
    if (age == null) return { tone: 'bad', label: 'no heartbeat' };
    if (age > 30) return { tone: 'warn', label: `${formatAge(age)} ago` };
    return { tone: 'ok', label: `${formatAge(age)} ago` };
}

// ---------- Sub-components ----------

const StatusChip: React.FC<{ tone: 'ok' | 'warn' | 'bad'; label: string }> = ({ tone, label }) => {
    const palette = {
        ok: { bg: '#1b3b1f', fg: '#7ee787', icon: <CheckCircle2 size={14} /> },
        warn: { bg: '#3b2f1b', fg: '#f5c451', icon: <AlertTriangle size={14} /> },
        bad: { bg: '#3b1b1b', fg: '#f87171', icon: <XCircle size={14} /> },
    }[tone];
    return (
        <Chip
            size="small"
            icon={palette.icon}
            label={label}
            sx={{
                bgcolor: palette.bg,
                color: palette.fg,
                fontWeight: 600,
                '& .MuiChip-icon': { color: palette.fg },
            }}
        />
    );
};

interface QueueActions {
    onBrowse: (name: string) => void;
    onPurge: (name: string) => void;
}

const QueueActionButtons: React.FC<QueueActions & { name: string | null; depth: number }> =
    ({ name, depth, onBrowse, onPurge }) => {
        if (!name) return null;
        return (
            <Stack direction="row" spacing={0.5}>
                <Tooltip title="Peek messages (auto-requeue)">
                    <IconButton size="small" onClick={() => onBrowse(name)} sx={{ color: 'rgba(255,255,255,0.6)' }}>
                        <Eye size={16} />
                    </IconButton>
                </Tooltip>
                <Tooltip title="Purge queue (irreversible)">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => onPurge(name)}
                            disabled={depth === 0}
                            sx={{ color: depth > 0 ? '#f87171' : 'rgba(255,255,255,0.3)' }}
                        >
                            <Trash2 size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>
        );
    };

const PipelineCard: React.FC<{ p: PipelineEntry } & QueueActions> = ({ p, onBrowse, onPurge }) => {
    const status = pipelineStatus(p);
    return (
        <Card
            variant="outlined"
            sx={{
                bgcolor: '#0d1117',
                borderColor: 'rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.85)',
                height: '100%',
            }}
        >
            <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>{p.name}</Typography>
                    <StatusChip tone={status.tone} label={status.label} />
                </Stack>

                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                        Task queue · {p.task_queue.name ?? '—'}
                    </Typography>
                    <QueueActionButtons name={p.task_queue.name} depth={p.task_queue.depth} onBrowse={onBrowse} onPurge={onPurge} />
                </Stack>
                <Stack direction="row" spacing={3} mt={0.5} mb={2}>
                    <Stat label="Depth" value={p.task_queue.depth} accent={p.task_queue.depth > 0} />
                    <Stat label="Consumers" value={p.task_queue.consumers} accent={p.task_queue.consumers === 0} bad />
                    <Stat label="In/s" value={formatRate(p.task_queue.publish_rate)} />
                    <Stat label="Out/s" value={formatRate(p.task_queue.deliver_rate)} />
                </Stack>

                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.08)', mb: 1.5 }} />

                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                        Result queue · {p.result_queue.name ?? '—'}
                    </Typography>
                    <QueueActionButtons name={p.result_queue.name} depth={p.result_queue.depth} onBrowse={onBrowse} onPurge={onPurge} />
                </Stack>
                <Stack direction="row" spacing={3} mt={0.5}>
                    <Stat label="Depth" value={p.result_queue.depth} accent={p.result_queue.depth > 0} />
                    <Stat label="Consumers" value={p.result_queue.consumers} />
                    <Stat label="In/s" value={formatRate(p.result_queue.publish_rate)} />
                    <Stat label="Out/s" value={formatRate(p.result_queue.deliver_rate)} />
                </Stack>
            </CardContent>
        </Card>
    );
};

const InfraQueueRow: React.FC<{ q: QueueTile } & QueueActions> = ({ q, onBrowse, onPurge }) => (
    <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{
            py: 1,
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            '&:last-child': { borderBottom: 'none' },
        }}
    >
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: 'rgba(255,255,255,0.9)' }}>
                {q.name}
            </Typography>
        </Box>
        <Stack direction="row" spacing={3} alignItems="center" mr={1}>
            <Stat label="Depth" value={q.depth} accent={q.depth > 0} />
            <Stat label="Consumers" value={q.consumers} />
            <Stat label="In/s" value={formatRate(q.publish_rate)} />
            <Stat label="Out/s" value={formatRate(q.deliver_rate)} />
        </Stack>
        <QueueActionButtons name={q.name} depth={q.depth} onBrowse={onBrowse} onPurge={onPurge} />
    </Stack>
);

const Stat: React.FC<{ label: string; value: number | string; accent?: boolean; bad?: boolean }> =
    ({ label, value, accent, bad }) => (
        <Box>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>{label}</Typography>
            <Typography
                variant="h6"
                sx={{
                    fontWeight: 700,
                    color: accent ? (bad ? '#f87171' : '#67e8f9') : 'rgba(255,255,255,0.9)',
                    lineHeight: 1.2,
                }}
            >
                {value}
            </Typography>
        </Box>
    );

// ---------- Page ----------

export const PipelineHealthPage: React.FC = () => {
    const [data, setData] = useState<BrokerHealth | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [autoRefresh, setAutoRefresh] = useState(true);
    // Avoid stacking polls if the backend ever stalls.
    const inFlightRef = useRef(false);

    const client = useMemo(() => getAxiosClient(API_BASE), []);

    const fetchHealth = useCallback(async () => {
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        setLoading(true);
        try {
            const resp = await client.get<BrokerHealth>('/admin/broker/health');
            setData(resp.data);
            setError(null);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            setError(`Failed to load broker health: ${msg}`);
        } finally {
            setLoading(false);
            inFlightRef.current = false;
        }
    }, [client]);

    useEffect(() => {
        fetchHealth();
        if (!autoRefresh) return;
        const id = setInterval(fetchHealth, POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [autoRefresh, fetchHealth]);

    // ---- Browse / Peek drawer state ----
    const [browseQueue, setBrowseQueue] = useState<string | null>(null);
    const [peek, setPeek] = useState<PeekResponse | null>(null);
    const [peekLoading, setPeekLoading] = useState(false);
    const [peekError, setPeekError] = useState<string | null>(null);

    const openBrowse = useCallback(async (name: string) => {
        setBrowseQueue(name);
        setPeek(null);
        setPeekError(null);
        setPeekLoading(true);
        try {
            const resp = await client.get<PeekResponse>(
                `/admin/broker/queues/${encodeURIComponent(name)}/peek`,
                { params: { count: 10 } },
            );
            setPeek(resp.data);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            setPeekError(msg);
        } finally {
            setPeekLoading(false);
        }
    }, [client]);

    const closeBrowse = useCallback(() => {
        setBrowseQueue(null);
        setPeek(null);
        setPeekError(null);
    }, []);

    // ---- Purge dialog state ----
    const [purgeQueue, setPurgeQueue] = useState<string | null>(null);
    const [purgeBusy, setPurgeBusy] = useState(false);
    const [snack, setSnack] = useState<{ msg: string; severity: 'success' | 'error' } | null>(null);

    const openPurge = useCallback((name: string) => setPurgeQueue(name), []);
    const closePurge = useCallback(() => {
        if (!purgeBusy) setPurgeQueue(null);
    }, [purgeBusy]);

    const confirmPurge = useCallback(async () => {
        if (!purgeQueue) return;
        setPurgeBusy(true);
        try {
            const resp = await client.post<{ queue: string; purged: number }>(
                `/admin/broker/queues/${encodeURIComponent(purgeQueue)}/purge`,
            );
            setSnack({ msg: `Purged ${resp.data.purged} messages from ${resp.data.queue}`, severity: 'success' });
            setPurgeQueue(null);
            fetchHealth();
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            setSnack({ msg: `Purge failed: ${msg}`, severity: 'error' });
        } finally {
            setPurgeBusy(false);
        }
    }, [client, purgeQueue, fetchHealth]);

    const mgmtUiUrl = data
        ? `http://${data.broker.host}:${data.broker.management_port}`
        : null;

    return (
        <Container maxWidth="xl" sx={{ py: 3 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>Pipeline Health</Typography>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                        Magellon-domain projection of RabbitMQ broker state and plugin liveness.
                        For raw queue/exchange browsing,{' '}
                        {mgmtUiUrl ? (
                            <MuiLink href={mgmtUiUrl} target="_blank" rel="noopener" sx={{ color: '#67e8f9' }}>
                                open the RabbitMQ Management UI <ExternalLink size={12} style={{ verticalAlign: 'middle' }} />
                            </MuiLink>
                        ) : 'open the RabbitMQ Management UI'}.
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                    <FormControlLabel
                        control={<Switch checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} size="small" />}
                        label={<Typography variant="body2">Auto-refresh 5s</Typography>}
                    />
                    <Tooltip title="Refresh now">
                        <span>
                            <IconButton onClick={fetchHealth} disabled={loading} size="small">
                                {loading ? <CircularProgress size={18} /> : <RefreshCw size={18} />}
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            </Stack>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {data && !data.broker.reachable && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    Broker management API unreachable at <code>{data.broker.host}:{data.broker.management_port}</code>
                    {data.broker.error ? ` — ${data.broker.error}` : ''}.
                    Pipeline tiles below show last-known shape only. Plugin liveness is unaffected (in-process registry).
                </Alert>
            )}

            {/* Pipeline tiles — answers "is my pipeline healthy?" at a glance. */}
            {data && (
                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
                        gap: 2,
                        mb: 3,
                    }}
                >
                    {data.pipelines.map((p) => (
                        <PipelineCard key={p.name} p={p} onBrowse={openBrowse} onPurge={openPurge} />
                    ))}
                </Box>
            )}

            {/* Infrastructure queues — events bus, plugin liveness, ad-hoc with activity. */}
            {data && data.infrastructure.length > 0 && (
                <Paper variant="outlined" sx={{ bgcolor: '#0d1117', borderColor: 'rgba(255,255,255,0.08)', p: 2, mb: 2 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>Infrastructure Queues</Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', display: 'block', mb: 1.5 }}>
                        Events bus, plugin liveness, and any other queue with activity that isn't a per-pipeline task/result queue.
                    </Typography>
                    <Box>
                        {data.infrastructure.map((q) => (
                            <InfraQueueRow key={q.name ?? '_'} q={q} onBrowse={openBrowse} onPurge={openPurge} />
                        ))}
                    </Box>
                </Paper>
            )}

            {/* Plugin liveness — Magellon-specific, not in built-in RMQ UI. */}
            {data && (
                <Paper variant="outlined" sx={{ bgcolor: '#0d1117', borderColor: 'rgba(255,255,255,0.08)', p: 2, mb: 2 }}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                        <Activity size={18} style={{ color: '#67e8f9' }} />
                        <Typography variant="h6" sx={{ fontWeight: 700 }}>Plugin Liveness</Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                            ({data.plugins.length} alive)
                        </Typography>
                    </Stack>
                    {data.plugins.length === 0 ? (
                        <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                            No plugin announces received yet. Plugins publish liveness on <code>magellon.plugins.*</code>.
                        </Typography>
                    ) : (
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <Th>Plugin</Th>
                                        <Th>Version</Th>
                                        <Th>Category</Th>
                                        <Th>Instance</Th>
                                        <Th>Status</Th>
                                        <Th>Last heartbeat</Th>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {data.plugins.map((p) => {
                                        const stale = pluginStaleness(p);
                                        return (
                                            <TableRow key={p.instance_id}>
                                                <Td><strong>{p.plugin_id}</strong></Td>
                                                <Td>{p.plugin_version}</Td>
                                                <Td>{p.category}</Td>
                                                <Td><code style={{ fontSize: '0.75rem' }}>{p.instance_id.slice(0, 8)}</code></Td>
                                                <Td>{p.status}</Td>
                                                <Td><StatusChip tone={stale.tone} label={stale.label} /></Td>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </Paper>
            )}

            {data && (
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)' }}>
                    Last updated {new Date(data.as_of).toLocaleTimeString()} ·
                    polling every {POLL_INTERVAL_MS / 1000}s
                </Typography>
            )}

            <BrowseDrawer
                queue={browseQueue}
                data={peek}
                loading={peekLoading}
                error={peekError}
                onClose={closeBrowse}
                onRefresh={() => browseQueue && openBrowse(browseQueue)}
            />

            <Dialog open={purgeQueue !== null} onClose={closePurge} maxWidth="xs" fullWidth>
                <DialogTitle sx={{ color: '#f87171', fontWeight: 700 }}>
                    Purge queue?
                </DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        This drops <strong>every pending message</strong> in <code>{purgeQueue}</code>.
                        Already-delivered messages (in flight to a consumer) are not affected.
                        This is irreversible.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={closePurge} disabled={purgeBusy}>Cancel</Button>
                    <Button
                        onClick={confirmPurge}
                        disabled={purgeBusy}
                        color="error"
                        variant="contained"
                        startIcon={purgeBusy ? <CircularProgress size={14} /> : <Trash2 size={14} />}
                    >
                        Purge
                    </Button>
                </DialogActions>
            </Dialog>

            <Snackbar
                open={snack !== null}
                autoHideDuration={4000}
                onClose={() => setSnack(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
                {snack ? <Alert severity={snack.severity} onClose={() => setSnack(null)}>{snack.msg}</Alert> : undefined}
            </Snackbar>
        </Container>
    );
};

// ---------- Browse drawer ----------

const BrowseDrawer: React.FC<{
    queue: string | null;
    data: PeekResponse | null;
    loading: boolean;
    error: string | null;
    onClose: () => void;
    onRefresh: () => void;
}> = ({ queue, data, loading, error, onClose, onRefresh }) => {
    const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

    const copyPayload = useCallback(async (idx: number, payload: unknown) => {
        const text = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
        try {
            await navigator.clipboard.writeText(text);
            setCopiedIdx(idx);
            setTimeout(() => setCopiedIdx((curr) => (curr === idx ? null : curr)), 1500);
        } catch {
            // Clipboard API can fail in non-secure contexts; ignore quietly,
            // user can still select the text manually from the rendered JSON.
        }
    }, []);

    return (
        <Drawer
            anchor="right"
            open={queue !== null}
            onClose={onClose}
            PaperProps={{
                sx: { width: { xs: '100%', sm: 600, md: 720 }, bgcolor: '#0a1929', color: 'rgba(255,255,255,0.85)' },
            }}
        >
            <Box sx={{ p: 2, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                    <Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>Peek queue</Typography>
                        <Typography variant="h6" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>{queue}</Typography>
                    </Box>
                    <Stack direction="row" spacing={1}>
                        <Tooltip title="Refresh">
                            <span>
                                <IconButton onClick={onRefresh} disabled={loading} size="small">
                                    {loading ? <CircularProgress size={18} /> : <RefreshCw size={18} />}
                                </IconButton>
                            </span>
                        </Tooltip>
                        <IconButton onClick={onClose} size="small"><X size={18} /></IconButton>
                    </Stack>
                </Stack>
                <Alert severity="info" sx={{ fontSize: '0.78rem', py: 0.5 }}>
                    Messages are auto-requeued after this peek — may briefly affect FIFO ordering.
                </Alert>
            </Box>

            <Box sx={{ p: 2, overflow: 'auto', flexGrow: 1 }}>
                {error && <Alert severity="error">{error}</Alert>}
                {!error && data && data.error && <Alert severity="warning">{data.error}</Alert>}
                {!error && data && data.messages.length === 0 && (
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                        Queue is empty (no ready messages). Already-delivered messages aren't included in a peek.
                    </Typography>
                )}
                {!error && data && data.messages.map((m, idx) => (
                    <Paper
                        key={idx}
                        variant="outlined"
                        sx={{ bgcolor: '#0d1117', borderColor: 'rgba(255,255,255,0.08)', mb: 2, p: 1.5 }}
                    >
                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={1}>
                            <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>routing key</Typography>
                                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 0.5, wordBreak: 'break-all' }}>
                                    {m.routing_key ?? '—'}
                                </Typography>
                                {(m.ce_type || m.ce_subject) && (
                                    <Stack direction="row" spacing={2}>
                                        {m.ce_type && (
                                            <Box>
                                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>ce-type</Typography>
                                                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{m.ce_type}</Typography>
                                            </Box>
                                        )}
                                        {m.ce_subject && (
                                            <Box>
                                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>ce-subject</Typography>
                                                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{m.ce_subject}</Typography>
                                            </Box>
                                        )}
                                    </Stack>
                                )}
                            </Box>
                            <Tooltip title={copiedIdx === idx ? 'Copied!' : 'Copy payload'}>
                                <IconButton size="small" onClick={() => copyPayload(idx, m.payload)}>
                                    {copiedIdx === idx ? <Check size={16} style={{ color: '#7ee787' }} /> : <Copy size={16} />}
                                </IconButton>
                            </Tooltip>
                        </Stack>
                        <Box
                            component="pre"
                            sx={{
                                m: 0,
                                p: 1,
                                bgcolor: '#06090f',
                                borderRadius: 1,
                                fontSize: '0.78rem',
                                fontFamily: 'monospace',
                                color: 'rgba(255,255,255,0.85)',
                                overflow: 'auto',
                                maxHeight: 320,
                            }}
                        >
                            {typeof m.payload === 'string' ? m.payload : JSON.stringify(m.payload, null, 2)}
                        </Box>
                    </Paper>
                ))}
            </Box>
        </Drawer>
    );
};

const Th: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <TableCell sx={{ color: 'rgba(255,255,255,0.6)', borderColor: 'rgba(255,255,255,0.08)', fontWeight: 600 }}>
        {children}
    </TableCell>
);

const Td: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <TableCell sx={{ color: 'rgba(255,255,255,0.85)', borderColor: 'rgba(255,255,255,0.08)' }}>
        {children}
    </TableCell>
);

export default PipelineHealthPage;
