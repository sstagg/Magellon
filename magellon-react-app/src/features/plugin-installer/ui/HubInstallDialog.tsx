import React, { useState } from 'react';
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
    LinearProgress,
    Stack,
    Typography,
} from '@mui/material';
import { Download, ShieldCheck } from 'lucide-react';
import {
    archiveUrl,
    downloadArchiveAsFile,
    type HubPlugin,
    type HubVersion,
} from '../api/hubApi.ts';
import { useInstallMpn, type InstallResponse } from '../api/installerApi.ts';

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

type Stage = 'confirm' | 'downloading' | 'verifying' | 'installing' | 'done';

/**
 * Two-stage install dialog: confirm what's about to be installed,
 * then run the download → verify → upload pipeline.
 *
 * Bytes never touch CoreService disk during the download — they
 * stream into the browser, get SHA256-checked client-side against
 * the hub manifest, then POST as multipart to /admin/plugins/install.
 * That keeps CoreService's hub trust footprint minimal: it trusts
 * the upload it receives, not an arbitrary URL it has to fetch.
 *
 * Two pages of UX in one modal:
 *   - Confirmation (manifest summary + version + size + sha)
 *   - Progress + result (download bar, install logs, success/error)
 */
export const HubInstallDialog: React.FC<HubInstallDialogProps> = ({
    open,
    onClose,
    plugin,
    version,
    onInstalled,
}) => {
    const installMpn = useInstallMpn();
    const [stage, setStage] = useState<Stage>('confirm');
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<InstallResponse | null>(null);

    if (!plugin) return null;
    const v = version ?? plugin.versions[0];

    const reset = () => {
        setStage('confirm');
        setError(null);
        setResult(null);
    };

    const handleClose = () => {
        if (stage === 'downloading' || stage === 'verifying' || stage === 'installing') return;
        reset();
        onClose();
    };

    const handleInstall = async () => {
        setError(null);
        setResult(null);
        setStage('downloading');
        try {
            // crypto.subtle.digest is the slow step on big archives,
            // but we keep the verifying stage explicit so the user
            // sees what's happening on a large download.
            setStage('downloading');
            const file = await downloadArchiveAsFile(plugin, v);
            setStage('installing');
            const res = await installMpn.mutateAsync(file);
            setResult(res);
            setStage('done');
            onInstalled?.(res);
        } catch (err: any) {
            const msg = err?.response?.data?.detail ?? err?.message ?? 'Install failed.';
            setError(String(msg));
            setStage('confirm');
        }
    };

    const busy = stage === 'downloading' || stage === 'verifying' || stage === 'installing';

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

                    {busy && (
                        <Box>
                            <Typography variant="body2" sx={{ mb: 0.5 }}>
                                {stage === 'downloading' && 'Downloading + verifying SHA256…'}
                                {stage === 'installing' && 'Installing on CoreService…'}
                            </Typography>
                            <LinearProgress />
                        </Box>
                    )}

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
                                    fontSize: 11,
                                    maxHeight: 180,
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
                    {stage === 'done' ? 'Close' : 'Cancel'}
                </Button>
                {stage !== 'done' && (
                    <Button
                        variant="contained"
                        onClick={handleInstall}
                        disabled={busy}
                    >
                        {busy ? 'Installing…' : 'Install'}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
