import React, { useRef, useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Card,
    Chip,
    CircularProgress,
    Collapse,
    IconButton,
    LinearProgress,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowUp,
    Box as BoxIcon,
    ChevronDown,
    ChevronUp,
    Package,
    RefreshCw,
    Shield,
    Trash2,
    Upload,
    X,
} from 'lucide-react';
import {
    useAdminInstalledPlugins,
    useInstallMpn,
    useUninstallMpn,
    type InstalledPlugin,
    type InstallResponse,
} from '../api/installerApi.ts';
import { UpgradeMpnDialog } from './UpgradeMpnDialog.tsx';

/**
 * Two responsibilities:
 *
 *   1. **Install from file** — inline drop zone at the top. Drop a
 *      ``.mpn`` or click to browse → upload runs in-place; progress
 *      and result render below the zone. No modal indirection
 *      (per UX feedback — the modal-then-pick-file flow added a
 *      click for no benefit).
 *
 *   2. **Manage installed plugins** — list of plugins live via the
 *      v1 admin pipeline, each row offering Upgrade and Uninstall.
 *      Upgrade still uses a modal because it's plugin-scoped and
 *      benefits from showing manifest summary + force_downgrade
 *      toggle; "I have a file, install it" doesn't need that.
 */
export const AdminInstalledPanel: React.FC = () => {
    const { data: installed, isLoading, isError, refetch, isFetching } =
        useAdminInstalledPlugins();
    const installMpn = useInstallMpn();
    const uninstall = useUninstallMpn();

    // Install-from-file state — kept INLINE, not in a modal.
    const fileInput = useRef<HTMLInputElement | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [installError, setInstallError] = useState<string | null>(null);
    const [installResult, setInstallResult] = useState<InstallResponse | null>(null);
    const [logsOpen, setLogsOpen] = useState(false);

    // Per-row state.
    const [upgradeTarget, setUpgradeTarget] = useState<string | null>(null);
    const [pendingUninstall, setPendingUninstall] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<{ severity: 'success' | 'error'; text: string } | null>(null);

    const acceptFile = (file: File | null) => {
        setInstallError(null);
        setInstallResult(null);
        if (!file) {
            setPendingFile(null);
            return;
        }
        const ok = file.name.endsWith('.mpn') ||
                   file.name.endsWith('.magplugin') ||
                   file.name.endsWith('.zip');
        if (!ok) {
            setInstallError(`Expected a .mpn archive; got ${file.name}.`);
            setPendingFile(null);
            return;
        }
        setPendingFile(file);
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setDragOver(false);
        acceptFile(e.dataTransfer.files[0] ?? null);
    };

    const handleInstall = async () => {
        if (!pendingFile) return;
        setInstallError(null);
        setInstallResult(null);
        try {
            const result = await installMpn.mutateAsync(pendingFile);
            setInstallResult(result);
            setPendingFile(null);
        } catch (err: any) {
            setInstallError(err?.response?.data?.detail ?? err?.message ?? 'Install failed.');
        }
    };

    const handleUninstall = async (pluginId: string) => {
        setActionMessage(null);
        setPendingUninstall(pluginId);
        try {
            await uninstall.mutateAsync(pluginId);
            setActionMessage({ severity: 'success', text: `Uninstalled ${pluginId}` });
        } catch (err: any) {
            setActionMessage({
                severity: 'error',
                text: err?.response?.data?.detail ?? err?.message ?? 'Uninstall failed.',
            });
        } finally {
            setPendingUninstall(null);
        }
    };

    const installing = installMpn.isLoading;

    return (
        <Box sx={{ mb: 4 }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 2 }}>
                <Shield size={20} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6">Admin install</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Install <code>.mpn</code> archives directly · manage installed plugins
                    </Typography>
                </Box>
                <Tooltip title="Refresh installed list">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => refetch()}
                            disabled={isFetching}
                            aria-label="refresh"
                        >
                            <RefreshCw size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>

            {/* Inline drop zone — no modal. Drop or click to pick a
                file; install runs in-place below. */}
            <Box
                onDragOver={(e) => {
                    e.preventDefault();
                    if (!installing) setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => !installing && handleDrop(e)}
                onClick={() => !installing && fileInput.current?.click()}
                role="button"
                tabIndex={0}
                aria-label="Drop or browse for a .mpn archive"
                sx={{
                    border: '2px dashed',
                    borderColor: dragOver ? 'primary.main' : 'divider',
                    bgcolor: dragOver ? 'action.hover' : 'background.default',
                    borderRadius: 2,
                    p: 3,
                    textAlign: 'center',
                    cursor: installing ? 'not-allowed' : 'pointer',
                    transition: 'background-color 150ms, border-color 150ms',
                    opacity: installing ? 0.5 : 1,
                    mb: pendingFile || installing || installResult || installError ? 2 : 0,
                }}
            >
                <Upload size={28} style={{ opacity: 0.5, marginBottom: 4 }} />
                <Typography variant="body2">
                    Drop a <code>.mpn</code> archive here, or <strong>click to browse</strong>
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    The host's capabilities decide whether the plugin installs via uv or docker.
                </Typography>
                <input
                    ref={fileInput}
                    type="file"
                    accept=".mpn,.magplugin,.zip"
                    style={{ display: 'none' }}
                    onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
                />
            </Box>

            {/* Pending file — confirm step. Single click installs. */}
            {pendingFile && !installing && (
                <Card variant="outlined" sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5, gap: 1 }}>
                        <Package size={18} />
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography variant="body2" noWrap>
                                {pendingFile.name}
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                {(pendingFile.size / 1024).toFixed(1)} KB
                            </Typography>
                        </Box>
                        <IconButton
                            size="small"
                            onClick={() => setPendingFile(null)}
                            aria-label="discard pending file"
                        >
                            <X size={16} />
                        </IconButton>
                        <Button
                            variant="contained"
                            size="small"
                            startIcon={<Upload size={14} />}
                            onClick={handleInstall}
                        >
                            Install
                        </Button>
                    </Box>
                </Card>
            )}

            {/* In-flight progress. */}
            {installing && (
                <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                        Installing {pendingFile?.name ?? 'plugin'}…
                    </Typography>
                    <LinearProgress />
                </Box>
            )}

            {/* Result — alert + collapsible logs. Stays visible until
                next install or operator dismisses. */}
            {installError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setInstallError(null)}>
                    {installError}
                </Alert>
            )}
            {installResult?.success && (
                <Alert
                    severity="success"
                    sx={{ mb: 2 }}
                    onClose={() => { setInstallResult(null); setLogsOpen(false); }}
                    action={
                        installResult.logs ? (
                            <Button
                                size="small"
                                onClick={() => setLogsOpen((o) => !o)}
                                endIcon={logsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            >
                                Logs
                            </Button>
                        ) : null
                    }
                >
                    <AlertTitle>{installResult.plugin_id} installed</AlertTitle>
                    via {installResult.install_method}
                    {installResult.install_dir && (
                        <> at <code>{installResult.install_dir}</code></>
                    )}
                    <Collapse in={logsOpen}>
                        <Box
                            component="pre"
                            sx={{
                                mt: 1,
                                bgcolor: 'background.default',
                                border: '1px solid',
                                borderColor: 'divider',
                                borderRadius: 1,
                                p: 1,
                                fontSize: 11,
                                maxHeight: 180,
                                overflow: 'auto',
                            }}
                        >
                            {installResult.logs}
                        </Box>
                    </Collapse>
                </Alert>
            )}

            {actionMessage && (
                <Alert
                    severity={actionMessage.severity}
                    sx={{ mb: 2 }}
                    onClose={() => setActionMessage(null)}
                >
                    {actionMessage.text}
                </Alert>
            )}

            {/* Installed list. */}
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
                Installed plugins
            </Typography>
            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                    <CircularProgress size={24} />
                </Box>
            ) : isError ? (
                <Alert severity="error">
                    Could not load installed plugins. Check that you have the
                    Administrator role — the endpoint is Casbin-gated.
                </Alert>
            ) : !installed || installed.length === 0 ? (
                <Alert severity="info" variant="outlined">
                    No plugins installed yet. Drop a <code>.mpn</code> above, or pick one
                    from the catalog.
                </Alert>
            ) : (
                <Stack spacing={1}>
                    {installed.map((entry) => (
                        <InstalledRow
                            key={entry.plugin_id}
                            entry={entry}
                            onUpgrade={() => setUpgradeTarget(entry.plugin_id)}
                            onUninstall={() => handleUninstall(entry.plugin_id)}
                            uninstalling={pendingUninstall === entry.plugin_id}
                        />
                    ))}
                </Stack>
            )}

            {upgradeTarget && (
                <UpgradeMpnDialog
                    open={true}
                    pluginId={upgradeTarget}
                    onClose={() => setUpgradeTarget(null)}
                    onUpgraded={() => {
                        setActionMessage({
                            severity: 'success',
                            text: `Upgraded ${upgradeTarget}`,
                        });
                        setUpgradeTarget(null);
                    }}
                />
            )}
        </Box>
    );
};

interface InstalledRowProps {
    entry: InstalledPlugin;
    onUpgrade: () => void;
    onUninstall: () => void;
    uninstalling: boolean;
}

const InstalledRow: React.FC<InstalledRowProps> = ({
    entry,
    onUpgrade,
    onUninstall,
    uninstalling,
}) => {
    return (
        <Card variant="outlined">
            <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5, gap: 1 }}>
                <BoxIcon size={16} style={{ opacity: 0.6 }} />
                <Typography variant="body1" sx={{ flex: 1 }}>
                    <code>{entry.plugin_id}</code>
                </Typography>
                <Chip
                    size="small"
                    label={entry.install_method}
                    color={entry.install_method === 'docker' ? 'primary' : 'default'}
                    variant="outlined"
                />
                <Tooltip title="Upload a newer version's .mpn">
                    <span>
                        <Button
                            size="small"
                            startIcon={<ArrowUp size={14} />}
                            onClick={onUpgrade}
                            disabled={uninstalling}
                        >
                            Upgrade
                        </Button>
                    </span>
                </Tooltip>
                <Tooltip title="Stop + remove from disk">
                    <span>
                        <Button
                            size="small"
                            color="error"
                            startIcon={<Trash2 size={14} />}
                            onClick={onUninstall}
                            disabled={uninstalling}
                        >
                            {uninstalling ? 'Uninstalling…' : 'Uninstall'}
                        </Button>
                    </span>
                </Tooltip>
            </Box>
        </Card>
    );
};
