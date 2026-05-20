/**
 * /en/panel/plugins/categories/<slug> — per-category drilldown
 * (Wave 5 Phase 19).
 *
 * Shows every backend serving one TaskCategory side-by-side, with
 * status chips (live / paused / disabled), replica count, install
 * method, and a "Set as default" action. The natural answer to the
 * operator's question "which CTF estimator should I use?".
 *
 * Reads ``GET /dispatch/{category}/backends`` via the shared
 * useCategoryBackends hook — same source the BackendPicker uses.
 *
 * Edge cases:
 *   - No backends for the category → friendly empty state with a
 *     link back to the hub catalog (operator probably hasn't
 *     installed one yet).
 *   - Unknown category slug → 404 from the API → renders an alert
 *     and a back link.
 */
import React from 'react';
import { Link as RouterLink, useParams, useNavigate } from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Container,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowLeft,
    CheckCircle2,
    Layers,
    PauseCircle,
    ServerOff,
    Star,
} from 'lucide-react';
import {
    useCategoryBackends,
    type CategoryBackendEntry,
} from '../../features/plugin-runner/api/PluginApi.ts';
import { useSetCategoryDefault } from '../../features/plugin-runner/api/PluginApi.ts';


const CategoryBackendsPage: React.FC = () => {
    const { categorySlug } = useParams<{ categorySlug: string }>();
    const navigate = useNavigate();
    const { data, isLoading, isError, error, refetch } = useCategoryBackends(categorySlug);
    const setDefault = useSetCategoryDefault();
    const [setDefaultError, setSetDefaultError] = React.useState<string | null>(null);
    const [setDefaultBusy, setSetDefaultBusy] = React.useState<string | null>(null);

    const handleSetDefault = async (pluginId: string) => {
        if (!categorySlug) return;
        setSetDefaultError(null);
        setSetDefaultBusy(pluginId);
        try {
            await setDefault.mutateAsync({
                category: categorySlug, pluginId,
            });
            await refetch();
        } catch (err: unknown) {
            const detail = (err as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail;
            setSetDefaultError(detail || 'Failed to set default.');
        } finally {
            setSetDefaultBusy(null);
        }
    };

    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
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

            {isError && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    Could not load backends for{' '}
                    <code>{categorySlug}</code>:{' '}
                    {(error as Error)?.message || 'unknown error'}
                </Alert>
            )}

            {data && (
                <>
                    <Stack
                        direction="row" spacing={1}
                        sx={{ alignItems: 'center', mb: 2, flexWrap: 'wrap' }}
                    >
                        <Layers size={22} />
                        <Typography variant="h5" sx={{ flex: 1, minWidth: 0 }}>
                            {data.category_display_name}
                        </Typography>
                        <Chip
                            size="small" variant="outlined"
                            label={`${data.backends.length} backend${data.backends.length === 1 ? '' : 's'}`}
                        />
                        {data.default_plugin_id && (
                            <Tooltip title="Operator-pinned default for this category">
                                <Chip
                                    size="small" color="success"
                                    icon={<Star size={12} />}
                                    label={`default: ${data.default_plugin_id}`}
                                />
                            </Tooltip>
                        )}
                    </Stack>

                    {setDefaultError && (
                        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSetDefaultError(null)}>
                            {setDefaultError}
                        </Alert>
                    )}

                    {data.backends.length === 0 ? (
                        <Alert severity="info">
                            No backends are currently serving this category.
                            Install a plugin tagged{' '}
                            <code>category: {data.category}</code> to get started.
                        </Alert>
                    ) : (
                        <Stack spacing={1.5}>
                            {data.backends.map((b) => (
                                <BackendCard
                                    key={`${b.plugin_id}#${b.backend_id ?? ''}`}
                                    backend={b}
                                    setDefaultBusy={setDefaultBusy === b.plugin_id}
                                    onSetDefault={() => handleSetDefault(b.plugin_id)}
                                />
                            ))}
                        </Stack>
                    )}
                </>
            )}
        </Container>
    );
};


interface BackendCardProps {
    backend: CategoryBackendEntry;
    setDefaultBusy: boolean;
    onSetDefault: () => void;
}

const BackendCard: React.FC<BackendCardProps> = ({
    backend, setDefaultBusy, onSetDefault,
}) => {
    const statusChip = (() => {
        if (!backend.is_live) {
            return (
                <Chip size="small" color="default" variant="outlined"
                      icon={<ServerOff size={12} />} label="installed (stopped)" />
            );
        }
        if (!backend.enabled) {
            return (
                <Chip size="small" color="warning" icon={<PauseCircle size={12} />}
                      label="disabled" />
            );
        }
        return (
            <Chip size="small" color="success" icon={<CheckCircle2 size={12} />}
                  label={backend.live_replicas > 1
                      ? `${backend.live_replicas} replicas live`
                      : 'live'} />
        );
    })();

    return (
        <Card variant="outlined">
            <CardContent>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                    <Typography variant="h6" sx={{ flex: 1, minWidth: 0 }}>
                        {backend.backend_id || backend.plugin_id}
                    </Typography>
                    {backend.is_default && (
                        <Chip size="small" color="success" icon={<Star size={12} />}
                              label="default" />
                    )}
                    {statusChip}
                </Stack>

                <Stack direction="row" spacing={2} sx={{ mb: 1, flexWrap: 'wrap', rowGap: 0.5 }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        <strong>plugin_id:</strong> <code>{backend.plugin_id}</code>
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        <strong>version:</strong> {backend.version || '—'}
                    </Typography>
                    {backend.install_method && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            <strong>install:</strong> {backend.install_method}
                        </Typography>
                    )}
                </Stack>

                {backend.capabilities.length > 0 && (
                    <Stack direction="row" spacing={0.5} sx={{ mb: 1, flexWrap: 'wrap', rowGap: 0.5 }}>
                        {backend.capabilities.map((c) => (
                            <Chip key={c} size="small" variant="outlined" label={c} />
                        ))}
                    </Stack>
                )}

                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 1 }}>
                    <Button
                        size="small" variant="outlined"
                        component={RouterLink}
                        to={`/en/panel/plugins/${encodeURIComponent(backend.plugin_id)}`}
                    >
                        Open runner
                    </Button>
                    {!backend.is_default && backend.is_live && backend.enabled && (
                        <Tooltip title="Make this the default backend for the category">
                            <span>
                                <Button
                                    size="small" variant="text"
                                    onClick={onSetDefault}
                                    disabled={setDefaultBusy}
                                    startIcon={<Star size={14} />}
                                >
                                    {setDefaultBusy ? 'Setting…' : 'Set as default'}
                                </Button>
                            </span>
                        </Tooltip>
                    )}
                </Stack>
            </CardContent>
        </Card>
    );
};

export default CategoryBackendsPage;
