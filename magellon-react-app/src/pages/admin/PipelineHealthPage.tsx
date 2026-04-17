import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Container,
    Divider,
    FormControlLabel,
    IconButton,
    Link as MuiLink,
    Paper,
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
import { RefreshCw, ExternalLink, Activity, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
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
    plugins: PluginEntry[];
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

const PipelineCard: React.FC<{ p: PipelineEntry }> = ({ p }) => {
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

                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                    Task queue · {p.task_queue.name ?? '—'}
                </Typography>
                <Stack direction="row" spacing={3} mt={0.5} mb={2}>
                    <Stat label="Depth" value={p.task_queue.depth} accent={p.task_queue.depth > 0} />
                    <Stat label="Consumers" value={p.task_queue.consumers} accent={p.task_queue.consumers === 0} bad />
                    <Stat label="In/s" value={formatRate(p.task_queue.publish_rate)} />
                    <Stat label="Out/s" value={formatRate(p.task_queue.deliver_rate)} />
                </Stack>

                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.08)', mb: 1.5 }} />

                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                    Result queue · {p.result_queue.name ?? '—'}
                </Typography>
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
                    {data.pipelines.map((p) => <PipelineCard key={p.name} p={p} />)}
                </Box>
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
        </Container>
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
