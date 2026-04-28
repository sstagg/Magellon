import React, { useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    Chip,
    CircularProgress,
    IconButton,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import { ArrowUp, Box as BoxIcon, Plus, RefreshCw, Shield, Trash2 } from 'lucide-react';
import {
    useAdminInstalledPlugins,
    useUninstallMpn,
    type InstalledPlugin,
} from '../api/installerApi.ts';
import { InstallMpnDialog } from './InstallMpnDialog.tsx';
import { UpgradeMpnDialog } from './UpgradeMpnDialog.tsx';

/**
 * Panel that drops into the Plugins page above the runtime browser.
 * Shows what's installed via the v1 admin pipeline (`.mpn` archives,
 * uv or docker), with Upgrade and Uninstall actions per row plus an
 * Install button at the top.
 *
 * Distinct from the runtime list (which shows discovered plugins on
 * the bus). A plugin can be "installed via this panel" but not
 * "live on the bus" yet during initial spawn, or "live on the bus"
 * but not "installed via this panel" if it was deployed via
 * docker-compose. The two views answer different operator
 * questions.
 */
export const AdminInstalledPanel: React.FC = () => {
    const { data: installed, isLoading, isError, refetch, isFetching } = useAdminInstalledPlugins();
    const uninstall = useUninstallMpn();

    const [installOpen, setInstallOpen] = useState(false);
    const [upgradeTarget, setUpgradeTarget] = useState<string | null>(null);
    const [pendingUninstall, setPendingUninstall] = useState<string | null>(null);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [flash, setFlash] = useState<string | null>(null);

    const handleUninstall = async (pluginId: string) => {
        setErrorMsg(null);
        setFlash(null);
        setPendingUninstall(pluginId);
        try {
            await uninstall.mutateAsync(pluginId);
            setFlash(`Uninstalled ${pluginId}`);
        } catch (err: any) {
            setErrorMsg(err?.response?.data?.detail ?? err?.message ?? 'Uninstall failed.');
        } finally {
            setPendingUninstall(null);
        }
    };

    return (
        <Box sx={{ mb: 4 }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 2 }}>
                <Shield size={20} />
                <Typography variant="h6" sx={{ flex: 1 }}>
                    Admin install
                    <Typography
                        variant="caption"
                        sx={{ ml: 1, color: 'text.secondary', fontWeight: 'normal' }}
                    >
                        v1 install pipeline — uploaded <code>.mpn</code> archives
                    </Typography>
                </Typography>
                <Tooltip title="Refresh installed list">
                    <IconButton
                        size="small"
                        onClick={() => refetch()}
                        disabled={isFetching}
                    >
                        <RefreshCw size={16} />
                    </IconButton>
                </Tooltip>
                <Button
                    variant="contained"
                    startIcon={<Plus size={16} />}
                    onClick={() => setInstallOpen(true)}
                >
                    Install plugin
                </Button>
            </Stack>

            {flash && (
                <Alert severity="success" sx={{ mb: 2 }} onClose={() => setFlash(null)}>
                    {flash}
                </Alert>
            )}
            {errorMsg && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErrorMsg(null)}>
                    {errorMsg}
                </Alert>
            )}

            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                    <CircularProgress size={24} />
                </Box>
            ) : isError ? (
                <Alert severity="error">
                    Could not load installed plugins. Check that you have
                    Administrator role — the endpoint is Casbin-gated.
                </Alert>
            ) : !installed || installed.length === 0 ? (
                <Alert severity="info">
                    No plugins installed via the admin pipeline yet. Click
                    "Install plugin" to upload a <code>.mpn</code>.
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

            <InstallMpnDialog
                open={installOpen}
                onClose={() => setInstallOpen(false)}
                onInstalled={() => setFlash('Install succeeded')}
            />
            {upgradeTarget && (
                <UpgradeMpnDialog
                    open={true}
                    pluginId={upgradeTarget}
                    onClose={() => setUpgradeTarget(null)}
                    onUpgraded={() => {
                        setFlash(`Upgraded ${upgradeTarget}`);
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
