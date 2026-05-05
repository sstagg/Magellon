/**
 * Hub install dialog — same Settings + result pattern as
 * UploadArchiveDialog, parameterized for the hub flow.
 *
 * Pipeline:
 *   1. Download the .mpn from the hub URL into browser memory.
 *   2. Verify SHA256 against the hub catalog.
 *   3. POST it to /admin/plugins/inspect → method picker populates
 *      with the per-host support verdict for each install method.
 *   4. Operator (optionally) overrides the host-default selection.
 *   5. POST to /admin/plugins/install with file + install_method.
 *
 * Bytes never touch CoreService disk during the hub fetch — they
 * stream into the browser, get verified there, and reach CoreService
 * only as the multipart upload of step 3 / step 5. CoreService never
 * receives an arbitrary URL to fetch.
 */
import React, { useEffect, useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    InputLabel,
    LinearProgress,
    MenuItem,
    Select,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import { AlertTriangle, Download, ShieldCheck } from 'lucide-react';
import {
    archiveUrl,
    downloadArchiveAsFile,
    type HubPlugin,
    type HubVersion,
} from '../api/hubApi.ts';
import {
    useInspectArchive,
    useInstallMpn,
    type InspectResponse,
    type InstallMethodOption,
    type InstallResponse,
} from '../api/installerApi.ts';

interface HubInstallDialogProps {
    open: boolean;
    onClose: () => void;
    plugin: HubPlugin | null;
    /** Override the version the user installs — defaults to
     * `plugin.versions[0]` (latest). Reserved for a future "Choose
     * version" picker; today we always install latest. */
    version?: HubVersion;
    onInstalled?: (result: InstallResponse) => void;
}

type Stage =
    | 'preparing'      // download + sha256 + inspect
    | 'confirm'        // method picker visible, awaiting Install click
    | 'installing'
    | 'done';

const errText = (err: unknown): string => {
    if (typeof err === 'object' && err !== null) {
        const r = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
        const detail = r.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (typeof r.message === 'string') return r.message;
    }
    return 'Operation failed.';
};

export const HubInstallDialog: React.FC<HubInstallDialogProps> = ({
    open,
    onClose,
    plugin,
    version,
    onInstalled,
}) => {
    const inspect = useInspectArchive();
    const install = useInstallMpn();

    const [stage, setStage] = useState<Stage>('preparing');
    const [error, setError] = useState<string | null>(null);
    const [downloadedFile, setDownloadedFile] = useState<File | null>(null);
    const [inspectResult, setInspectResult] = useState<InspectResponse | null>(null);
    const [selectedMethod, setSelectedMethod] = useState<string>('');
    const [installResult, setInstallResult] = useState<InstallResponse | null>(null);

    const reset = () => {
        setStage('preparing');
        setError(null);
        setDownloadedFile(null);
        setInspectResult(null);
        setSelectedMethod('');
        setInstallResult(null);
    };

    useEffect(() => {
        if (!open) reset();
    }, [open]);

    // When the dialog opens with a plugin, kick off the
    // download + sha256 + inspect pipeline immediately so the
    // method picker has something to show by the time the operator
    // is ready to click Install.
    useEffect(() => {
        if (!open || !plugin) return;
        const v = version ?? plugin.versions[0];
        if (!v) return;
        let cancelled = false;
        (async () => {
            setError(null);
            setStage('preparing');
            try {
                const file = await downloadArchiveAsFile(plugin, v);
                if (cancelled) return;
                setDownloadedFile(file);
                const result = await inspect.mutateAsync(file);
                if (cancelled) return;
                setInspectResult(result);
                setSelectedMethod(result.default_method ?? '');
                setStage('confirm');
            } catch (err) {
                if (cancelled) return;
                setError(errText(err));
                setStage('confirm');
            }
        })();
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, plugin?.plugin_id, version?.version]);

    if (!plugin) return null;
    const v = version ?? plugin.versions[0];

    const handleClose = () => {
        if (stage === 'preparing' || stage === 'installing') return;
        reset();
        onClose();
    };

    const handleInstall = async () => {
        if (!downloadedFile) return;
        setError(null);
        setInstallResult(null);
        setStage('installing');
        try {
            const res = await install.mutateAsync({
                file: downloadedFile,
                installMethod: selectedMethod || null,
            });
            setInstallResult(res);
            setStage('done');
            onInstalled?.(res);
        } catch (err) {
            setError(errText(err));
            setStage('confirm');
        }
    };

    const busy = stage === 'preparing' || stage === 'installing';

    const renderMethodOption = (m: InstallMethodOption) => (
        <MenuItem key={m.method} value={m.method}>
            <Tooltip
                title={m.supported ? '' : `This host can't satisfy: ${m.failures.join('; ')}`}
                placement="right"
            >
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', width: '100%' }}>
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
            </Tooltip>
        </MenuItem>
    );

    const chosen = inspectResult?.methods.find((x) => x.method === selectedMethod);

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <Download size={20} />
                    <span>Install {plugin.name}</span>
                </Stack>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Stack direction="row" spacing={1}>
                        <Chip size="small" label={`v${v.version}`} />
                        <Chip size="small" variant="outlined" label={plugin.category} />
                        <Chip
                            size="small"
                            color={plugin.tier === 'verified' ? 'success' : 'warning'}
                            icon={plugin.tier === 'verified' ? <ShieldCheck size={12} /> : undefined}
                            label={plugin.tier}
                        />
                        {inspectResult?.already_installed && (
                            <Chip size="small" color="warning" label="already installed" />
                        )}
                    </Stack>

                    {plugin.description && (
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                            {plugin.description}
                        </Typography>
                    )}

                    <Box
                        sx={{
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: 1,
                            p: 1.5,
                            fontSize: 13,
                        }}
                    >
                        <Stack spacing={0.5}>
                            <Stack direction="row" spacing={1}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>plugin_id</Typography>
                                <code>{plugin.plugin_id}</code>
                            </Stack>
                            <Stack direction="row" spacing={1}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>author</Typography>
                                <span>{plugin.author}</span>
                            </Stack>
                            <Stack direction="row" spacing={1}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>license</Typography>
                                <span>{plugin.license}</span>
                            </Stack>
                            <Stack direction="row" spacing={1}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>requires SDK</Typography>
                                <code>{v.requires_sdk}</code>
                            </Stack>
                            <Stack direction="row" spacing={1}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>size</Typography>
                                <span>{(v.size_bytes / 1024).toFixed(1)} KB</span>
                            </Stack>
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>SHA256</Typography>
                                <code style={{ fontSize: 11, wordBreak: 'break-all' }}>{v.sha256}</code>
                            </Stack>
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                                <Typography variant="caption" sx={{ width: 100, color: 'text.secondary' }}>download</Typography>
                                <code style={{ fontSize: 11, wordBreak: 'break-all' }}>{archiveUrl(v.url)}</code>
                            </Stack>
                        </Stack>
                    </Box>

                    {plugin.tier === 'community' && (
                        <Alert severity="warning" icon={false}>
                            Community-tier plugin — not reviewed by Magellon
                            maintainers. Inspect the archive before installing
                            on a production deployment.
                        </Alert>
                    )}

                    {stage === 'preparing' && (
                        <Box>
                            <Typography variant="body2" sx={{ mb: 0.5 }}>
                                Downloading + verifying SHA256, then reading manifest…
                            </Typography>
                            <LinearProgress />
                        </Box>
                    )}

                    {inspectResult && (
                        <FormControl fullWidth size="small">
                            <InputLabel id="hub-install-method-label">Install method</InputLabel>
                            <Select
                                labelId="hub-install-method-label"
                                label="Install method"
                                value={selectedMethod}
                                onChange={(e) => setSelectedMethod(String(e.target.value))}
                                disabled={stage === 'installing'}
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
                    )}

                    {chosen && !chosen.supported && (
                        <Alert severity="warning" icon={<AlertTriangle size={16} />}>
                            <AlertTitle>Host doesn't satisfy this method</AlertTitle>
                            {chosen.failures.map((f, i) => (
                                <div key={i}>{f}</div>
                            ))}
                        </Alert>
                    )}

                    {inspectResult?.default_method && selectedMethod !== inspectResult.default_method && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Default for this host: <strong>{inspectResult.default_method}</strong>
                        </Typography>
                    )}

                    {stage === 'installing' && (
                        <Box>
                            <Typography variant="body2" sx={{ mb: 0.5 }}>
                                Installing {plugin.name}
                                {selectedMethod && ` via ${selectedMethod}`}…
                            </Typography>
                            <LinearProgress />
                        </Box>
                    )}

                    {error && <Alert severity="error">{error}</Alert>}

                    {installResult?.success && (
                        <Alert severity="success">
                            <AlertTitle>{installResult.plugin_id} installed</AlertTitle>
                            via {installResult.install_method}
                            {installResult.install_dir && (
                                <> at <code>{installResult.install_dir}</code></>
                            )}
                        </Alert>
                    )}

                    {installResult?.logs && (
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
                                    fontSize: 11,
                                    maxHeight: 180,
                                    overflow: 'auto',
                                }}
                            >
                                {installResult.logs}
                            </Box>
                        </Box>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={busy}>
                    {stage === 'done' ? 'Close' : 'Cancel'}
                </Button>
                {stage !== 'done' && (
                    <Button
                        variant="contained"
                        onClick={handleInstall}
                        disabled={busy || !downloadedFile || !inspectResult}
                    >
                        {stage === 'installing' ? 'Installing…' : 'Install'}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
