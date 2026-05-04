/**
 * Modal dropzone for uploading a `.mpn` archive.
 *
 * The drop zone used to live inline at the top of AdminInstalledPanel.
 * Per the operator's "the dropzone should be hidden at first and shown
 * in a modal" feedback, we put it behind an explicit "Upload archive"
 * button so the page surface stays focused on what's installed.
 *
 * Accepts ``.mpn`` (v1) and ``.magplugin`` (v0 legacy). On successful
 * install, calls ``onInstalled`` so the parent can refresh its lists
 * and close the dialog.
 */
import React, { useRef, useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Card,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    LinearProgress,
    Typography,
} from '@mui/material';
import { ChevronDown, ChevronUp, Package, Upload, X } from 'lucide-react';
import {
    useInstallMpn,
    type InstallResponse,
} from '../api/installerApi.ts';

interface UploadArchiveDialogProps {
    open: boolean;
    onClose: () => void;
    onInstalled?: (result: InstallResponse) => void;
}

const ACCEPT_EXTENSIONS = ['.mpn', '.magplugin', '.zip'];

export const UploadArchiveDialog: React.FC<UploadArchiveDialogProps> = ({
    open,
    onClose,
    onInstalled,
}) => {
    const installMpn = useInstallMpn();
    const fileInput = useRef<HTMLInputElement | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [installError, setInstallError] = useState<string | null>(null);
    const [installResult, setInstallResult] = useState<InstallResponse | null>(null);
    const [logsOpen, setLogsOpen] = useState(false);

    const reset = () => {
        setPendingFile(null);
        setInstallError(null);
        setInstallResult(null);
        setLogsOpen(false);
    };

    const handleClose = () => {
        if (installMpn.isLoading) return;
        reset();
        onClose();
    };

    const acceptFile = (file: File | null) => {
        setInstallError(null);
        setInstallResult(null);
        if (!file) {
            setPendingFile(null);
            return;
        }
        const ok = ACCEPT_EXTENSIONS.some((ext) => file.name.endsWith(ext));
        if (!ok) {
            setInstallError(
                `Expected a .mpn (or legacy .magplugin) archive; got ${file.name}.`,
            );
            setPendingFile(null);
            return;
        }
        setPendingFile(file);
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setDragOver(false);
        acceptFile(e.dataTransfer.files[0] ?? null);
    };

    const handleInstall = async () => {
        if (!pendingFile) return;
        setInstallError(null);
        setInstallResult(null);
        try {
            const result = await installMpn.mutateAsync(pendingFile);
            setInstallResult(result);
            setPendingFile(null);
            onInstalled?.(result);
        } catch (err: any) {
            setInstallError(
                err?.response?.data?.detail ?? err?.message ?? 'Install failed.',
            );
        }
    };

    const installing = installMpn.isLoading;

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>Upload plugin archive</DialogTitle>
            <DialogContent dividers>
                <Box
                    onDragOver={(e) => {
                        e.preventDefault();
                        if (!installing) setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => !installing && handleDrop(e)}
                    onClick={() => !installing && fileInput.current?.click()}
                    role="button"
                    tabIndex={0}
                    aria-label="Drop or browse for a .mpn archive"
                    sx={{
                        border: '2px dashed',
                        borderColor: dragOver ? 'primary.main' : 'divider',
                        bgcolor: dragOver ? 'action.hover' : 'background.default',
                        borderRadius: 2,
                        p: 4,
                        textAlign: 'center',
                        cursor: installing ? 'not-allowed' : 'pointer',
                        transition: 'background-color 150ms, border-color 150ms',
                        opacity: installing ? 0.5 : 1,
                    }}
                >
                    <Upload size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
                    <Typography variant="body1" sx={{ mb: 0.5 }}>
                        Drop a <code>.mpn</code> archive here, or{' '}
                        <strong>click to browse</strong>
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        The host's capabilities decide whether the plugin installs via
                        uv or docker.
                    </Typography>
                    <input
                        ref={fileInput}
                        type="file"
                        accept=".mpn,.magplugin,.zip"
                        style={{ display: 'none' }}
                        onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
                    />
                </Box>

                {pendingFile && !installing && (
                    <Card variant="outlined" sx={{ mt: 2 }}>
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                px: 2,
                                py: 1.5,
                                gap: 1,
                            }}
                        >
                            <Package size={18} />
                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                <Typography variant="body2" noWrap>
                                    {pendingFile.name}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                    {(pendingFile.size / 1024).toFixed(1)} KB
                                </Typography>
                            </Box>
                            <IconButton
                                size="small"
                                onClick={() => setPendingFile(null)}
                                aria-label="discard pending file"
                            >
                                <X size={16} />
                            </IconButton>
                        </Box>
                    </Card>
                )}

                {installing && (
                    <Box sx={{ mt: 2 }}>
                        <Typography variant="body2" sx={{ mb: 0.5 }}>
                            Installing {pendingFile?.name ?? 'plugin'}…
                        </Typography>
                        <LinearProgress />
                    </Box>
                )}

                {installError && (
                    <Alert
                        severity="error"
                        sx={{ mt: 2 }}
                        onClose={() => setInstallError(null)}
                    >
                        {installError}
                    </Alert>
                )}
                {installResult?.success && (
                    <Alert
                        severity="success"
                        sx={{ mt: 2 }}
                        action={
                            installResult.logs ? (
                                <Button
                                    size="small"
                                    onClick={() => setLogsOpen((o) => !o)}
                                    endIcon={
                                        logsOpen ? (
                                            <ChevronUp size={14} />
                                        ) : (
                                            <ChevronDown size={14} />
                                        )
                                    }
                                >
                                    Logs
                                </Button>
                            ) : null
                        }
                    >
                        <AlertTitle>{installResult.plugin_id} installed</AlertTitle>
                        via {installResult.install_method}
                        {installResult.install_dir && (
                            <>
                                {' '}
                                at <code>{installResult.install_dir}</code>
                            </>
                        )}
                        <Collapse in={logsOpen}>
                            <Box
                                component="pre"
                                sx={{
                                    mt: 1,
                                    bgcolor: 'background.default',
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1,
                                    p: 1,
                                    fontSize: 11,
                                    maxHeight: 180,
                                    overflow: 'auto',
                                }}
                            >
                                {installResult.logs}
                            </Box>
                        </Collapse>
                    </Alert>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={installing}>
                    {installResult ? 'Close' : 'Cancel'}
                </Button>
                <Button
                    onClick={handleInstall}
                    disabled={!pendingFile || installing}
                    variant="contained"
                    startIcon={<Upload size={14} />}
                >
                    Install
                </Button>
            </DialogActions>
        </Dialog>
    );
};
