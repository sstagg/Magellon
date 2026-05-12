/**
 * /panel/plugins/registry — operator's view of the federated plugin
 * registry (PE4 acceptance).
 *
 * Three panes driven by one ``GET /plugins/registry/index`` call:
 *
 *   - Browse — every plugin the hub publishes. Filter by category,
 *     subject tag (open follow-up), installed-state, verified flag.
 *   - Update inbox — installed plugins with newer hub versions.
 *   - Local-only — installed plugins not on the hub (air-gapped or
 *     custom). Operators see them so an unintentionally-divergent
 *     install doesn't slip past.
 *
 * Pinning (version-pin / unpin) is on the plan's PE4 spec but needs
 * a backend pin-persistence table to survive restarts — that's a
 * follow-up PR. For now the page shows current installed versions
 * read-only.
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
    Container,
    Divider,
    Stack,
    Tab,
    Tabs,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AlertCircle,
    BadgeCheck,
    Cloud,
    Download,
    HardDrive,
    Inbox,
    Puzzle,
    Search,
} from 'lucide-react';

import {
    type RegistryPlugin,
    useRegistryIndex,
} from '../../features/plugin-registry/api/RegistryApi.ts';


type Tab = 'browse' | 'updates' | 'local';


// ---------------------------------------------------------------------------
// Small per-plugin card
// ---------------------------------------------------------------------------


const PluginRegistryCard: React.FC<{ plugin: RegistryPlugin }> = ({ plugin }) => {
    return (
        <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                    <Typography variant="h6" sx={{ flex: 1 }}>
                        {plugin.display_name}
                    </Typography>
                    {plugin.is_verified && (
                        <Tooltip title="Verified by the hub" placement="top">
                            <Chip
                                size="small"
                                color="success"
                                icon={<BadgeCheck size={14} />}
                                label="Verified"
                            />
                        </Tooltip>
                    )}
                    {plugin.source === 'local-only' && (
                        <Tooltip title="Installed locally but not in the hub catalog">
                            <Chip
                                size="small"
                                variant="outlined"
                                icon={<HardDrive size={12} />}
                                label="local"
                            />
                        </Tooltip>
                    )}
                </Stack>
                <Stack direction="row" spacing={0.5} sx={{ mb: 1, flexWrap: 'wrap' }} useFlexGap>
                    <Chip size="small" variant="outlined" label={plugin.plugin_id} />
                    {plugin.category && (
                        <Chip size="small" variant="outlined" label={plugin.category} />
                    )}
                </Stack>

                <Stack spacing={0.5} sx={{ mt: 1 }}>
                    {plugin.latest_hub_version && (
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Cloud size={14} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Hub latest:
                            </Typography>
                            <Chip size="small" label={plugin.latest_hub_version} />
                        </Stack>
                    )}
                    {plugin.installed_version && (
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Download size={14} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Installed:
                            </Typography>
                            <Chip
                                size="small"
                                label={plugin.installed_version}
                                color={plugin.update_available ? 'warning' : 'default'}
                                variant={plugin.update_available ? 'filled' : 'outlined'}
                            />
                            {plugin.install_method && (
                                <Chip
                                    size="small"
                                    variant="outlined"
                                    label={plugin.install_method}
                                />
                            )}
                        </Stack>
                    )}
                    {plugin.update_available && (
                        <Typography variant="caption" sx={{ color: 'warning.main' }}>
                            Update available — {plugin.installed_version} →{' '}
                            {plugin.latest_hub_version}
                        </Typography>
                    )}
                </Stack>
            </CardContent>
        </Card>
    );
};


// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------


export const PluginRegistryPage: React.FC = () => {
    const { data, isLoading, error } = useRegistryIndex();
    const [tab, setTab] = useState<Tab>('browse');
    const [query, setQuery] = useState('');

    const filtered = useMemo(() => {
        const all = data?.plugins ?? [];
        let scope = all;
        if (tab === 'updates') {
            scope = all.filter((p) => p.update_available);
        } else if (tab === 'local') {
            scope = all.filter((p) => p.source === 'local-only');
        } else {
            // Browse — hub plugins only (local-only has its own tab).
            scope = all.filter((p) => p.source === 'hub');
        }
        if (!query.trim()) return scope;
        const q = query.toLowerCase();
        return scope.filter(
            (p) =>
                p.plugin_id.toLowerCase().includes(q) ||
                p.display_name.toLowerCase().includes(q) ||
                (p.category ?? '').toLowerCase().includes(q),
        );
    }, [data, tab, query]);

    const updateCount = useMemo(
        () => (data?.plugins ?? []).filter((p) => p.update_available).length,
        [data],
    );
    const localOnlyCount = useMemo(
        () => (data?.plugins ?? []).filter((p) => p.source === 'local-only').length,
        [data],
    );

    if (isLoading) {
        return (
            <Container maxWidth="lg" sx={{ py: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                    <CircularProgress />
                </Box>
            </Container>
        );
    }

    if (error) {
        return (
            <Container maxWidth="lg" sx={{ py: 3 }}>
                <Alert severity="error">Failed to load the plugin registry.</Alert>
            </Container>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 3 }}>
                <Puzzle size={26} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h5">Plugin Registry</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Browse the hub, see what needs updating, spot
                        local-only installs.
                    </Typography>
                </Box>
                <TextField
                    size="small"
                    placeholder="Search…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    sx={{ width: 240 }}
                    slotProps={{
                        input: {
                            startAdornment: <Search size={14} style={{ marginRight: 6 }} />,
                        },
                    }}
                />
            </Stack>

            {data?.hub_status && data.hub_status !== 'ok' && (
                <Alert
                    severity="warning"
                    icon={<AlertCircle size={18} />}
                    sx={{ mb: 2 }}
                >
                    Hub status: {data.hub_status}
                    {data.hub_error ? ` — ${data.hub_error}` : ''}.
                    Local-only plugins still surface below.
                </Alert>
            )}

            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v as Tab)}
                sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
            >
                <Tab
                    value="browse"
                    label={
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Cloud size={14} />
                            <span>Browse</span>
                        </Stack>
                    }
                />
                <Tab
                    value="updates"
                    label={
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Inbox size={14} />
                            <span>Update inbox</span>
                            {updateCount > 0 && (
                                <Chip size="small" color="warning" label={updateCount} />
                            )}
                        </Stack>
                    }
                />
                <Tab
                    value="local"
                    label={
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <HardDrive size={14} />
                            <span>Local-only</span>
                            {localOnlyCount > 0 && (
                                <Chip size="small" label={localOnlyCount} />
                            )}
                        </Stack>
                    }
                />
            </Tabs>

            {filtered.length === 0 ? (
                <Alert severity="info">
                    {tab === 'updates' && 'No updates available — everything is at latest.'}
                    {tab === 'local' && 'No local-only plugins detected.'}
                    {tab === 'browse' && (data?.hub_status === 'ok'
                        ? 'Hub returned no plugins matching the filter.'
                        : 'Hub catalog unreachable — no plugins to browse.')}
                </Alert>
            ) : (
                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' },
                        gap: 2,
                    }}
                >
                    {filtered.map((p) => (
                        <PluginRegistryCard key={p.plugin_id} plugin={p} />
                    ))}
                </Box>
            )}

            <Divider sx={{ my: 3 }} />
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Hub: {data?.hub_url}
            </Typography>
        </Container>
    );
};

export default PluginRegistryPage;
