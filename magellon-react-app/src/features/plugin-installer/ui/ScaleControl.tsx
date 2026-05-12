/**
 * ScaleControl — operator-facing scale slider for multi-replica plugins
 * (Wave 4).
 *
 * Renders a small chip showing current replica count + open-dialog
 * action. Dialog: number stepper with manifest min/max guard rails,
 * Apply button that POSTs to /admin/plugins/{id}/scale.
 *
 * Docker-only — for uv-installed plugins the parent should hide the
 * chip entirely (the scale endpoint returns 422 with the docker-only
 * message regardless, so we keep this component a no-op if the parent
 * forgets — but it's cleaner UX to not render the trigger at all).
 *
 * The "current count" we display is the live bus-announced count from
 * `usePluginReplicas`, not the manifest's `desired` — what's *running*
 * is what matters operationally, and the two can disagree mid-scale.
 */
import React, { useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    LinearProgress,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import { Layers, Minus, Plus } from 'lucide-react';
import { usePluginReplicas } from '../../plugin-runner/api/PluginApi.ts';
import { useScalePlugin } from '../api/installerApi.ts';

interface ScaleControlProps {
    /** The runtime plugin_id used by the bus / live registry. */
    pluginId: string;
    /** The manifest plugin_id used by admin endpoints. May equal
     *  pluginId when no rename is in effect. */
    manifestPluginId: string;
    /** Minimum replicas allowed (from manifest.resources.replicas.min).
     *  Default 1 — single-instance plugins shouldn't render this control;
     *  the parent gates with replicas.max > 1. */
    min?: number;
    /** Maximum replicas allowed (from manifest.resources.replicas.max). */
    max: number;
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
    return 'Scale failed.';
};

export const ScaleControl: React.FC<ScaleControlProps> = ({
    pluginId, manifestPluginId, min = 1, max,
}) => {
    const { data: replicas } = usePluginReplicas(pluginId);
    const scale = useScalePlugin(manifestPluginId);
    const [open, setOpen] = useState(false);
    const liveCount = replicas?.length ?? 0;
    const [desired, setDesired] = useState<number>(Math.max(min, liveCount));
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    const openDialog = () => {
        setError(null);
        setSuccessMsg(null);
        setDesired(Math.max(min, Math.min(max, liveCount || 1)));
        setOpen(true);
    };

    const applyScale = async () => {
        setError(null);
        setSuccessMsg(null);
        if (desired < min || desired > max) {
            setError(`Desired count must be in [${min}, ${max}].`);
            return;
        }
        try {
            const res = await scale.mutateAsync({ desired });
            setSuccessMsg(`Scaled ${manifestPluginId} → ${res.desired} replicas`);
        } catch (err) {
            setError(errText(err));
        }
    };

    const busy = scale.isLoading;

    return (
        <>
            <Tooltip
                title={
                    max > 1
                        ? `Scale ${manifestPluginId} (${min}–${max} replicas; ${liveCount} live)`
                        : 'Single-instance plugin'
                }
            >
                <Chip
                    size="small"
                    icon={<Layers size={12} />}
                    label={`${liveCount} / ${max}`}
                    variant="outlined"
                    onClick={max > 1 ? openDialog : undefined}
                    clickable={max > 1}
                    data-testid="scale-control-chip"
                />
            </Tooltip>
            <Dialog open={open} onClose={busy ? undefined : () => setOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                        <Layers size={18} />
                        <span>Scale {manifestPluginId}</span>
                    </Stack>
                </DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <Typography variant="body2">
                            Currently <strong>{liveCount}</strong> replica
                            {liveCount === 1 ? '' : 's'} announcing. Bounds:{' '}
                            <code>[{min}, {max}]</code>.
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <IconButton
                                size="small"
                                onClick={() => setDesired((d) => Math.max(min, d - 1))}
                                disabled={busy || desired <= min}
                                aria-label="decrement"
                            >
                                <Minus size={14} />
                            </IconButton>
                            <TextField
                                size="small"
                                type="number"
                                value={desired}
                                onChange={(e) => {
                                    const n = parseInt(e.target.value, 10);
                                    if (!Number.isNaN(n)) setDesired(n);
                                }}
                                slotProps={{ htmlInput: { min, max } }}
                                sx={{ width: 100 }}
                                disabled={busy}
                            />
                            <IconButton
                                size="small"
                                onClick={() => setDesired((d) => Math.min(max, d + 1))}
                                disabled={busy || desired >= max}
                                aria-label="increment"
                            >
                                <Plus size={14} />
                            </IconButton>
                        </Stack>
                        {desired < liveCount && (
                            <Alert severity="info" icon={false} sx={{ py: 0.5 }}>
                                Scale-down stops {liveCount - desired} replica
                                {liveCount - desired === 1 ? '' : 's'} immediately.
                                In-flight tasks on those replicas will be requeued
                                to the survivors.
                            </Alert>
                        )}
                        {busy && (
                            <Box>
                                <Typography variant="body2">Applying…</Typography>
                                <LinearProgress />
                            </Box>
                        )}
                        {error && <Alert severity="error">{error}</Alert>}
                        {successMsg && <Alert severity="success">{successMsg}</Alert>}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpen(false)} disabled={busy}>
                        Close
                    </Button>
                    <Button
                        variant="contained"
                        onClick={applyScale}
                        disabled={busy || desired === liveCount}
                    >
                        Apply
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};
