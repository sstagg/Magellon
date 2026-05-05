/**
 * /panel/plugins/<plugin_id> — per-plugin detail + test workspace.
 *
 * Layout (no tabs, both halves always visible):
 *
 *   ┌── Header strip ────────────────────────────────┐
 *   │  name · version · category · live/stopped     │
 *   │  description · install location               │
 *   │  [Run/Stop/Restart]  [back]                   │
 *   ├── Settings ──────┬── Activity ─────────────────┤
 *   │  Transport pick   │  ProgressTracker (bus)     │
 *   │  SchemaForm       │  Wire envelopes (live)     │
 *   │  [Run]            │  Result (output schema)    │
 *   └───────────────────┴────────────────────────────┘
 *
 * Lookup order for plugin identity:
 *   1. Live plugins (``GET /plugins/``) — heartbeating right now.
 *   2. DB catalog (``GET /plugins/db``) — installed but not currently
 *      announcing. Test panel renders disabled with a hint.
 */
import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Container,
    IconButton,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowLeft,
    FolderOpen,
    Play,
    RotateCcw,
    Square,
} from 'lucide-react';
import {
    useInstalledFromDb,
    usePlugins,
    PluginSummary,
} from '../../features/plugin-runner/api/PluginApi.ts';
import { PluginTestPanel } from '../../features/plugin-runner/ui/PluginTestPanel.tsx';
import {
    useAdminPluginProcessStatus,
    useRestartPlugin,
    useStartPlugin,
    useStopPlugin,
} from '../../features/plugin-installer/api/installerApi.ts';

const errorText = (err: unknown, fallback: string): string => {
    if (typeof err === 'object' && err !== null) {
        const r = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
        const detail = r.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (typeof r.message === 'string') return r.message;
    }
    return fallback;
};

// ---------------------------------------------------------------------------
// Header strip — identity + lifecycle controls
// ---------------------------------------------------------------------------

interface HeaderStripProps {
    name: string;
    version?: string;
    category?: string | null;
    description?: string | null;
    installDir?: string | null;
    httpEndpoint?: string | null;
    running: boolean;
    /** When set, renders Start/Stop/Restart controls. */
    manifestPluginId?: string | null;
}

const HeaderStrip: React.FC<HeaderStripProps> = ({
    name,
    version,
    category,
    description,
    installDir,
    httpEndpoint,
    running,
    manifestPluginId,
}) => {
    const start = useStartPlugin();
    const stop = useStopPlugin();
    const restart = useRestartPlugin();
    const [actionLog, setActionLog] = React.useState<string | null>(null);
    const [actionError, setActionError] = React.useState<string | null>(null);

    const busy = start.isLoading || stop.isLoading || restart.isLoading;

    const run = async (
        verb: 'start' | 'stop' | 'restart',
        mut: typeof start,
    ) => {
        if (!manifestPluginId) return;
        setActionError(null);
        setActionLog(null);
        try {
            const res = await mut.mutateAsync(manifestPluginId);
            setActionLog(res.logs ?? `${verb} ok`);
        } catch (err) {
            setActionError(errorText(err, `${verb} failed`));
        }
    };

    return (
        <Card variant="outlined" sx={{ mb: 2 }}>
            <CardContent>
                <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <Box sx={{ flex: 1, minWidth: 300 }}>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5, flexWrap: 'wrap' }}>
                            <Typography variant="h5">{name}</Typography>
                            {version && <Chip size="small" label={`v${version}`} />}
                            {category && <Chip size="small" variant="outlined" label={category} />}
                            <Chip
                                size="small"
                                color={running ? 'success' : 'default'}
                                label={running ? 'Live' : 'Stopped'}
                            />
                        </Stack>
                        {description && (
                            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.75 }}>
                                {description}
                            </Typography>
                        )}
                        <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
                            {installDir && (
                                <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                    <FolderOpen size={14} />
                                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                        {installDir}
                                    </Typography>
                                </Stack>
                            )}
                            {httpEndpoint && (
                                <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                    {httpEndpoint}
                                </Typography>
                            )}
                        </Stack>
                    </Box>

                    {manifestPluginId && (
                        <Stack direction="row" spacing={1}>
                            <Tooltip title={running ? 'Already running' : 'Start plugin'}>
                                <span>
                                    <IconButton
                                        color="success"
                                        aria-label="start"
                                        disabled={busy || running}
                                        onClick={() => run('start', start)}
                                    >
                                        <Play size={18} />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title={running ? 'Stop plugin' : 'Already stopped'}>
                                <span>
                                    <IconButton
                                        aria-label="stop"
                                        disabled={busy || !running}
                                        onClick={() => run('stop', stop)}
                                    >
                                        <Square size={18} />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title="Restart plugin">
                                <span>
                                    <IconButton
                                        aria-label="restart"
                                        disabled={busy}
                                        onClick={() => run('restart', restart)}
                                    >
                                        <RotateCcw size={18} />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </Stack>
                    )}
                </Stack>

                {actionError && (
                    <Alert severity="error" sx={{ mt: 1.5 }} onClose={() => setActionError(null)}>
                        {actionError}
                    </Alert>
                )}
                {actionLog && (
                    <Alert severity="success" sx={{ mt: 1.5 }} onClose={() => setActionLog(null)}>
                        <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit' }}>
                            {actionLog}
                        </pre>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
};

// ---------------------------------------------------------------------------
// Page view
// ---------------------------------------------------------------------------

export const PluginRunnerPageView: React.FC = () => {
    const { '*': pluginId } = useParams();
    const navigate = useNavigate();
    const { data: livePlugins, isLoading: liveLoading } = usePlugins();
    const { data: installedRows, isLoading: dbLoading } = useInstalledFromDb();

    // Resolve identity: catalog row gives us manifest/install metadata,
    // live row gives us the runtime plugin_id used for schema fetch +
    // job submit. Match the live row by plugin_id, falling back to a
    // category/slug heuristic when the announce form differs from the
    // catalog form (e.g. "fft/FFT — magnitude spectrum" vs "fft/FFT Plugin").
    const installedRow = installedRows?.find(
        (r) => r.plugin_id === pluginId || r.manifest_plugin_id === pluginId,
    );

    const livePlugin = livePlugins?.find((p) => {
        if (p.plugin_id === pluginId) return true;
        if (!installedRow?.manifest_plugin_id) return false;
        const slug = installedRow.manifest_plugin_id.toLowerCase();
        const liveId = p.plugin_id.toLowerCase();
        return liveId === slug || liveId.startsWith(`${slug}/`);
    });

    const processStatus = useAdminPluginProcessStatus(installedRow?.manifest_plugin_id ?? null);
    const isLoading = liveLoading || dbLoading;
    const found = livePlugin || installedRow;
    const running = !!livePlugin || !!processStatus.data?.running;

    // Synthesize a PluginSummary for the test panel when only the catalog
    // row is known. The panel needs `plugin_id` + `category` to fetch
    // schemas and route Sync calls; everything else is presentational.
    const panelPlugin: PluginSummary | null = livePlugin
        ? livePlugin
        : installedRow
            ? ({
                plugin_id: installedRow.manifest_plugin_id ?? installedRow.plugin_id,
                name: installedRow.name ?? installedRow.plugin_id,
                description: installedRow.description ?? '',
                version: installedRow.version ?? '',
                category: installedRow.category ?? '',
                capabilities: [],
            } as unknown as PluginSummary)
            : null;

    return (
        <Container maxWidth="xl" sx={{ py: 3 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 2 }}>
                <Button
                    size="small"
                    startIcon={<ArrowLeft size={16} />}
                    onClick={() => navigate('/en/panel/plugins')}
                >
                    All plugins
                </Button>
            </Stack>

            {isLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                    <CircularProgress />
                </Box>
            )}
            {!isLoading && !found && (
                <Alert severity="warning">
                    Plugin "{pluginId}" was not found — neither live on the bus
                    nor in the install catalog.
                </Alert>
            )}

            {found && panelPlugin && (
                <>
                    <HeaderStrip
                        name={panelPlugin.name}
                        version={panelPlugin.version}
                        category={panelPlugin.category}
                        description={panelPlugin.description}
                        installDir={installedRow?.install_dir ?? null}
                        httpEndpoint={installedRow?.http_endpoint ?? null}
                        running={running}
                        manifestPluginId={installedRow?.manifest_plugin_id ?? null}
                    />
                    <PluginTestPanel
                        plugin={panelPlugin}
                        runEnabled={running}
                        runDisabledReason={
                            running
                                ? undefined
                                : 'Start the plugin to dispatch test tasks against it.'
                        }
                    />
                </>
            )}
        </Container>
    );
};

export default PluginRunnerPageView;
