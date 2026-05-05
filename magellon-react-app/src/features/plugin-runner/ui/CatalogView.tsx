/**
 * "Downloaded" tab — local archives uploaded but not yet installed.
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
import { Archive, Cloud, Download, Trash2, Upload } from 'lucide-react';
import {
    useCatalog,
    useDeleteCatalog,
    useInstallCatalog,
} from '../api/PluginApi.ts';

interface CatalogViewProps {
    onUploadArchive?: () => void;
    onBrowseHub?: () => void;
}

export const CatalogView: React.FC<CatalogViewProps> = ({
    onUploadArchive,
    onBrowseHub,
}) => {
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
        return <Alert severity="error">Failed to load downloaded plugins.</Alert>;
    }

    const entries = data?.entries ?? [];

    return (
        <Box>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 3 }}>
                <Archive size={22} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6">Ready to install</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Downloaded plugin archives staged on this server.
                        {entries.length > 0 ? ` ${entries.length} total.` : ''}
                    </Typography>
                </Box>
            </Stack>

            {entries.length === 0 ? (
                <Box
                    sx={{
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                        py: 6,
                        px: 3,
                        textAlign: 'center',
                    }}
                >
                    <Archive size={36} style={{ opacity: 0.55 }} />
                    <Typography variant="h6" sx={{ mt: 2 }}>
                        No downloaded plugins
                    </Typography>
                    <Typography
                        variant="body2"
                        sx={{
                            color: 'text.secondary',
                            maxWidth: 520,
                            mx: 'auto',
                            mt: 1,
                        }}
                    >
                        Upload a <code>.mpn</code> archive or browse the hub.
                        Downloaded archives will appear here before installation.
                    </Typography>
                    <Stack
                        direction={{ xs: 'column', sm: 'row' }}
                        spacing={1}
                        sx={{ justifyContent: 'center', mt: 3 }}
                    >
                        {onUploadArchive && (
                            <Button
                                variant="outlined"
                                startIcon={<Upload size={16} />}
                                onClick={onUploadArchive}
                            >
                                Upload archive
                            </Button>
                        )}
                        {onBrowseHub && (
                            <Button
                                variant="contained"
                                startIcon={<Cloud size={16} />}
                                onClick={onBrowseHub}
                            >
                                Browse hub
                            </Button>
                        )}
                    </Stack>
                </Box>
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
                                        if (window.confirm(`Remove ${entry.name} v${entry.version} from downloaded plugins?`)) {
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
