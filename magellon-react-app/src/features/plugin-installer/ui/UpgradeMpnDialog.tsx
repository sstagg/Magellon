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
    FormControlLabel,
    Stack,
    Switch,
    Typography,
} from '@mui/material';
import { ArrowUp, Upload } from 'lucide-react';
import { useUpgradeMpn, type InstallResponse } from '../api/installerApi.ts';

interface UpgradeMpnDialogProps {
    open: boolean;
    onClose: () => void;
    /** plugin_id of the install being upgraded. Required — there's
     * no "upgrade something else" path; the operator picked which
     * row's Upgrade button they clicked. */
    pluginId: string;
    onUpgraded?: (result: InstallResponse) => void;
}

/**
 * Admin upgrade dialog. Operator uploads a new-version `.mpn`; the
 * manager validates plugin_id + version, moves the existing install
 * to `.bak`, installs the new version, and rolls back on failure.
 *
 * `force_downgrade` is here for emergency rollback — operator
 * uploads an OLDER archive to revert across plugin boundaries.
 * Defaults off so a routine "I want to bump the patch" upgrade
 * doesn't accidentally accept an older artifact.
 */
export const UpgradeMpnDialog: React.FC<UpgradeMpnDialogProps> = ({
    open,
    onClose,
    pluginId,
    onUpgraded,
}) => {
    const upgrade = useUpgradeMpn();
    const fileInput = useRef<HTMLInputElement | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [forceDowngrade, setForceDowngrade] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<InstallResponse | null>(null);

    const busy = upgrade.isLoading;

    const reset = () => {
        setFile(null);
        setForceDowngrade(false);
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
            const res = await upgrade.mutateAsync({
                pluginId,
                file,
                forceDowngrade,
            });
            setResult(res);
            onUpgraded?.(res);
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Upgrade failed.');
        }
    };

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <ArrowUp size={20} />
                    <span>Upgrade <code>{pluginId}</code></span>
                </Stack>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Alert severity="info">
                        The current install is moved aside as{' '}
                        <code>{pluginId}.&lt;version&gt;.bak</code> while the new
                        version installs. If the new install fails, the
                        previous one is restored automatically (operator must
                        restart the plugin process).
                    </Alert>

                    <input
                        ref={fileInput}
                        type="file"
                        accept=".mpn,.zip"
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
                            Choose new archive
                        </Button>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                            {file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'No file selected.'}
                        </Typography>
                    </Stack>

                    <FormControlLabel
                        control={
                            <Switch
                                checked={forceDowngrade}
                                onChange={(e) => setForceDowngrade(e.target.checked)}
                                disabled={busy}
                            />
                        }
                        label={
                            <Typography variant="body2">
                                Allow downgrade
                                <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                                    Off (default) refuses an older version. On for emergency rollback.
                                </Typography>
                            </Typography>
                        }
                    />

                    {error && <Alert severity="error">{error}</Alert>}

                    {result && result.success && (
                        <Alert severity="success">
                            <AlertTitle>Upgraded to new version</AlertTitle>
                            via {result.install_method}
                        </Alert>
                    )}

                    {result?.logs && (
                        <Box>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Upgrade logs
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
                        {busy ? 'Upgrading…' : 'Upgrade'}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
