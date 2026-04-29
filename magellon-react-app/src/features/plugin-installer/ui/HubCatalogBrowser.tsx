import React, { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    IconButton,
    InputAdornment,
    Paper,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    CheckCircle2,
    Cloud,
    Download,
    RefreshCw,
    Search,
    ShieldCheck,
} from 'lucide-react';
import {
    hubUrl,
    useHubIndex,
    type HubPlugin,
} from '../api/hubApi.ts';
import { useAdminInstalledPlugins } from '../api/installerApi.ts';
import { HubInstallDialog } from './HubInstallDialog.tsx';

/**
 * Catalog browser — the marketplace-style view at the top of the
 * Plugins page. Fetches the public catalog from the configured hub
 * (configs.json → HUB_URL, default https://demo.magellon.org) and
 * renders one row per plugin with an Install action.
 *
 * Already-installed plugins (from the local /admin/plugins/installed
 * list) get a "Installed" chip instead of an Install button — saves
 * the operator the click that'd return 409 anyway.
 */
export const HubCatalogBrowser: React.FC = () => {
    const { data, isLoading, isError, error, refetch, isFetching } = useHubIndex();
    const { data: installed = [] } = useAdminInstalledPlugins();
    const installedIds = useMemo(
        () => new Set(installed.map((p) => p.plugin_id)),
        [installed],
    );

    const [query, setQuery] = useState('');
    const [tierFilter, setTierFilter] = useState<'all' | 'verified' | 'community'>('all');
    const [installTarget, setInstallTarget] = useState<HubPlugin | null>(null);

    const filtered = useMemo(() => {
        const all = data?.plugins ?? [];
        return all.filter((p) => {
            if (tierFilter !== 'all' && p.tier !== tierFilter) return false;
            if (query.trim()) {
                const q = query.toLowerCase();
                if (
                    !p.plugin_id.toLowerCase().includes(q) &&
                    !p.name.toLowerCase().includes(q) &&
                    !p.author.toLowerCase().includes(q) &&
                    !p.description.toLowerCase().includes(q) &&
                    !p.tags.some((t) => t.toLowerCase().includes(q))
                ) return false;
            }
            return true;
        });
    }, [data, query, tierFilter]);

    return (
        <Box sx={{ mb: 4 }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 2 }}>
                <Cloud size={22} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6">Plugin catalog</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Available from <code>{hubUrl()}</code>
                    </Typography>
                </Box>
                <Tooltip title="Refresh catalog">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => refetch()}
                            disabled={isFetching}
                        >
                            <RefreshCw size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>

            <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center' }}>
                <TextField
                    size="small"
                    placeholder="Search name, author, description, tag…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    sx={{ flex: 1 }}
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <Search size={16} />
                                </InputAdornment>
                            ),
                        },
                    }}
                />
                <Chip
                    label="All"
                    size="small"
                    color={tierFilter === 'all' ? 'primary' : 'default'}
                    variant={tierFilter === 'all' ? 'filled' : 'outlined'}
                    onClick={() => setTierFilter('all')}
                />
                <Chip
                    label="Verified"
                    size="small"
                    color={tierFilter === 'verified' ? 'success' : 'default'}
                    variant={tierFilter === 'verified' ? 'filled' : 'outlined'}
                    icon={<ShieldCheck size={12} />}
                    onClick={() => setTierFilter('verified')}
                />
                <Chip
                    label="Community"
                    size="small"
                    color={tierFilter === 'community' ? 'warning' : 'default'}
                    variant={tierFilter === 'community' ? 'filled' : 'outlined'}
                    onClick={() => setTierFilter('community')}
                />
            </Stack>

            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                </Box>
            ) : isError ? (
                <Alert severity="error">
                    Could not reach the hub at <code>{hubUrl()}</code>.{' '}
                    {(error as Error)?.message}
                    {' '}Check the <code>HUB_URL</code> in
                    <code> configs.json</code> or your network.
                </Alert>
            ) : filtered.length === 0 ? (
                <Alert severity="info">
                    {data?.plugins.length === 0
                        ? 'No plugins published in the hub yet.'
                        : 'No plugins match the current filter.'}
                </Alert>
            ) : (
                <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Plugin</TableCell>
                                <TableCell>Author</TableCell>
                                <TableCell>Category</TableCell>
                                <TableCell align="right">Version</TableCell>
                                <TableCell>License</TableCell>
                                <TableCell>Tier</TableCell>
                                <TableCell align="right">Size</TableCell>
                                <TableCell align="right">Action</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filtered.map((p) => {
                                const v = p.versions[0];
                                const isInstalled = installedIds.has(p.plugin_id);
                                return (
                                    <TableRow key={p.plugin_id} hover>
                                        <TableCell sx={{ minWidth: 220 }}>
                                            <Typography variant="body2">
                                                {p.name}
                                            </Typography>
                                            <Typography
                                                variant="caption"
                                                sx={{ color: 'text.secondary' }}
                                            >
                                                <code>{p.plugin_id}</code>
                                                {p.description && ` · ${p.description.slice(0, 80)}${p.description.length > 80 ? '…' : ''}`}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>{p.author || '—'}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={p.category}
                                                size="small"
                                                variant="outlined"
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            <code>{v.version}</code>
                                            {p.versions.length > 1 && (
                                                <Typography
                                                    variant="caption"
                                                    sx={{ color: 'text.secondary', display: 'block' }}
                                                >
                                                    {p.versions.length} versions
                                                </Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>{p.license || '—'}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={p.tier}
                                                size="small"
                                                color={p.tier === 'verified' ? 'success' : 'warning'}
                                                icon={p.tier === 'verified' ? <ShieldCheck size={11} /> : undefined}
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            {(v.size_bytes / 1024).toFixed(1)} KB
                                        </TableCell>
                                        <TableCell align="right">
                                            {isInstalled ? (
                                                <Tooltip title="Already installed — uninstall first to reinstall, or use Upgrade for a different version">
                                                    <Chip
                                                        size="small"
                                                        color="default"
                                                        icon={<CheckCircle2 size={12} />}
                                                        label="Installed"
                                                    />
                                                </Tooltip>
                                            ) : (
                                                <Button
                                                    size="small"
                                                    variant="contained"
                                                    startIcon={<Download size={14} />}
                                                    onClick={() => setInstallTarget(p)}
                                                >
                                                    Install
                                                </Button>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}

            <HubInstallDialog
                open={installTarget !== null}
                onClose={() => setInstallTarget(null)}
                plugin={installTarget}
            />
        </Box>
    );
};
