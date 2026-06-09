/**
 * /panel/plugins/<plugin_id> — per-plugin detail + test workspace.
 *
 * Layout: header strip (identity + lifecycle) sits above two tabs:
 *
 *   ┌── Header strip ────────────────────────────────┐
 *   │  name · version · category · live/stopped     │
 *   │  description · install location               │
 *   │  [Run/Stop/Restart]  [back]                   │
 *   ├── [Workspace] [Logs] ──────────────────────────┤
 *   │  (selected tab content)                        │
 *   └────────────────────────────────────────────────┘
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
    Tab,
    Tabs,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Activity,
    ArrowLeft,
    ExternalLink,
    FolderOpen,
    Pause,
    Play,
    RotateCcw,
    ScrollText,
    Square,
    TerminalSquare,
} from 'lucide-react';
import type {
    InstallMethod,
    PluginSummary} from '../../features/plugin-runner/api/PluginApi.ts';
import {
    useInstalledFromDb,
    usePlugins
} from '../../features/plugin-runner/api/PluginApi.ts';
import { DeploymentMethodChip } from '../../features/plugin-runner/ui/DeploymentMethodChip.tsx';
import { PluginTestPanel } from '../../features/plugin-runner/ui/PluginTestPanel.tsx';
import { PluginActivityPanel } from '../../features/plugin-installer/ui/PluginActivityPanel.tsx';
import { PluginLogsPanel } from '../../features/plugin-installer/ui/PluginLogsPanel.tsx';
import {
    useAdminPluginProcessStatus,
    usePausePlugin,
    useRestartPlugin,
    useStartPlugin,
    useStopPlugin,
    useUnpausePlugin,
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
    installMethod?: InstallMethod | null;
    imageRef?: string | null;
    running: boolean;
    paused?: boolean;
    supportsPause?: boolean;
    /** When set, renders Start/Stop/Restart controls. */
    manifestPluginId?: string | null;
}

/**
 * RabbitMQ management UI base URL. Per-deployment override via
 * RMQ_MGMT_URL on configs.json (falls back to localhost which is
 * the docker-compose default). The deep-link button opens a tab on
 * the plugin's task / result queue so operators can dig into wire
 * state without typing the queue name.
 */
const rmqMgmtUrl = (queueName: string): string => {
    const base =
        (window as { __MAGELLON_CONFIG__?: { RMQ_MGMT_URL?: string } }).__MAGELLON_CONFIG__?.RMQ_MGMT_URL ??
        'http://localhost:15672';
    return `${base.replace(/\/$/, '')}/#/queues/%2F/${encodeURIComponent(queueName)}`;
};

/**
 * Derive the input + output queue names for a plugin from its
 * category. Matches CoreService/core/helper.py — every external
 * plugin's queues follow ``<category>_tasks_queue`` /
 * ``<category>_out_tasks_queue``. Returns null when the category
 * is missing so the Activity strip is hidden cleanly.
 */
const queueNamesFor = (category?: string | null): { tasks: string; out: string } | null => {
    if (!category) return null;
    const slug = category.toLowerCase().replace(/[\s-]/g, '_');
    return { tasks: `${slug}_tasks_queue`, out: `${slug}_out_tasks_queue` };
};

const HeaderStrip: React.FC<HeaderStripProps> = ({
    name,
    version,
    category,
    description,
    installDir,
    httpEndpoint,
    installMethod,
    imageRef,
    running,
    paused,
    supportsPause,
    manifestPluginId,
}) => {
    const start = useStartPlugin();
    const stop = useStopPlugin();
    const restart = useRestartPlugin();
    const pause = usePausePlugin();
    const unpause = useUnpausePlugin();
    const [actionLog, setActionLog] = React.useState<string | null>(null);
    const [actionError, setActionError] = React.useState<string | null>(null);

    const busy =
        start.isPending ||
        stop.isPending ||
        restart.isPending ||
        pause.isPending ||
        unpause.isPending;

    const run = async (
        verb: 'start' | 'stop' | 'restart' | 'pause' | 'unpause',
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
                            <DeploymentMethodChip method={installMethod} />
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
                                <Tooltip title={installDir}>
                                    <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                        <FolderOpen size={14} />
                                        <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                            {installDir}
                                        </Typography>
                                    </Stack>
                                </Tooltip>
                            )}
                            {imageRef && (
                                <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                    {imageRef}
                                </Typography>
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
                            <Tooltip
                                title={
                                    !supportsPause
                                        ? 'Pause is docker-only — uv plugins should be stopped instead'
                                        : paused
                                          ? 'Resume paused plugin'
                                          : running
                                            ? 'Pause plugin (memory stays resident)'
                                            : 'Plugin is not running'
                                }
                            >
                                <span>
                                    <IconButton
                                        aria-label={paused ? 'unpause' : 'pause'}
                                        disabled={
                                            busy ||
                                            !supportsPause ||
                                            (!paused && !running)
                                        }
                                        onClick={() =>
                                            run(
                                                paused ? 'unpause' : 'pause',
                                                paused ? unpause : pause,
                                            )
                                        }
                                    >
                                        <Pause size={18} />
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

                {/* RabbitMQ deep-links — operators get one-click access
                    to the plugin's input + output queues in the
                    management UI for "what's in flight?" without
                    typing queue names. Hidden when the category
                    can't be derived (uv plugins that haven't joined
                    the bus yet). */}
                {queueNamesFor(category) && (
                    <Stack
                        direction="row"
                        spacing={1}
                        useFlexGap
                        sx={{
                            mt: 1.5,
                            pt: 1.5,
                            borderTop: '1px solid',
                            borderColor: 'divider',
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            rowGap: 0.75,
                        }}
                    >
                        <Typography
                            variant="caption"
                            sx={{ color: 'text.secondary', mr: 0.5 }}
                        >
                            Queues:
                        </Typography>
                        {(() => {
                            const q = queueNamesFor(category)!;
                            return (
                                <>
                                    <Tooltip title="Open task queue in RabbitMQ Management UI">
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            endIcon={<ExternalLink size={12} />}
                                            href={rmqMgmtUrl(q.tasks)}
                                            target="_blank"
                                            rel="noreferrer"
                                            sx={{ textTransform: 'none', fontFamily: 'monospace', fontSize: 11 }}
                                        >
                                            {q.tasks}
                                        </Button>
                                    </Tooltip>
                                    <Tooltip title="Open result queue in RabbitMQ Management UI">
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            endIcon={<ExternalLink size={12} />}
                                            href={rmqMgmtUrl(q.out)}
                                            target="_blank"
                                            rel="noreferrer"
                                            sx={{ textTransform: 'none', fontFamily: 'monospace', fontSize: 11 }}
                                        >
                                            {q.out}
                                        </Button>
                                    </Tooltip>
                                </>
                            );
                        })()}
                    </Stack>
                )}

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
    const { '*': rawPluginId } = useParams();
    const pluginId = React.useMemo(() => {
        if (!rawPluginId) return rawPluginId;
        try {
            return decodeURIComponent(rawPluginId);
        } catch {
            return rawPluginId;
        }
    }, [rawPluginId]);
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

    // Tab state — `workspace` is the default because most operators come
    // here to run a task, not to read logs. Logs + Activity keep their
    // own mount state via the conditional render below so their
    // Socket.IO / poll subscriptions only run when the tab is active.
    const [tab, setTab] = React.useState<'workspace' | 'logs' | 'activity'>(
        'workspace',
    );

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
                kind: 'broker',
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
                        /* Prefer the manifest's display name over the
                         * announce-derived name. After we aligned
                         * PluginInfo.name with the manifest plugin_id
                         * (so the install pipeline's liveness check
                         * matches — see plugin-installer+plugins fix),
                         * live plugins announce their slug ("fft")
                         * rather than a friendly name. The manifest's
                         * `name:` field stays human-readable
                         * ("FFT — magnitude spectrum"). */
                        name={installedRow?.name ?? panelPlugin.name}
                        version={panelPlugin.version}
                        category={panelPlugin.category}
                        description={panelPlugin.description}
                        installDir={installedRow?.install_dir ?? null}
                        imageRef={installedRow?.image_ref ?? null}
                        httpEndpoint={installedRow?.http_endpoint ?? null}
                        installMethod={installedRow?.install_method ?? null}
                        running={running}
                        paused={processStatus.data?.status === 'paused'}
                        supportsPause={!!processStatus.data?.supports_pause}
                        manifestPluginId={installedRow?.manifest_plugin_id ?? null}
                    />
                    <Card variant="outlined">
                        <Tabs
                            value={tab}
                            onChange={(_, v) => setTab(v)}
                            sx={{ borderBottom: 1, borderColor: 'divider', px: 1 }}
                        >
                            <Tab
                                value="workspace"
                                label="Workspace"
                                icon={<TerminalSquare size={16} />}
                                iconPosition="start"
                                sx={{ minHeight: 48 }}
                            />
                            <Tab
                                value="logs"
                                label="Logs"
                                icon={<ScrollText size={16} />}
                                iconPosition="start"
                                disabled={!installedRow?.manifest_plugin_id}
                                sx={{ minHeight: 48 }}
                            />
                            <Tab
                                value="activity"
                                label="Activity"
                                icon={<Activity size={16} />}
                                iconPosition="start"
                                disabled={!installedRow?.manifest_plugin_id}
                                sx={{ minHeight: 48 }}
                            />
                        </Tabs>
                        <CardContent>
                            {tab === 'workspace' && (
                                <PluginTestPanel
                                    plugin={panelPlugin}
                                    runEnabled={running}
                                    runDisabledReason={
                                        running
                                            ? undefined
                                            : 'Start the plugin to dispatch test tasks against it.'
                                    }
                                />
                            )}
                            {tab === 'logs' && installedRow?.manifest_plugin_id && (
                                <PluginLogsPanel
                                    pluginId={installedRow.manifest_plugin_id}
                                />
                            )}
                            {tab === 'activity' && installedRow?.manifest_plugin_id && (
                                <PluginActivityPanel
                                    pluginId={installedRow.manifest_plugin_id}
                                />
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </Container>
    );
};

export default PluginRunnerPageView;
