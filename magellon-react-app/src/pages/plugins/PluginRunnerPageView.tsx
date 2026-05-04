/**
 * /panel/plugins/<plugin_id> — per-plugin detail + runner page.
 *
 * Lookup order:
 *   1. Live plugins (``GET /plugins/``) — heartbeating right now.
 *      Renders the full ``PluginRunner`` component (input form,
 *      submit, results).
 *   2. DB catalog (``GET /plugins/db``) — installed but not currently
 *      announcing. Renders an "installed but stopped" panel with the
 *      same Run / Stop / Restart controls that live on each card,
 *      so the operator can launch the plugin from the detail page.
 *
 * Pre-PI-6.1 step 2 didn't exist — installed-but-stopped plugins
 * 404'd on the detail route. The detail page now matches operator
 * expectations: every installed plugin has a page.
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
} from '../../features/plugin-runner/api/PluginApi.ts';
import { PluginRunner } from '../../features/plugin-runner/ui/PluginRunner.tsx';
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

const InstalledNotRunningPanel: React.FC<{
    manifestPluginId: string;
    name: string;
    version?: string;
    category?: string | null;
    installDir?: string | null;
    httpEndpoint?: string | null;
    description?: string | null;
}> = ({
    manifestPluginId,
    name,
    version,
    category,
    installDir,
    httpEndpoint,
    description,
}) => {
    const { data: status } = useAdminPluginProcessStatus(manifestPluginId);
    const start = useStartPlugin();
    const stop = useStopPlugin();
    const restart = useRestartPlugin();
    const [actionLog, setActionLog] = React.useState<string | null>(null);
    const [actionError, setActionError] = React.useState<string | null>(null);
    const running = !!status?.running;
    const busy = start.isLoading || stop.isLoading || restart.isLoading;

    const run = async (
        verb: 'start' | 'stop' | 'restart',
        mut: typeof start,
    ) => {
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
        <Card variant="outlined">
            <CardContent>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                    <Typography variant="h5">{name}</Typography>
                    {version && <Chip size="small" label={`v${version}`} />}
                    {category && (
                        <Chip size="small" variant="outlined" label={category} />
                    )}
                    <Chip
                        size="small"
                        color={running ? 'success' : 'default'}
                        label={running ? 'Running' : 'Stopped'}
                    />
                </Stack>
                {description && (
                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                        {description}
                    </Typography>
                )}
                {installDir && (
                    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', mb: 1 }}>
                        <FolderOpen size={14} />
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            {installDir}
                        </Typography>
                    </Stack>
                )}
                {httpEndpoint && (
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>
                        Endpoint: {httpEndpoint}
                    </Typography>
                )}

                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                    <Tooltip title={running ? 'Already running' : 'Start plugin process'}>
                        <span>
                            <IconButton
                                color="success"
                                aria-label="start"
                                disabled={busy || running}
                                onClick={() => run('start', start)}
                            >
                                <Play size={20} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title={running ? 'Stop plugin process' : 'Already stopped'}>
                        <span>
                            <IconButton
                                aria-label="stop"
                                disabled={busy || !running}
                                onClick={() => run('stop', stop)}
                            >
                                <Square size={20} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Restart plugin process">
                        <span>
                            <IconButton
                                aria-label="restart"
                                disabled={busy}
                                onClick={() => run('restart', restart)}
                            >
                                <RotateCcw size={20} />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>

                {actionError && (
                    <Alert severity="error" sx={{ mt: 2 }} onClose={() => setActionError(null)}>
                        {actionError}
                    </Alert>
                )}
                {actionLog && (
                    <Alert severity="success" sx={{ mt: 2 }} onClose={() => setActionLog(null)}>
                        <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit' }}>
                            {actionLog}
                        </pre>
                    </Alert>
                )}

                {!running && (
                    <Alert severity="info" sx={{ mt: 2 }}>
                        Start the plugin to dispatch tasks against it.
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
};

export const PluginRunnerPageView: React.FC = () => {
    const { '*': pluginId } = useParams();
    const navigate = useNavigate();
    const { data: livePlugins, isLoading: liveLoading } = usePlugins();
    const { data: installedRows, isLoading: dbLoading } = useInstalledFromDb();

    const livePlugin = livePlugins?.find((p) => p.plugin_id === pluginId);

    // Detail-page lookup falls back to the DB catalog so installed-but-
    // stopped plugins still get a page (with Run / Stop / Restart
    // controls). Match by plugin_id (composed cat/manifest_plugin_id)
    // OR by manifest_plugin_id directly.
    const installedRow = installedRows?.find(
        (r) =>
            r.plugin_id === pluginId ||
            r.manifest_plugin_id === pluginId,
    );

    const isLoading = liveLoading || dbLoading;
    const found = livePlugin || installedRow;

    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            <Stack
                direction="row"
                spacing={1}
                sx={{ alignItems: 'center', mb: 2 }}
            >
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
            {livePlugin && <PluginRunner plugin={livePlugin} />}
            {!livePlugin && installedRow && (
                <InstalledNotRunningPanel
                    manifestPluginId={installedRow.manifest_plugin_id ?? installedRow.plugin_id}
                    name={installedRow.name}
                    version={installedRow.version}
                    category={installedRow.category}
                    installDir={installedRow.install_dir}
                    httpEndpoint={installedRow.http_endpoint}
                    description={installedRow.description}
                />
            )}
        </Container>
    );
};

export default PluginRunnerPageView;
