/**
 * "Installed" tab — the main view of the plugins page.
 *
 * Reads from GET /plugins/db (the DB-backed catalog with physical
 * location info) and overlays runtime status from the live registry.
 * Each row shows:
 *
 *   - identity (name, version, category)
 *   - physical location (docker:image / dir:path / container:id) so
 *     the operator can see where each plugin lives, per the user's
 *     "it can be inside a directory or inside a container" point
 *   - Conditions[] chip cluster (PM7a)
 *   - "Update available" chip (PM7d)
 *   - Replicas drilldown drawer (PM7c)
 *   - Enable / Disable toggle, Set-default button
 *   - Uninstall button
 */
import React, { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    FormControlLabel,
    Grid,
    IconButton,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Boxes,
    ChevronDown,
    ChevronUp,
    Container as ContainerIcon,
    FolderOpen,
    Star,
    Trash2,
} from 'lucide-react';
import {
    useInstalledFromDb,
    usePluginStatus,
    usePluginUpdates,
    useTogglePlugin,
    useSetCategoryDefault,
    type InstalledPluginRow,
} from '../api/PluginApi.ts';
import { useUninstallMpn } from '../../plugin-installer/api/installerApi.ts';
import { PluginConditions } from './PluginConditions.tsx';
import { PluginReplicas } from './PluginReplicas.tsx';
import { PluginUpdateChip } from './PluginUpdateChip.tsx';

/** Per-card Conditions cluster — each card fetches its own status. */
const ConditionsForCard: React.FC<{ pluginId: string }> = ({ pluginId }) => {
    const { data } = usePluginStatus(pluginId);
    return <PluginConditions conditions={data} />;
};

/** Render the physical-location chip(s) appropriate for this plugin. */
const InstallLocationChip: React.FC<{ row: InstalledPluginRow }> = ({ row }) => {
    if (row.install_method === 'docker' && row.image_ref) {
        return (
            <Tooltip
                title={
                    row.container_ref
                        ? `Container ${row.container_ref}`
                        : `Image ${row.image_ref}`
                }
            >
                <Chip
                    size="small"
                    icon={<ContainerIcon size={12} />}
                    label={row.image_ref}
                    variant="outlined"
                    color="primary"
                />
            </Tooltip>
        );
    }
    if (row.install_method === 'uv' && row.install_dir) {
        return (
            <Tooltip title={row.install_dir}>
                <Chip
                    size="small"
                    icon={<FolderOpen size={12} />}
                    label={row.install_dir.split(/[\\/]/).pop() ?? row.install_dir}
                    variant="outlined"
                />
            </Tooltip>
        );
    }
    if (row.install_method) {
        return (
            <Chip size="small" label={row.install_method} variant="outlined" />
        );
    }
    return null;
};

export const InstalledPluginsView: React.FC = () => {
    const { data: rows, isLoading, error } = useInstalledFromDb();
    const toggle = useTogglePlugin();
    const setDefault = useSetCategoryDefault();
    const uninstall = useUninstallMpn();
    const { data: updates = [] } = usePluginUpdates();
    const [query, setQuery] = useState('');
    const [expandedReplicas, setExpandedReplicas] = useState<Record<string, boolean>>({});
    const [actionMessage, setActionMessage] = useState<
        { severity: 'success' | 'error'; text: string } | null
    >(null);
    const [pendingUninstall, setPendingUninstall] = useState<string | null>(null);

    const updatesByPluginId = useMemo(() => {
        const m = new Map<string, typeof updates[number]>();
        updates.forEach((u) => m.set(u.plugin_id, u));
        return m;
    }, [updates]);

    const implsByCategory = useMemo(() => {
        const m = new Map<string, number>();
        (rows ?? []).forEach((p) => {
            const c = p.category?.toLowerCase();
            if (c) m.set(c, (m.get(c) ?? 0) + 1);
        });
        return m;
    }, [rows]);

    const filtered = useMemo(() => {
        const all = rows ?? [];
        if (!query.trim()) return all;
        const q = query.toLowerCase();
        return all.filter(
            (p) =>
                p.plugin_id.toLowerCase().includes(q) ||
                p.name.toLowerCase().includes(q) ||
                p.description.toLowerCase().includes(q),
        );
    }, [rows, query]);

    const toggleReplicas = (pluginId: string) =>
        setExpandedReplicas((s) => ({ ...s, [pluginId]: !s[pluginId] }));

    const handleUninstall = async (manifestPluginId: string | null | undefined, label: string) => {
        if (!manifestPluginId) {
            setActionMessage({
                severity: 'error',
                text: `Cannot uninstall ${label}: no manifest_plugin_id (legacy row).`,
            });
            return;
        }
        if (!window.confirm(`Uninstall ${label}? This stops the plugin and removes it.`)) return;
        setActionMessage(null);
        setPendingUninstall(manifestPluginId);
        try {
            await uninstall.mutateAsync(manifestPluginId);
            setActionMessage({ severity: 'success', text: `Uninstalled ${label}` });
        } catch (err: any) {
            setActionMessage({
                severity: 'error',
                text: err?.response?.data?.detail ?? err?.message ?? 'Uninstall failed.',
            });
        } finally {
            setPendingUninstall(null);
        }
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
            </Box>
        );
    }
    if (error) {
        return <Alert severity="error">Failed to load installed plugins.</Alert>;
    }

    return (
        <Box>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 3 }}>
                <Boxes size={22} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6">Installed plugins</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Registered in the database — running on the bus or
                        ready to start. {(rows ?? []).length} total.
                    </Typography>
                </Box>
                <TextField
                    size="small"
                    placeholder="Search plugins…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    sx={{ width: 280 }}
                />
            </Stack>

            {actionMessage && (
                <Alert
                    severity={actionMessage.severity}
                    sx={{ mb: 2 }}
                    onClose={() => setActionMessage(null)}
                >
                    {actionMessage.text}
                </Alert>
            )}

            {filtered.length === 0 ? (
                <Alert severity="info">
                    No installed plugins. Use <strong>Upload archive</strong> or{' '}
                    <strong>Browse hub</strong> above to install one.
                </Alert>
            ) : (
                <Grid container spacing={2}>
                    {filtered.map((plugin) => {
                        const enabled = plugin.enabled ?? true;
                        const isDefault = plugin.is_default_for_category === true;
                        const siblingCount =
                            implsByCategory.get(plugin.category?.toLowerCase() ?? '') ?? 1;
                        const canSetDefault = !isDefault && siblingCount > 1;
                        const update = updatesByPluginId.get(plugin.plugin_id);
                        const expanded = !!expandedReplicas[plugin.plugin_id];
                        return (
                            <Grid key={plugin.plugin_id} size={{ xs: 12, sm: 6, md: 4 }}>
                                <Card
                                    variant="outlined"
                                    sx={{ height: '100%', opacity: enabled ? 1 : 0.65 }}
                                >
                                    <CardContent>
                                        <Stack
                                            direction="row"
                                            spacing={1}
                                            sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap' }}
                                        >
                                            <Typography variant="h6">{plugin.name}</Typography>
                                            {plugin.version && (
                                                <Chip size="small" label={`v${plugin.version}`} />
                                            )}
                                            <PluginUpdateChip update={update} />
                                            {isDefault && (
                                                <Tooltip title="Default impl for this category">
                                                    <Chip
                                                        size="small"
                                                        color="success"
                                                        icon={<Star size={14} />}
                                                        label="Default"
                                                    />
                                                </Tooltip>
                                            )}
                                        </Stack>
                                        <Stack
                                            direction="row"
                                            spacing={0.5}
                                            sx={{ mb: 1, flexWrap: 'wrap' }}
                                            useFlexGap
                                        >
                                            {plugin.category && (
                                                <Chip
                                                    size="small"
                                                    variant="outlined"
                                                    label={plugin.category}
                                                />
                                            )}
                                            <InstallLocationChip row={plugin} />
                                        </Stack>
                                        {plugin.description && (
                                            <Typography
                                                variant="body2"
                                                sx={{ color: 'text.secondary' }}
                                            >
                                                {plugin.description}
                                            </Typography>
                                        )}
                                        {plugin.developer && (
                                            <Typography
                                                variant="caption"
                                                sx={{
                                                    color: 'text.secondary',
                                                    mt: 1,
                                                    display: 'block',
                                                }}
                                            >
                                                {plugin.developer}
                                            </Typography>
                                        )}
                                        <ConditionsForCard pluginId={plugin.plugin_id} />
                                    </CardContent>
                                    <Stack
                                        direction="row"
                                        spacing={1}
                                        sx={{
                                            alignItems: 'center',
                                            px: 2,
                                            py: 1,
                                            borderTop: '1px solid',
                                            borderColor: 'divider',
                                            flexWrap: 'wrap',
                                        }}
                                    >
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    size="small"
                                                    checked={enabled}
                                                    disabled={toggle.isLoading}
                                                    onChange={(e) =>
                                                        toggle.mutate({
                                                            pluginId: plugin.plugin_id,
                                                            enabled: e.target.checked,
                                                        })
                                                    }
                                                />
                                            }
                                            label={enabled ? 'Enabled' : 'Disabled'}
                                            sx={{ m: 0, flex: 1 }}
                                        />
                                        {canSetDefault && plugin.category && (
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                disabled={setDefault.isLoading}
                                                onClick={() =>
                                                    setDefault.mutate({
                                                        category: plugin.category!,
                                                        pluginId: plugin.plugin_id,
                                                    })
                                                }
                                            >
                                                Set as default
                                            </Button>
                                        )}
                                        <Tooltip
                                            title={
                                                expanded
                                                    ? 'Hide replicas'
                                                    : 'Show replicas'
                                            }
                                        >
                                            <IconButton
                                                size="small"
                                                onClick={() => toggleReplicas(plugin.plugin_id)}
                                                aria-label="toggle replicas"
                                                aria-expanded={expanded}
                                            >
                                                {expanded ? (
                                                    <ChevronUp size={16} />
                                                ) : (
                                                    <ChevronDown size={16} />
                                                )}
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip
                                            title={
                                                plugin.manifest_plugin_id
                                                    ? `Uninstall ${plugin.name}`
                                                    : 'Cannot uninstall: no manifest_plugin_id'
                                            }
                                        >
                                            <span>
                                                <IconButton
                                                    size="small"
                                                    color="error"
                                                    aria-label="uninstall"
                                                    disabled={
                                                        !plugin.manifest_plugin_id ||
                                                        pendingUninstall === plugin.manifest_plugin_id
                                                    }
                                                    onClick={() =>
                                                        handleUninstall(
                                                            plugin.manifest_plugin_id,
                                                            plugin.name,
                                                        )
                                                    }
                                                >
                                                    <Trash2 size={16} />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                    </Stack>
                                    <Collapse in={expanded} unmountOnExit>
                                        <Box
                                            sx={{
                                                px: 2,
                                                py: 1,
                                                borderTop: '1px solid',
                                                borderColor: 'divider',
                                            }}
                                        >
                                            <Typography
                                                variant="caption"
                                                color="text.secondary"
                                                sx={{ display: 'block', mb: 0.5 }}
                                            >
                                                Replicas
                                            </Typography>
                                            <PluginReplicas pluginId={plugin.plugin_id} />
                                        </Box>
                                    </Collapse>
                                </Card>
                            </Grid>
                        );
                    })}
                </Grid>
            )}
        </Box>
    );
};
