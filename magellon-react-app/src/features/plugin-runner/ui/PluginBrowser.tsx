import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    Card,
    CardActionArea,
    CardContent,
    Chip,
    CircularProgress,
    FormControlLabel,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
    Alert,
    Grid,
} from '@mui/material';
import { Package, Puzzle, Square, Star, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
    usePlugins,
    useTogglePlugin,
    useSetCategoryDefault,
    useInstalledPlugins,
    useStopInstalled,
    useRemoveInstalled,
    PluginSummary,
} from '../api/PluginApi.ts';
import { BrowseCatalogDialog } from './BrowseCatalogDialog.tsx';
import { InstallPluginDialog } from './InstallPluginDialog.tsx';

interface PluginBrowserProps {
    onSelect?: (plugin: PluginSummary) => void;
}

export const PluginBrowser: React.FC<PluginBrowserProps> = ({ onSelect }) => {
    const navigate = useNavigate();
    const { data, isLoading, error } = usePlugins();
    const toggle = useTogglePlugin();
    const setDefault = useSetCategoryDefault();
    const { data: installed = [] } = useInstalledPlugins();
    const stopInstalled = useStopInstalled();
    const removeInstalled = useRemoveInstalled();
    const [query, setQuery] = useState('');
    const [installOpen, setInstallOpen] = useState(false);
    const [browseOpen, setBrowseOpen] = useState(false);

    // Count per-category impls — a "Set as default" action only makes
    // sense when ≥2 impls exist for the category. For solo impls the
    // default is unambiguous and the badge alone is enough.
    const implsByCategory = useMemo(() => {
        const m = new Map<string, number>();
        (data ?? []).forEach((p) => {
            const c = p.category?.toLowerCase();
            if (c) m.set(c, (m.get(c) ?? 0) + 1);
        });
        return m;
    }, [data]);

    const filtered = useMemo(() => {
        const all = data ?? [];
        if (!query.trim()) return all;
        const q = query.toLowerCase();
        return all.filter((p) =>
            p.plugin_id.toLowerCase().includes(q) ||
            p.name.toLowerCase().includes(q) ||
            p.description.toLowerCase().includes(q),
        );
    }, [data, query]);

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return <Alert severity="error">Failed to load plugin list.</Alert>;
    }

    const handleSelect = (p: PluginSummary) => {
        if (onSelect) return onSelect(p);
        navigate(`/en/panel/plugins/${p.plugin_id}`);
    };

    return (
        <Box>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
                <Puzzle size={22} />
                <Typography variant="h5" sx={{ flex: 1 }}>Plugins</Typography>
                <TextField
                    size="small"
                    placeholder="Search plugins…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    sx={{ width: 280 }}
                />
                <Button
                    variant="contained"
                    startIcon={<Package size={18} />}
                    onClick={() => setBrowseOpen(true)}
                >
                    Browse plugins
                </Button>
            </Stack>

            {installed.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle1" sx={{ mb: 1 }}>
                        Installed containers
                    </Typography>
                    <Stack spacing={1}>
                        {installed.map((ent) => (
                            <Card key={ent.install_id} variant="outlined">
                                <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1, gap: 1 }}>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography variant="body2" component="span">
                                            {ent.image_ref}
                                        </Typography>
                                        <Chip
                                            size="small"
                                            label={ent.state}
                                            color={
                                                ent.state === 'running'
                                                    ? 'success'
                                                    : ent.state === 'exited' || ent.state === 'stopped'
                                                    ? 'warning'
                                                    : 'default'
                                            }
                                            sx={{ ml: 1 }}
                                        />
                                        {ent.announcing_on_bus && (
                                            <Chip size="small" color="primary" label="announcing" sx={{ ml: 0.5 }} />
                                        )}
                                        {ent.error && (
                                            <Typography variant="caption" color="error" sx={{ display: 'block' }}>
                                                {ent.error}
                                            </Typography>
                                        )}
                                    </Box>
                                    <Button
                                        size="small"
                                        startIcon={<Square size={14} />}
                                        disabled={ent.state !== 'running' || stopInstalled.isLoading}
                                        onClick={() => stopInstalled.mutate(ent.install_id)}
                                    >
                                        Stop
                                    </Button>
                                    <Button
                                        size="small"
                                        color="error"
                                        startIcon={<Trash2 size={14} />}
                                        disabled={removeInstalled.isLoading}
                                        onClick={() => removeInstalled.mutate(ent.install_id)}
                                    >
                                        Remove
                                    </Button>
                                </Box>
                            </Card>
                        ))}
                    </Stack>
                </Box>
            )}

            {filtered.length === 0 ? (
                <Alert severity="info">No plugins match the current filter.</Alert>
            ) : (
                <Grid container spacing={2}>
                    {filtered.map((plugin) => {
                        const enabled = plugin.enabled ?? true;
                        const isDefault = plugin.is_default_for_category === true;
                        const siblingCount = implsByCategory.get(plugin.category?.toLowerCase() ?? '') ?? 1;
                        const canSetDefault = !isDefault && siblingCount > 1;
                        return (
                            <Grid key={plugin.plugin_id} size={{ xs: 12, sm: 6, md: 4 }}>
                                <Card variant="outlined" sx={{ height: '100%', opacity: enabled ? 1 : 0.65 }}>
                                    <CardActionArea
                                        onClick={() => handleSelect(plugin)}
                                        sx={{ height: '100%', alignItems: 'flex-start' }}
                                    >
                                        <CardContent>
                                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                                                <Typography variant="h6">{plugin.name}</Typography>
                                                <Chip size="small" label={`v${plugin.version}`} />
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
                                            <Stack direction="row" spacing={0.5} sx={{ mb: 1 }}>
                                                <Chip size="small" variant="outlined" label={plugin.category} />
                                                <Chip
                                                    size="small"
                                                    variant="outlined"
                                                    label={plugin.kind === 'broker' ? 'broker' : 'in-process'}
                                                    color={plugin.kind === 'broker' ? 'primary' : 'default'}
                                                />
                                            </Stack>
                                            <Typography variant="body2" color="text.secondary">
                                                {plugin.description}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                                {plugin.developer}
                                            </Typography>
                                        </CardContent>
                                    </CardActionArea>
                                    <Stack
                                        direction="row"
                                        spacing={1}
                                        alignItems="center"
                                        sx={{ px: 2, py: 1, borderTop: '1px solid', borderColor: 'divider' }}
                                        // MUI nests the CardActionArea's ripple above siblings; stopping
                                        // propagation lets the switch fire without also selecting the card.
                                        onClick={(e) => e.stopPropagation()}
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
                                        {canSetDefault && (
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                disabled={setDefault.isLoading}
                                                onClick={() =>
                                                    setDefault.mutate({
                                                        category: plugin.category,
                                                        pluginId: plugin.plugin_id,
                                                    })
                                                }
                                            >
                                                Set as default
                                            </Button>
                                        )}
                                    </Stack>
                                </Card>
                            </Grid>
                        );
                    })}
                </Grid>
            )}
            <BrowseCatalogDialog
                open={browseOpen}
                onClose={() => setBrowseOpen(false)}
                onOpenInstallDialog={() => setInstallOpen(true)}
            />
            <InstallPluginDialog open={installOpen} onClose={() => setInstallOpen(false)} />
        </Box>
    );
};
