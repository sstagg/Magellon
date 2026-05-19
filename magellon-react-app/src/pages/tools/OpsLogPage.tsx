import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Container,
    FormControlLabel,
    IconButton,
    Paper,
    Stack,
    Switch,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    Tooltip,
    Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { RefreshCw, Database } from 'lucide-react';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';

// ── Types ────────────────────────────────────────────────────────────────────

interface OpsLogInfo {
    log_glob: string;
    file_count: number;
    total_size_mb: number;
}

interface SummaryRow {
    category: string;
    status: string;
    n: number;
    first_seen: string | null;
    last_seen: string | null;
    avg_s: number | null;
}

interface EventRow {
    ts: string | null;
    event: string | null;
    category: string | null;
    status: string | null;
    session_name: string | null;
    image_name: string | null;
    job_id: string | null;
    task_id: string | null;
    duration_ms: number | null;
    processor_error: string | null;
    queue: string | null;
}

interface ThroughputRow {
    hour: string;
    category: string;
    n: number;
}

// ── Constants ────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 10_000;
const API_BASE = (settings.ConfigData as { SERVER_API_URL: string }).SERVER_API_URL;

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtTs(ts: string | null): string {
    if (!ts) return '—';
    try {
        return new Date(ts).toLocaleTimeString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
    } catch {
        return ts;
    }
}

function fmtDuration(ms: number | null): string {
    if (ms == null) return '—';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
}

function truncate(s: string | null, n = 40): string {
    if (!s) return '—';
    return s.length > n ? s.slice(0, n) + '…' : s;
}

// ── Sub-components ────────────────────────────────────────────────────────────

const StatusChip: React.FC<{ status: string | null }> = ({ status }) => {
    const theme = useTheme();
    const s = status ?? '?';
    const tone =
        s === 'completed' ? 'success' :
        s === 'failed' ? 'error' :
        s === 'started' ? 'info' : 'default';
    const palette = tone === 'default'
        ? null
        : theme.palette[tone as 'success' | 'error' | 'info'];
    const bg = palette ? alpha(palette.main, theme.palette.mode === 'dark' ? 0.18 : 0.12) : undefined;
    const fg = palette
        ? (theme.palette.mode === 'dark' ? palette.light : palette.dark)
        : 'text.secondary';
    return (
        <Chip
            size="small"
            label={s}
            sx={{ bgcolor: bg, color: fg, fontWeight: 600, fontSize: '0.72rem' }}
        />
    );
};

const Th: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <TableCell sx={{ color: 'text.secondary', borderColor: 'divider', fontWeight: 600, whiteSpace: 'nowrap' }}>
        {children}
    </TableCell>
);

const Td: React.FC<{ children: React.ReactNode; mono?: boolean }> = ({ children, mono }) => (
    <TableCell sx={{
        color: 'text.primary',
        borderColor: 'divider',
        fontFamily: mono ? 'monospace' : undefined,
        fontSize: mono ? '0.78rem' : undefined,
        maxWidth: 180,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
    }}>
        {children}
    </TableCell>
);

// ── Summary Tab ───────────────────────────────────────────────────────────────

const SummaryTab: React.FC<{ rows: SummaryRow[] }> = ({ rows }) => (
    <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'background.paper', borderColor: 'divider' }}>
        <Table size="small">
            <TableHead>
                <TableRow>
                    <Th>Category</Th>
                    <Th>Status</Th>
                    <Th>Count</Th>
                    <Th>Avg duration</Th>
                    <Th>First seen</Th>
                    <Th>Last seen</Th>
                </TableRow>
            </TableHead>
            <TableBody>
                {rows.map((r, i) => (
                    <TableRow key={i} hover>
                        <Td mono>{r.category}</Td>
                        <Td><StatusChip status={r.status} /></Td>
                        <Td><strong>{r.n.toLocaleString()}</strong></Td>
                        <Td>{r.avg_s != null ? `${r.avg_s} s` : '—'}</Td>
                        <Td>{fmtTs(r.first_seen)}</Td>
                        <Td>{fmtTs(r.last_seen)}</Td>
                    </TableRow>
                ))}
                {rows.length === 0 && (
                    <TableRow>
                        <TableCell colSpan={6} sx={{ textAlign: 'center', color: 'text.secondary', py: 3 }}>
                            No events recorded yet.
                        </TableCell>
                    </TableRow>
                )}
            </TableBody>
        </Table>
    </TableContainer>
);

// ── Events Tab ────────────────────────────────────────────────────────────────

const EventsTab: React.FC<{ rows: EventRow[] }> = ({ rows }) => (
    <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'background.paper', borderColor: 'divider' }}>
        <Table size="small">
            <TableHead>
                <TableRow>
                    <Th>Time</Th>
                    <Th>Category</Th>
                    <Th>Status</Th>
                    <Th>Session</Th>
                    <Th>Image</Th>
                    <Th>Duration</Th>
                    <Th>Error</Th>
                </TableRow>
            </TableHead>
            <TableBody>
                {rows.map((r, i) => (
                    <TableRow key={i} hover>
                        <Td mono>{fmtTs(r.ts)}</Td>
                        <Td mono>{r.category ?? '—'}</Td>
                        <Td><StatusChip status={r.status} /></Td>
                        <Td>{r.session_name ?? '—'}</Td>
                        <Td mono>{truncate(r.image_name, 32)}</Td>
                        <Td>{fmtDuration(r.duration_ms)}</Td>
                        <Td>
                            {r.processor_error ? (
                                <Tooltip title={r.processor_error}>
                                    <Typography
                                        variant="caption"
                                        sx={{ color: 'error.main', fontFamily: 'monospace', cursor: 'help' }}
                                    >
                                        {truncate(r.processor_error, 36)}
                                    </Typography>
                                </Tooltip>
                            ) : '—'}
                        </Td>
                    </TableRow>
                ))}
                {rows.length === 0 && (
                    <TableRow>
                        <TableCell colSpan={7} sx={{ textAlign: 'center', color: 'text.secondary', py: 3 }}>
                            No events.
                        </TableCell>
                    </TableRow>
                )}
            </TableBody>
        </Table>
    </TableContainer>
);

// ── Throughput Tab ────────────────────────────────────────────────────────────

const ThroughputTab: React.FC<{ rows: ThroughputRow[] }> = ({ rows }) => {
    const categories = useMemo(() => [...new Set(rows.map(r => r.category))].sort(), [rows]);
    const hours = useMemo(() => [...new Set(rows.map(r => r.hour))].sort(), [rows]);
    const byHourCat = useMemo(() => {
        const m: Record<string, Record<string, number>> = {};
        rows.forEach(r => {
            (m[r.hour] ??= {})[r.category] = r.n;
        });
        return m;
    }, [rows]);

    if (rows.length === 0) {
        return (
            <Paper variant="outlined" sx={{ p: 3, bgcolor: 'background.paper', borderColor: 'divider' }}>
                <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center' }}>
                    No events in the last 24 hours.
                </Typography>
            </Paper>
        );
    }

    return (
        <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'background.paper', borderColor: 'divider' }}>
            <Table size="small">
                <TableHead>
                    <TableRow>
                        <Th>Hour</Th>
                        {categories.map(c => <Th key={c}>{c}</Th>)}
                    </TableRow>
                </TableHead>
                <TableBody>
                    {hours.map(h => (
                        <TableRow key={h} hover>
                            <Td mono>{h}</Td>
                            {categories.map(c => (
                                <Td key={c}>
                                    {byHourCat[h]?.[c] != null
                                        ? <strong>{byHourCat[h][c]}</strong>
                                        : <span style={{ color: 'var(--mui-palette-text-disabled, #9e9e9e)' }}>—</span>}
                                </Td>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

// ── Page ──────────────────────────────────────────────────────────────────────

type TabId = 'summary' | 'recent' | 'failed' | 'throughput';

const OpsLogPage: React.FC = () => {
    const client = useMemo(() => getAxiosClient(API_BASE), []);
    const inFlightRef = useRef(false);

    const [tab, setTab] = useState<TabId>('summary');
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [info, setInfo] = useState<OpsLogInfo | null>(null);
    const [summary, setSummary] = useState<SummaryRow[]>([]);
    const [recent, setRecent] = useState<EventRow[]>([]);
    const [failed, setFailed] = useState<EventRow[]>([]);
    const [throughput, setThroughput] = useState<ThroughputRow[]>([]);

    const fetchAll = useCallback(async () => {
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        setLoading(true);
        try {
            const [infoR, summaryR, recentR, failedR, throughputR] = await Promise.all([
                client.get<OpsLogInfo>('/web/ops/info'),
                client.get<SummaryRow[]>('/web/ops/summary'),
                client.get<EventRow[]>('/web/ops/recent', { params: { limit: 100 } }),
                client.get<EventRow[]>('/web/ops/failed', { params: { limit: 100 } }),
                client.get<ThroughputRow[]>('/web/ops/throughput'),
            ]);
            setInfo(infoR.data);
            setSummary(summaryR.data);
            setRecent(recentR.data);
            setFailed(failedR.data);
            setThroughput(throughputR.data);
            setError(null);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            setError(`Failed to load ops log: ${msg}`);
        } finally {
            setLoading(false);
            inFlightRef.current = false;
        }
    }, [client]);

    useEffect(() => {
        fetchAll();
        if (!autoRefresh) return;
        const id = setInterval(fetchAll, POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [autoRefresh, fetchAll]);

    return (
        <Container maxWidth="xl" sx={{ py: 3 }}>
            {/* Header */}
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                        <Database size={20} />
                        <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary' }}>
                            Ops Event Log
                        </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Live view of the operational JSONL log (DuckDB).
                        {info && (
                            <> · <strong>{info.file_count}</strong> file{info.file_count !== 1 ? 's' : ''},{' '}
                            <strong>{info.total_size_mb} MB</strong> on disk</>
                        )}
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <FormControlLabel
                        control={
                            <Switch
                                checked={autoRefresh}
                                onChange={e => setAutoRefresh(e.target.checked)}
                                size="small"
                            />
                        }
                        label={<Typography variant="body2">Auto-refresh 10s</Typography>}
                    />
                    <Tooltip title="Refresh now">
                        <span>
                            <IconButton onClick={fetchAll} disabled={loading} size="small">
                                {loading ? <CircularProgress size={18} /> : <RefreshCw size={18} />}
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            </Stack>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                <Tabs value={tab} onChange={(_, v) => setTab(v as TabId)}>
                    <Tab
                        value="summary"
                        label={
                            <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                <span>Summary</span>
                                {summary.length > 0 && (
                                    <Chip size="small" label={summary.reduce((s, r) => s + r.n, 0).toLocaleString()} />
                                )}
                            </Stack>
                        }
                    />
                    <Tab
                        value="recent"
                        label={
                            <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                <span>Recent</span>
                                {recent.length > 0 && <Chip size="small" label={recent.length} />}
                            </Stack>
                        }
                    />
                    <Tab
                        value="failed"
                        label={
                            <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                <span>Failed</span>
                                {failed.length > 0 && (
                                    <Chip
                                        size="small"
                                        label={failed.length}
                                        color="error"
                                    />
                                )}
                            </Stack>
                        }
                    />
                    <Tab value="throughput" label="Throughput (24h)" />
                </Tabs>
            </Box>

            {tab === 'summary' && <SummaryTab rows={summary} />}
            {tab === 'recent' && <EventsTab rows={recent} />}
            {tab === 'failed' && <EventsTab rows={failed} />}
            {tab === 'throughput' && <ThroughputTab rows={throughput} />}
        </Container>
    );
};

export default OpsLogPage;
