/**
 * UpgradeDialog — operator-facing upgrade flow (Phase 9).
 *
 * Pipeline:
 *   1. Open the dialog from `PluginUpdateChip` (clickable trigger).
 *   2. Fetch /admin/plugins/{id}/upgrades — list hub versions.
 *   3. Show current → target with a version picker (defaults to the
 *      latest available, or to ``update.latest_version`` if passed in).
 *   4. Warn if the picked version is older than current (force_downgrade
 *      checkbox required).
 *   5. Operator clicks Upgrade → POST /upgrade-from-hub.
 *   6. Surface InstallResult logs same as the install dialog.
 *
 * Per the locked plan: warn-and-proceed, not block-on-active-tasks.
 * The warning chip says "in-flight tasks will be requeued" — RMQ
 * handles the actual requeue when the old container is killed.
 */
import React, { useEffect, useMemo, useState } from 'react';
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
    FormControlLabel,
    InputLabel,
    LinearProgress,
    MenuItem,
    Select,
    Stack,
    Switch,
    Typography,
} from '@mui/material';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import {
    usePluginUpgrades,
    useUpgradeFromHub,
    type InstallFromHubResponse,
    type UpgradeCandidate,
} from '../api/installerApi.ts';

interface UpgradeDialogProps {
    open: boolean;
    onClose: () => void;
    pluginId: string;
    /** Optional hint about which version to pre-select; if the hub's
     *  candidate list contains it, that's the default. */
    suggestedVersion?: string;
}

const errText = (err: unknown): string => {
    if (typeof err === 'object' && err !== null) {
        const r = err as {
            response?: { data?: { detail?: unknown } };
            message?: unknown;
        };
        const detail = r.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (typeof r.message === 'string') return r.message;
    }
    return 'Operation failed.';
};

function compareSemver(a: string, b: string): number {
    // Naive but sufficient for the catalog — split on dots, compare
    // numerically with non-numeric segments falling back to string
    // compare so "1.0.0" < "1.0.0-rc1".
    const pa = a.split('.');
    const pb = b.split('.');
    const n = Math.max(pa.length, pb.length);
    for (let i = 0; i < n; i++) {
        const av = pa[i] ?? '';
        const bv = pb[i] ?? '';
        const an = Number(av);
        const bn = Number(bv);
        if (!Number.isNaN(an) && !Number.isNaN(bn)) {
            if (an !== bn) return an - bn;
        } else {
            const cmp = av.localeCompare(bv);
            if (cmp !== 0) return cmp;
        }
    }
    return 0;
}

export const UpgradeDialog: React.FC<UpgradeDialogProps> = ({
    open, onClose, pluginId, suggestedVersion,
}) => {
    const upgrades = usePluginUpgrades(pluginId, { enabled: open });
    const upgrade = useUpgradeFromHub(pluginId);

    const [selectedVersion, setSelectedVersion] = useState<string>('');
    const [forceDowngrade, setForceDowngrade] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<InstallFromHubResponse | null>(null);

    // Sort candidates newest-first for the picker; default to the
    // suggested version if it's in the list, otherwise the newest.
    const sortedCandidates = useMemo<UpgradeCandidate[]>(() => {
        if (!upgrades.data) return [];
        return [...upgrades.data.candidates].sort(
            (a, b) => compareSemver(b.version, a.version),
        );
    }, [upgrades.data]);

    const currentVersion = upgrades.data?.current_version ?? null;

    useEffect(() => {
        if (!open || sortedCandidates.length === 0) return;
        const preferred = suggestedVersion && sortedCandidates.find(
            (c) => c.version === suggestedVersion,
        );
        const choice = preferred ?? sortedCandidates.find(
            // Default to the newest version that's strictly newer than
            // the current install. Fall back to absolute newest when
            // the operator's running on an off-catalog version.
            (c) => !currentVersion || compareSemver(c.version, currentVersion) > 0,
        );
        if (choice) setSelectedVersion(choice.version);
        else setSelectedVersion(sortedCandidates[0].version);
    }, [open, sortedCandidates, currentVersion, suggestedVersion]);

    useEffect(() => {
        if (!open) {
            setError(null);
            setResult(null);
            setForceDowngrade(false);
        }
    }, [open]);

    const chosen = sortedCandidates.find((c) => c.version === selectedVersion);
    const isDowngrade =
        !!currentVersion && !!chosen &&
        compareSemver(chosen.version, currentVersion) < 0;
    const isSameVersion =
        !!currentVersion && chosen?.version === currentVersion;

    const canUpgrade = !!chosen && !isSameVersion && (
        !isDowngrade || forceDowngrade
    );

    const handleUpgrade = async () => {
        if (!chosen) return;
        setError(null);
        setResult(null);
        try {
            const res = await upgrade.mutateAsync({
                version: chosen.version,
                force_downgrade: isDowngrade,
            });
            setResult(res);
        } catch (err) {
            setError(errText(err));
        }
    };

    const busy = upgrade.isLoading;
    const done = !!result?.success;

    return (
        <Dialog
            open={open}
            onClose={busy ? undefined : onClose}
            fullWidth
            maxWidth="sm"
        >
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <RotateCcw size={18} />
                    <span>Upgrade {pluginId}</span>
                </Stack>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                        <Chip
                            size="small"
                            label={`current: ${currentVersion ?? '(unknown)'}`}
                            variant="outlined"
                        />
                        {chosen && (
                            <Chip
                                size="small"
                                color={isDowngrade ? 'warning' : 'primary'}
                                label={`target: ${chosen.version}`}
                            />
                        )}
                    </Stack>

                    {upgrades.isLoading ? (
                        <LinearProgress />
                    ) : upgrades.isError ? (
                        <Alert severity="error">
                            Could not reach the hub to list versions.
                        </Alert>
                    ) : sortedCandidates.length === 0 ? (
                        <Alert severity="info">
                            No versions published in the hub yet.
                        </Alert>
                    ) : (
                        <FormControl size="small" fullWidth>
                            <InputLabel id="upgrade-version-label">
                                Version
                            </InputLabel>
                            <Select
                                labelId="upgrade-version-label"
                                label="Version"
                                value={selectedVersion}
                                onChange={(e) =>
                                    setSelectedVersion(String(e.target.value))
                                }
                                disabled={busy}
                            >
                                {sortedCandidates.map((c) => (
                                    <MenuItem key={c.version} value={c.version}>
                                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                                            <span>{c.version}</span>
                                            {c.version === currentVersion && (
                                                <Chip size="small" label="installed" />
                                            )}
                                            {c.requires_sdk && (
                                                <Typography
                                                    variant="caption"
                                                    sx={{ color: 'text.secondary', fontFamily: 'monospace' }}
                                                >
                                                    SDK {c.requires_sdk}
                                                </Typography>
                                            )}
                                        </Stack>
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    )}

                    {isDowngrade && (
                        <Alert severity="warning" icon={<AlertTriangle size={16} />}>
                            <AlertTitle>This would downgrade {pluginId}</AlertTitle>
                            From {currentVersion} to {chosen?.version}. Acknowledge
                            the rollback to proceed.
                            <Box sx={{ mt: 0.5 }}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={forceDowngrade}
                                            onChange={(_, v) => setForceDowngrade(v)}
                                        />
                                    }
                                    label="I understand this is a downgrade"
                                />
                            </Box>
                        </Alert>
                    )}

                    {isSameVersion && (
                        <Alert severity="info">
                            {chosen?.version} is the currently installed version.
                            Pick a different version to upgrade.
                        </Alert>
                    )}

                    {/* Warn-and-proceed for in-flight tasks. RMQ requeues
                        unacked messages when the old container is killed
                        so no data is lost, but operators should know there
                        may be duplicate work. */}
                    {chosen && !isSameVersion && (
                        <Alert severity="info" icon={false} sx={{ py: 0.5 }}>
                            In-flight tasks will be requeued — the upgrade
                            stops the current container, RMQ redelivers
                            unacked work to the new version. Expect possibly
                            duplicate execution.
                        </Alert>
                    )}

                    {busy && (
                        <Box>
                            <Typography variant="body2" sx={{ mb: 0.5 }}>
                                Upgrading {pluginId} → {chosen?.version}…
                            </Typography>
                            <LinearProgress />
                        </Box>
                    )}

                    {error && <Alert severity="error">{error}</Alert>}

                    {result?.success && (
                        <Alert severity="success">
                            <AlertTitle>{result.plugin_id} upgraded</AlertTitle>
                            now at {result.install_method} install
                            {result.install_dir && (
                                <> at <code>{result.install_dir}</code></>
                            )}
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
                <Button onClick={onClose} disabled={busy}>
                    {done ? 'Close' : 'Cancel'}
                </Button>
                {!done && (
                    <Button
                        variant="contained"
                        onClick={handleUpgrade}
                        disabled={busy || !canUpgrade}
                    >
                        {busy ? 'Upgrading…' : 'Upgrade'}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
