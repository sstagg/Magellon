/**
 * "Catalog" tab — local archives uploaded but not yet installed.
 *
 * Distinct from "Installed" (DB rows with running processes/containers
 * — `Plugin` table) and from "Hub" (remote registry). The catalog is
 * the operator's local staging area: drop a `.mpn` here, decide later.
 *
 * Backed by GET /plugins/catalog (legacy v0 store at
 * `core/plugin_catalog.py`). The "Install" button kicks off the v0
 * install flow; the v1 admin pipeline ships independently via the
 * Upload-archive modal.
 */
import React from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    Chip,
    CircularProgress,
    Stack,
    Typography,
} from '@mui/material';
import { Archive, Download, Trash2 } from 'lucide-react';
import {
    useCatalog,
    useDeleteCatalog,
    useInstallCatalog,
} from '../api/PluginApi.ts';

export const CatalogView: React.FC = () => {
    const { data, isLoading, error } = useCatalog();
    const installCatalog = useInstallCatalog();
    const deleteCatalog = useDeleteCatalog();

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
            </Box>
        );
    }
    if (error) {
        return <Alert severity="error">Failed to load local catalog.</Alert>;
    }

    const entries = data?.entries ?? [];

    return (
        <Box>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 3 }}>
                <Archive size={22} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6">Local catalog</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Archives uploaded to this server. Each is a packaged
                        plugin ready to install. {entries.length} total.
                    </Typography>
                </Box>
            </Stack>

            {entries.length === 0 ? (
                <Alert severity="info">
                    The local catalog is empty. Use <strong>Upload archive</strong>{' '}
                    above to add a <code>.mpn</code>, then install it from here.
                </Alert>
            ) : (
                <Stack spacing={1}>
                    {entries.map((entry) => (
                        <Card key={entry.catalog_id} variant="outlined">
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    px: 2,
                                    py: 1.5,
                                    gap: 1,
                                }}
                            >
                                <Archive size={16} style={{ opacity: 0.6 }} />
                                <Box sx={{ flex: 1, minWidth: 0 }}>
                                    <Typography variant="body1" component="span">
                                        {entry.name}
                                    </Typography>
                                    <Chip size="small" label={`v${entry.version}`} sx={{ ml: 1 }} />
                                    <Chip
                                        size="small"
                                        variant="outlined"
                                        label={entry.category}
                                        sx={{ ml: 0.5 }}
                                    />
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: 'text.secondary',
                                            display: 'block',
                                            mt: 0.5,
                                        }}
                                    >
                                        {entry.description || entry.developer}
                                    </Typography>
                                </Box>
                                <Button
                                    size="small"
                                    startIcon={<Download size={14} />}
                                    variant="outlined"
                                    disabled={installCatalog.isLoading}
                                    onClick={() => installCatalog.mutate(entry.catalog_id)}
                                >
                                    Install
                                </Button>
                                <Button
                                    size="small"
                                    color="error"
                                    startIcon={<Trash2 size={14} />}
                                    disabled={deleteCatalog.isLoading}
                                    onClick={() => {
                                        if (window.confirm(`Remove ${entry.name} v${entry.version} from the catalog?`)) {
                                            deleteCatalog.mutate(entry.catalog_id);
                                        }
                                    }}
                                >
                                    Remove
                                </Button>
                            </Box>
                        </Card>
                    ))}
                </Stack>
            )}
        </Box>
    );
};
