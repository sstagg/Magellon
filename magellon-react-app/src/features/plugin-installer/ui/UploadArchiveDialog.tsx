/**
 * Modal dropzone for installing a `.mpn` archive.
 *
 * Two-step flow:
 *   1. User drops/picks a file → we POST it to /admin/plugins/inspect.
 *      The dialog now shows the plugin's identity and a method dropdown
 *      pre-populated from the manifest, with the host-supported methods
 *      first and unsupported ones disabled-with-reason.
 *   2. User confirms (optionally changing the method) → we POST to
 *      /admin/plugins/install with the chosen install_method.
 *
 * The default selection follows the manifest author's preferred method
 * (manifest order, first one supported on this host). The operator can
 * override — switching to a method the host can't satisfy returns a
 * 422 with the failure reason rendered in the success/error banner.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Card,
    Chip,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    InputLabel,
    LinearProgress,
    MenuItem,
    Select,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AlertTriangle,
    ChevronDown,
    ChevronUp,
    Package,
    Upload,
    X,
} from 'lucide-react';
import {
    useInspectArchive,
    useInstallMpn,
    type InspectResponse,
    type InstallMethodOption,
    type InstallResponse,
} from '../api/installerApi.ts';

interface UploadArchiveDialogProps {
    open: boolean;
    onClose: () => void;
    onInstalled?: (result: InstallResponse) => void;
}

const ACCEPT_EXTENSIONS = ['.mpn', '.zip'];

const methodErrorText = (err: unknown): string => {
    if (typeof err === 'object' && err !== null) {
        const r = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
        const detail = r.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (typeof r.message === 'string') return r.message;
    }
    return 'Failed to read archive.';
};

export const UploadArchiveDialog: React.FC<UploadArchiveDialogProps> = ({
    open,
    onClose,
    onInstalled,
}) => {
    const inspect = useInspectArchive();
    const install = useInstallMpn();
    const fileInput = useRef<HTMLInputElement | null>(null);

    const [dragOver, setDragOver] = useState(false);
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [inspectResult, setInspectResult] = useState<InspectResponse | null>(null);
    const [inspectError, setInspectError] = useState<string | null>(null);
    const [selectedMethod, setSelectedMethod] = useState<string>('');
    const [installError, setInstallError] = useState<string | null>(null);
    const [installResult, setInstallResult] = useState<InstallResponse | null>(null);
    const [logsOpen, setLogsOpen] = useState(false);

    const reset = () => {
        setPendingFile(null);
        setInspectResult(null);
        setInspectError(null);
        setSelectedMethod('');
        setInstallError(null);
        setInstallResult(null);
        setLogsOpen(false);
    };

    const handleClose = () => {
        if (install.isLoading || inspect.isLoading) return;
        reset();
        onClose();
    };

    useEffect(() => {
        if (!open) reset();
    }, [open]);

    const acceptFile = async (file: File | null) => {
        setInspectError(null);
        setInspectResult(null);
        setInstallError(null);
        setInstallResult(null);
        setSelectedMethod('');

        if (!file) {
            setPendingFile(null);
            return;
        }
        const ok = ACCEPT_EXTENSIONS.some((ext) => file.name.endsWith(ext));
        if (!ok) {
            setInspectError(`Expected a .mpn archive; got ${file.name}.`);
            setPendingFile(null);
            return;
        }
        setPendingFile(file);

        // Inspect immediately so the dropdown can populate before the
        // operator hits Install. If inspect fails (corrupt archive,
        // missing manifest) we keep the file pending and surface the
        // error — they can still try clicking Install, in which case
        // /admin/plugins/install returns the same 400 with the same
        // detail.
        try {
            const result = await inspect.mutateAsync(file);
            setInspectResult(result);
            setSelectedMethod(result.default_method ?? '');
        } catch (err) {
            setInspectError(methodErrorText(err));
        }
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
            const result = await install.mutateAsync({
                file: pendingFile,
                installMethod: selectedMethod || null,
            });
            setInstallResult(result);
            setPendingFile(null);
            onInstalled?.(result);
        } catch (err: any) {
            setInstallError(
                err?.response?.data?.detail ?? err?.message ?? 'Install failed.',
            );
        }
    };

    const installing = install.isLoading;
    const inspecting = inspect.isLoading;

    const renderMethodOption = (m: InstallMethodOption) => {
        const label = (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <span>{m.method}</span>
                {!m.supported && (
                    <Chip
                        size="small"
                        color="warning"
                        icon={<AlertTriangle size={12} />}
                        label="unsupported on this host"
                        variant="outlined"
                    />
                )}
                {m.notes && (
                    <Typography
                        variant="caption"
                        sx={{ color: 'text.secondary', fontFamily: 'monospace' }}
                    >
                        {m.notes}
                    </Typography>
                )}
            </Stack>
        );
        return (
            <MenuItem key={m.method} value={m.method}>
                <Tooltip
                    title={
                        m.supported
                            ? ''
                            : `This host can't satisfy: ${m.failures.join('; ')}`
                    }
                    placement="right"
                >
                    <span style={{ width: '100%' }}>{label}</span>
                </Tooltip>
            </MenuItem>
        );
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>Upload plugin archive</DialogTitle>
            <DialogContent dividers>
                {!pendingFile && !installResult && (
                    <Box
                        onDragOver={(e) => {
                            e.preventDefault();
                            if (!installing && !inspecting) setDragOver(true);
                        }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={(e) => !installing && !inspecting && handleDrop(e)}
                        onClick={() => !installing && !inspecting && fileInput.current?.click()}
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
                            cursor: installing || inspecting ? 'not-allowed' : 'pointer',
                            transition: 'background-color 150ms, border-color 150ms',
                            opacity: installing || inspecting ? 0.5 : 1,
                        }}
                    >
                        <Upload size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
                        <Typography variant="body1" sx={{ mb: 0.5 }}>
                            Drop a <code>.mpn</code> archive here, or{' '}
                            <strong>click to browse</strong>
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            We'll read the manifest and let you pick the install method.
                        </Typography>
                        <input
                            ref={fileInput}
                            type="file"
                            accept=".mpn,.zip"
                            style={{ display: 'none' }}
                            onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
                        />
                    </Box>
                )}

                {pendingFile && !installResult && (
                    <Card variant="outlined" sx={{ mb: 2 }}>
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
                                onClick={() => {
                                    setPendingFile(null);
                                    setInspectResult(null);
                                    setSelectedMethod('');
                                }}
                                disabled={installing || inspecting}
                                aria-label="discard pending file"
                            >
                                <X size={16} />
                            </IconButton>
                        </Box>
                    </Card>
                )}

                {inspecting && (
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" sx={{ mb: 0.5 }}>
                            Reading manifest…
                        </Typography>
                        <LinearProgress />
                    </Box>
                )}

                {inspectError && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setInspectError(null)}>
                        {inspectError}
                    </Alert>
                )}

                {inspectResult && !installResult && (
                    <Stack spacing={2}>
                        <Box>
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5, flexWrap: 'wrap' }}>
                                <Typography variant="h6">{inspectResult.name}</Typography>
                                <Chip size="small" label={`v${inspectResult.version}`} />
                                <Chip size="small" variant="outlined" label={inspectResult.category} />
                                {inspectResult.already_installed && (
                                    <Chip size="small" color="warning" label="already installed" />
                                )}
                            </Stack>
                            {inspectResult.description && (
                                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                    {inspectResult.description}
                                </Typography>
                            )}
                            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
                                {inspectResult.plugin_id}
                                {inspectResult.developer && ` · ${inspectResult.developer}`}
                                {' · SDK '}
                                <code>{inspectResult.sdk_compat}</code>
                            </Typography>
                        </Box>

                        <FormControl fullWidth size="small">
                            <InputLabel id="install-method-label">Install method</InputLabel>
                            <Select
                                labelId="install-method-label"
                                label="Install method"
                                value={selectedMethod}
                                onChange={(e) => setSelectedMethod(String(e.target.value))}
                                disabled={installing}
                                renderValue={(value) => {
                                    const m = inspectResult.methods.find((x) => x.method === value);
                                    if (!m) return String(value);
                                    return (
                                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                                            <span>{m.method}</span>
                                            {!m.supported && (
                                                <Chip size="small" color="warning" label="host cannot satisfy" />
                                            )}
                                        </Stack>
                                    );
                                }}
                            >
                                {inspectResult.methods.map(renderMethodOption)}
                            </Select>
                        </FormControl>

                        {selectedMethod && (() => {
                            const chosen = inspectResult.methods.find((x) => x.method === selectedMethod);
                            if (chosen && !chosen.supported) {
                                return (
                                    <Alert severity="warning" icon={<AlertTriangle size={16} />}>
                                        <AlertTitle>Host doesn't satisfy this method</AlertTitle>
                                        {chosen.failures.map((f, i) => (
                                            <div key={i}>{f}</div>
                                        ))}
                                    </Alert>
                                );
                            }
                            return null;
                        })()}

                        {inspectResult.default_method && selectedMethod !== inspectResult.default_method && (
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Default for this host: <strong>{inspectResult.default_method}</strong>
                            </Typography>
                        )}
                    </Stack>
                )}

                {installing && (
                    <Box sx={{ mt: 2 }}>
                        <Typography variant="body2" sx={{ mb: 0.5 }}>
                            Installing {inspectResult?.name ?? pendingFile?.name ?? 'plugin'}
                            {selectedMethod && ` via ${selectedMethod}`}…
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
                <Button onClick={handleClose} disabled={installing || inspecting}>
                    {installResult ? 'Close' : 'Cancel'}
                </Button>
                <Button
                    onClick={handleInstall}
                    disabled={!pendingFile || installing || inspecting}
                    variant="contained"
                    startIcon={<Upload size={14} />}
                >
                    Install
                </Button>
            </DialogActions>
        </Dialog>
    );
};
