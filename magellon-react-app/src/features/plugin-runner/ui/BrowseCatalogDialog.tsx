import React, { useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import { Download, Package, Search, Trash2, Upload } from 'lucide-react';
import {
    useCatalog,
    useDeleteCatalog,
    useInstallCatalog,
    useUploadCatalog,
} from '../api/PluginApi.ts';

interface BrowseCatalogDialogProps {
    open: boolean;
    onClose: () => void;
    /** Fallback to direct-image-ref install from inside this modal. */
    onOpenInstallDialog?: () => void;
}

/**
 * The "browse online plugins" modal. Search + category filter + per-
 * entry install, plus an Upload action for publishing a new archive
 * into the catalog.
 *
 * Scope: the catalog is CoreService-local (one deployment's shared
 * library). A true federated registry — "online plugins" in the
 * multi-org sense — is H3c. Until then, "online" == "anyone with
 * access to this CoreService can browse + install from the shared
 * catalog."
 */
export const BrowseCatalogDialog: React.FC<BrowseCatalogDialogProps> = ({
    open,
    onClose,
    onOpenInstallDialog,
}) => {
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [flash, setFlash] = useState<string | null>(null);
    const uploadInputRef = useRef<HTMLInputElement | null>(null);

    const { data, isLoading } = useCatalog({
        search: search || undefined,
        category: category ?? undefined,
    });
    const uploadMutation = useUploadCatalog();
    const installMutation = useInstallCatalog();
    const deleteMutation = useDeleteCatalog();

    const categoryCounts = data?.categories ?? {};
    const entries = data?.entries ?? [];
    const busy =
        uploadMutation.isLoading ||
        installMutation.isLoading ||
        deleteMutation.isLoading;

    const handleUpload = async (file: File) => {
        setError(null);
        setFlash(null);
        try {
            const entry = await uploadMutation.mutateAsync(file);
            setFlash(`Uploaded ${entry.name} v${entry.version} (${entry.catalog_id})`);
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Upload failed.');
        }
    };

    const handleInstall = async (catalogId: string, displayName: string) => {
        setError(null);
        setFlash(null);
        try {
            await installMutation.mutateAsync(catalogId);
            setFlash(`Installed ${displayName}`);
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Install failed.');
        }
    };

    const handleDelete = async (catalogId: string) => {
        setError(null);
        setFlash(null);
        try {
            await deleteMutation.mutateAsync(catalogId);
            setFlash(`Removed ${catalogId} from catalog`);
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Delete failed.');
        }
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>
                <Stack direction="row" spacing={1} alignItems="center">
                    <Package size={22} />
                    <span>Browse plugins</span>
                </Stack>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Stack direction="row" spacing={1} alignItems="center">
                        <TextField
                            size="small"
                            placeholder="Search name, description, developer…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            InputProps={{
                                startAdornment: <Search size={16} style={{ marginRight: 8, opacity: 0.6 }} />,
                            }}
                            fullWidth
                        />
                        <input
                            ref={uploadInputRef}
                            type="file"
                            accept=".magplugin,.zip"
                            style={{ display: 'none' }}
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) handleUpload(file);
                                // reset so the same file can be re-selected
                                e.target.value = '';
                            }}
                        />
                        <Button
                            variant="contained"
                            startIcon={<Upload size={16} />}
                            disabled={busy}
                            onClick={() => uploadInputRef.current?.click()}
                        >
                            Upload plugin
                        </Button>
                    </Stack>

                    <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1}>
                        <Chip
                            label="All"
                            size="small"
                            color={category === null ? 'primary' : 'default'}
                            variant={category === null ? 'filled' : 'outlined'}
                            onClick={() => setCategory(null)}
                        />
                        {Object.entries(categoryCounts).map(([cat, count]) => (
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

                    {flash && <Alert severity="success" onClose={() => setFlash(null)}>{flash}</Alert>}
                    {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

                    {isLoading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                            <CircularProgress />
                        </Box>
                    ) : entries.length === 0 ? (
                        <Alert severity="info">
                            No plugins in the catalog
                            {search || category ? ' match the current filter' : ''}.
                            {!search && !category && (
                                <>
                                    {' '}Upload a <code>.magplugin</code> archive (produced by
                                    {' '}<code>magellon-sdk plugin pack &lt;dir&gt;</code>)
                                    {' '}to publish one.
                                </>
                            )}
                        </Alert>
                    ) : (
                        <Stack spacing={1}>
                            {entries.map((entry) => (
                                <Box
                                    key={entry.catalog_id}
                                    sx={{
                                        p: 2,
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        borderRadius: 1,
                                    }}
                                >
                                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                                        <Typography variant="subtitle1">{entry.name}</Typography>
                                        <Chip size="small" label={`v${entry.version}`} />
                                        <Chip size="small" variant="outlined" label={entry.category} />
                                        <Tooltip title={`SDK ${entry.sdk_compat}`}>
                                            <Chip
                                                size="small"
                                                variant="outlined"
                                                label={entry.sdk_compat}
                                                sx={{ opacity: 0.7 }}
                                            />
                                        </Tooltip>
                                        <Box sx={{ flex: 1 }} />
                                        <Button
                                            size="small"
                                            variant="contained"
                                            startIcon={<Download size={14} />}
                                            disabled={busy}
                                            onClick={() => handleInstall(entry.catalog_id, `${entry.name} v${entry.version}`)}
                                        >
                                            Install
                                        </Button>
                                        <IconButton
                                            size="small"
                                            aria-label="remove from catalog"
                                            disabled={busy}
                                            onClick={() => handleDelete(entry.catalog_id)}
                                        >
                                            <Trash2 size={16} />
                                        </IconButton>
                                    </Stack>
                                    <Typography variant="body2" color="text.secondary">
                                        {entry.description || <em>(no description)</em>}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {entry.developer} · image: <code>{entry.image_ref}</code>
                                    </Typography>
                                </Box>
                            ))}
                        </Stack>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                {onOpenInstallDialog && (
                    <Button
                        onClick={() => {
                            onClose();
                            onOpenInstallDialog();
                        }}
                        sx={{ mr: 'auto' }}
                    >
                        Install by image ref…
                    </Button>
                )}
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
};
