import React, { useRef, useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Stack,
    Typography,
} from '@mui/material';
import { Package, Upload } from 'lucide-react';
import { useInstallMpn, type InstallResponse } from '../api/installerApi.ts';

interface InstallMpnDialogProps {
    open: boolean;
    onClose: () => void;
    /** Optional: notified on a successful install so callers can
     * close their parent flows / refresh. Independent of the
     * mutation's onSuccess (which always fires). */
    onInstalled?: (result: InstallResponse) => void;
}

/**
 * Admin-side install dialog for v1 `.mpn` archives.
 *
 * Distinct from the legacy `InstallPluginDialog` (image-ref + env
 * + volumes). The new pipeline reads everything it needs from the
 * archive's manifest; the operator only picks the file and confirms.
 */
export const InstallMpnDialog: React.FC<InstallMpnDialogProps> = ({
    open,
    onClose,
    onInstalled,
}) => {
    const install = useInstallMpn();
    const fileInput = useRef<HTMLInputElement | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<InstallResponse | null>(null);

    const busy = install.isLoading;

    const reset = () => {
        setFile(null);
        setError(null);
        setResult(null);
    };

    const handleClose = () => {
        if (busy) return;
        reset();
        onClose();
    };

    const handleSubmit = async () => {
        if (!file) return;
        setError(null);
        try {
            const res = await install.mutateAsync(file);
            setResult(res);
            onInstalled?.(res);
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Install failed.');
        }
    };

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <Package size={20} />
                    <span>Install plugin</span>
                </Stack>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Alert severity="info">
                        Upload a <code>.mpn</code> archive produced by{' '}
                        <code>magellon-sdk plugin pack &lt;dir&gt;</code>.
                        The archive's manifest declares which install method
                        runs (uv or docker); the host's capabilities decide
                        which one wins.
                    </Alert>

                    <input
                        ref={fileInput}
                        type="file"
                        accept=".mpn,.magplugin,.zip"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                            setFile(e.target.files?.[0] ?? null);
                            setError(null);
                            setResult(null);
                        }}
                    />
                    <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
                        <Button
                            variant="outlined"
                            startIcon={<Upload size={16} />}
                            onClick={() => fileInput.current?.click()}
                            disabled={busy}
                        >
                            Choose archive
                        </Button>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                            {file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'No file selected.'}
                        </Typography>
                    </Stack>

                    {error && <Alert severity="error">{error}</Alert>}

                    {result && result.success && (
                        <Alert severity="success">
                            <AlertTitle>{result.plugin_id} installed</AlertTitle>
                            via {result.install_method}
                            {result.install_dir && (
                                <> at <code>{result.install_dir}</code></>
                            )}
                        </Alert>
                    )}

                    {result?.logs && (
                        <Box>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Install logs
                            </Typography>
                            <Box
                                component="pre"
                                sx={{
                                    bgcolor: 'background.default',
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1,
                                    p: 1,
                                    fontSize: 12,
                                    maxHeight: 200,
                                    overflow: 'auto',
                                }}
                            >
                                {result.logs}
                            </Box>
                        </Box>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={busy}>
                    {result?.success ? 'Close' : 'Cancel'}
                </Button>
                {!result?.success && (
                    <Button
                        variant="contained"
                        onClick={handleSubmit}
                        disabled={busy || !file}
                    >
                        {busy ? 'Installing…' : 'Install'}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
