import React, { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    FormControl,
    Grid,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Select,
    Stack,
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

type SortKey = 'name-asc' | 'name-desc' | 'recent' | 'category';

/**
 * Marketplace-style catalog at the top of /en/panel/plugins. Card
 * grid (matches the layout of `PluginBrowser` below it for visual
 * consistency); search + tier + category filters; sort dropdown.
 *
 * For ≤ 50 plugins (the realistic ceiling) cards beat a table on
 * scannability — name + version + tier are the things operators
 * skim first, and cards put them visually balanced rather than in
 * narrow columns.
 *
 * Already-installed plugins show "Installed" chip in place of the
 * Install button so the obvious-conflict click never goes through
 * to a 409.
 */
export const HubCatalogBrowser: React.FC = () => {
    const { data, isLoading, isError, error, refetch, isFetching } = useHubIndex();
    const { data: installed = [] } = useAdminInstalledPlugins();
    const installedIds = useMemo(
        () => new Set(installed.map((p) => p.plugin_id)),
        [installed],
    );

    const [query, setQuery] = useState('');
    const [tier, setTier] = useState<'all' | 'verified' | 'community'>('all');
    const [category, setCategory] = useState<string | null>(null);
    const [sort, setSort] = useState<SortKey>('name-asc');
    const [installTarget, setInstallTarget] = useState<HubPlugin | null>(null);

    // Per-category counts power the filter chip badges. Computed
    // BEFORE the category filter is applied so chip counts reflect
    // the unfiltered universe — you'd otherwise see "ctf · 0"
    // immediately after clicking it.
    const categoryCounts = useMemo(() => {
        const counts = new Map<string, number>();
        const plugins = data?.plugins ?? [];
        const tierFiltered = tier === 'all' ? plugins : plugins.filter((p) => p.tier === tier);
        for (const p of tierFiltered) {
            counts.set(p.category, (counts.get(p.category) ?? 0) + 1);
        }
        return counts;
    }, [data, tier]);

    const filtered = useMemo(() => {
        const all = data?.plugins ?? [];
        const q = query.trim().toLowerCase();
        return all
            .filter((p) => {
                if (tier !== 'all' && p.tier !== tier) return false;
                if (category && p.category !== category) return false;
                if (q) {
                    if (
                        !p.plugin_id.toLowerCase().includes(q) &&
                        !p.name.toLowerCase().includes(q) &&
                        !p.author.toLowerCase().includes(q) &&
                        !p.description.toLowerCase().includes(q) &&
                        !p.tags.some((t) => t.toLowerCase().includes(q))
                    ) return false;
                }
                return true;
            })
            .slice() // sort mutates; preserve filter result
            .sort((a, b) => {
                switch (sort) {
                    case 'name-desc':
                        return b.name.localeCompare(a.name);
                    case 'recent':
                        return (
                            (b.versions[0]?.published_at ?? '').localeCompare(
                                a.versions[0]?.published_at ?? '',
                            )
                        );
                    case 'category':
                        return (
                            a.category.localeCompare(b.category) ||
                            a.name.localeCompare(b.name)
                        );
                    case 'name-asc':
                    default:
                        return a.name.localeCompare(b.name);
                }
            });
    }, [data, query, tier, category, sort]);

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
                            aria-label="refresh"
                        >
                            <RefreshCw size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>

            {/* Row 1 — search + sort. Two controls that mostly answer
                "find this thing" and "what order do I want to see them in". */}
            <Stack direction="row" spacing={1.5} sx={{ mb: 1.5, alignItems: 'center' }}>
                <TextField
                    size="small"
                    placeholder="Search name, author, tag…"
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
                <FormControl size="small" sx={{ minWidth: 180 }}>
                    <InputLabel id="hub-sort-label">Sort</InputLabel>
                    <Select
                        labelId="hub-sort-label"
                        value={sort}
                        label="Sort"
                        onChange={(e) => setSort(e.target.value as SortKey)}
                    >
                        <MenuItem value="name-asc">Name (A–Z)</MenuItem>
                        <MenuItem value="name-desc">Name (Z–A)</MenuItem>
                        <MenuItem value="recent">Recently published</MenuItem>
                        <MenuItem value="category">Category</MenuItem>
                    </Select>
                </FormControl>
            </Stack>

            {/* Row 2 — tier chips. Trust signal at a glance. */}
            <Stack direction="row" spacing={0.5} sx={{ mb: 1, flexWrap: 'wrap', rowGap: 0.5 }}>
                <Chip
                    label="All tiers"
                    size="small"
                    color={tier === 'all' ? 'primary' : 'default'}
                    variant={tier === 'all' ? 'filled' : 'outlined'}
                    onClick={() => setTier('all')}
                />
                <Chip
                    label="Verified"
                    size="small"
                    color={tier === 'verified' ? 'success' : 'default'}
                    variant={tier === 'verified' ? 'filled' : 'outlined'}
                    icon={<ShieldCheck size={12} />}
                    onClick={() => setTier('verified')}
                />
                <Chip
                    label="Community"
                    size="small"
                    color={tier === 'community' ? 'warning' : 'default'}
                    variant={tier === 'community' ? 'filled' : 'outlined'}
                    onClick={() => setTier('community')}
                />
            </Stack>

            {/* Row 3 — category chips. Auto-derived from what's
                published; counts reflect tier filter. Hidden when
                only one category exists (avoids visual noise on a
                small catalog). */}
            {categoryCounts.size > 1 && (
                <Stack
                    direction="row"
                    spacing={0.5}
                    sx={{ mb: 2, flexWrap: 'wrap', rowGap: 0.5 }}
                >
                    <Chip
                        label="All categories"
                        size="small"
                        color={category === null ? 'primary' : 'default'}
                        variant={category === null ? 'filled' : 'outlined'}
                        onClick={() => setCategory(null)}
                    />
                    {Array.from(categoryCounts.entries())
                        .sort((a, b) => a[0].localeCompare(b[0]))
                        .map(([cat, count]) => (
                            <Chip
                                key={cat}
                                label={`${cat} · ${count}`}
                                size="small"
                                color={category === cat ? 'primary' : 'default'}
                                variant={category === cat ? 'filled' : 'outlined'}
                                onClick={() => setCategory(cat === category ? null : cat)}
                            />
                        ))}
                </Stack>
            )}

            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                </Box>
            ) : isError ? (
                <Alert severity="error">
                    Could not reach the hub at <code>{hubUrl()}</code>.{' '}
                    {(error as Error)?.message}
                </Alert>
            ) : filtered.length === 0 ? (
                <Alert severity="info">
                    {data?.plugins.length === 0
                        ? 'No plugins published in the hub yet.'
                        : 'No plugins match the current filter.'}
                </Alert>
            ) : (
                <Grid container spacing={2}>
                    {filtered.map((p) => (
                        <Grid key={p.plugin_id} size={{ xs: 12, sm: 6, md: 4 }}>
                            <PluginCard
                                plugin={p}
                                installed={installedIds.has(p.plugin_id)}
                                onInstall={() => setInstallTarget(p)}
                            />
                        </Grid>
                    ))}
                </Grid>
            )}

            <HubInstallDialog
                open={installTarget !== null}
                onClose={() => setInstallTarget(null)}
                plugin={installTarget}
            />
        </Box>
    );
};

interface PluginCardProps {
    plugin: HubPlugin;
    installed: boolean;
    onInstall: () => void;
}

const PluginCard: React.FC<PluginCardProps> = ({ plugin, installed, onInstall }) => {
    const v = plugin.versions[0];
    return (
        <Card
            variant="outlined"
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                opacity: installed ? 0.85 : 1,
            }}
        >
            <CardContent sx={{ flex: 1 }}>
                <Stack
                    direction="row"
                    spacing={1}
                    sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap', rowGap: 0.5 }}
                >
                    <Typography variant="h6" sx={{ flex: 1, minWidth: 0 }} noWrap>
                        {plugin.name}
                    </Typography>
                    <Chip size="small" label={`v${v.version}`} />
                </Stack>

                <Stack
                    direction="row"
                    spacing={0.5}
                    sx={{ mb: 1, flexWrap: 'wrap', rowGap: 0.5 }}
                >
                    <Chip size="small" variant="outlined" label={plugin.category} />
                    <Chip
                        size="small"
                        color={plugin.tier === 'verified' ? 'success' : 'warning'}
                        icon={
                            plugin.tier === 'verified'
                                ? <ShieldCheck size={11} />
                                : undefined
                        }
                        label={plugin.tier}
                    />
                </Stack>

                {plugin.description && (
                    <Typography
                        variant="body2"
                        sx={{
                            color: 'text.secondary',
                            mb: 1,
                            // Two-line clamp so cards stay even-height in a row.
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                        }}
                    >
                        {plugin.description}
                    </Typography>
                )}

                <Typography
                    variant="caption"
                    sx={{ color: 'text.secondary', display: 'block' }}
                >
                    {plugin.author}{plugin.license ? ` · ${plugin.license}` : ''}
                    {' · '}
                    {(v.size_bytes / 1024).toFixed(1)} KB
                </Typography>
            </CardContent>

            <Box
                sx={{
                    px: 2,
                    py: 1,
                    borderTop: '1px solid',
                    borderColor: 'divider',
                    display: 'flex',
                    justifyContent: 'flex-end',
                }}
            >
                {installed ? (
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
                        onClick={onInstall}
                    >
                        Install
                    </Button>
                )}
            </Box>
        </Card>
    );
};
