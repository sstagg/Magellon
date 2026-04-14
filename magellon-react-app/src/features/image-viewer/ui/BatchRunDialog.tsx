import React, { useEffect, useMemo, useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Box,
    Typography,
    LinearProgress,
    Alert,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Checkbox,
    Divider,
    CircularProgress,
    Chip,
    IconButton,
    Stack,
} from '@mui/material';
import {
    Close as CloseIcon,
    CheckCircle as CheckIcon,
    ErrorOutline as ErrorIcon,
    SkipNext as SkipIcon,
} from '@mui/icons-material';
import { settings } from '../../../shared/config/settings.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import ImageInfoDto from '../../../entities/image/types.ts';
import { TEMPLATE_PICKER_PATH } from '../lib/useParticleOperations.ts';

const API_URL = settings.ConfigData.SERVER_API_URL;

interface BatchImage {
    oid: string;
    name: string;
    magnification: number | null;
    dimension_x: number | null;
    dimension_y: number | null;
    pixel_size: number | null;
}

interface BatchItemResult {
    image_oid: string;
    image_name: string;
    num_particles: number;
    status: 'done' | 'skipped' | 'error';
    error?: string | null;
}

interface BatchRunDialogProps {
    open: boolean;
    onClose: () => void;
    sessionName: string;
    currentImage: ImageInfoDto | null;
    pickerParams: Record<string, any>;
    onComplete?: (result: { succeeded: number; failed: number; total: number }) => void;
}

export const BatchRunDialog: React.FC<BatchRunDialogProps> = ({
    open,
    onClose,
    sessionName,
    currentImage,
    pickerParams,
    onComplete,
}) => {
    const { sid, on } = useSocket();

    const defaultMag = currentImage?.mag ?? 0;
    const [magnification, setMagnification] = useState<number>(defaultMag);
    const [tolerance, setTolerance] = useState<number>(0);
    const [ippName, setIppName] = useState<string>('Auto-pick batch');

    const [candidates, setCandidates] = useState<BatchImage[]>([]);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [loadingList, setLoadingList] = useState(false);
    const [listError, setListError] = useState<string | null>(null);

    const [launching, setLaunching] = useState(false);
    const [running, setRunning] = useState(false);
    const [progress, setProgress] = useState<number>(0);
    const [progressMessage, setProgressMessage] = useState<string>('');
    const [jobId, setJobId] = useState<string | null>(null);
    const [itemResults, setItemResults] = useState<BatchItemResult[]>([]);
    const [finalResult, setFinalResult] = useState<{ succeeded: number; failed: number; total: number } | null>(null);
    const [runError, setRunError] = useState<string | null>(null);

    // Reset when opening
    useEffect(() => {
        if (open) {
            setMagnification(currentImage?.mag ?? 0);
            setTolerance(0);
            setIppName('Auto-pick batch');
            setProgress(0);
            setProgressMessage('');
            setJobId(null);
            setItemResults([]);
            setFinalResult(null);
            setRunError(null);
            setRunning(false);
            setLaunching(false);
        }
    }, [open, currentImage?.oid]);

    // Fetch matching images when query changes
    useEffect(() => {
        if (!open || !sessionName || !magnification) return;
        let cancelled = false;
        setLoadingList(true);
        setListError(null);
        const token = localStorage.getItem('access_token');
        const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const url =
            `${API_URL}${TEMPLATE_PICKER_PATH}/session-images` +
            `?session_name=${encodeURIComponent(sessionName)}` +
            `&magnification=${encodeURIComponent(String(magnification))}` +
            `&tolerance=${encodeURIComponent(String(tolerance))}`;
        fetch(url, { headers: authHeader })
            .then(async (res) => {
                if (!res.ok) {
                    const err = await res.json().catch(() => ({ detail: res.statusText }));
                    throw new Error(err.detail || `${res.status}`);
                }
                return res.json();
            })
            .then((data) => {
                if (cancelled) return;
                const list: BatchImage[] = data.images || data || [];
                setCandidates(list);
                setSelected(new Set(list.map((img) => img.oid)));
            })
            .catch((err) => {
                if (cancelled) return;
                setListError(err.message || 'Failed to load matching images');
                setCandidates([]);
                setSelected(new Set());
            })
            .finally(() => {
                if (!cancelled) setLoadingList(false);
            });
        return () => { cancelled = true; };
    }, [open, sessionName, magnification, tolerance]);

    // Subscribe to job updates and live log lines for this batch job
    useEffect(() => {
        if (!jobId) return;

        const offJob = on('job_update', (envelope: any) => {
            if (envelope?.job_id !== jobId) return;
            if (typeof envelope.progress === 'number') setProgress(envelope.progress);
            if (envelope.status === 'completed') {
                const final = envelope.result;
                if (final) {
                    setFinalResult({
                        total: final.total ?? 0,
                        succeeded: final.succeeded ?? 0,
                        failed: final.failed ?? 0,
                    });
                    if (Array.isArray(final.items)) setItemResults(final.items);
                    onComplete?.({
                        total: final.total ?? 0,
                        succeeded: final.succeeded ?? 0,
                        failed: final.failed ?? 0,
                    });
                }
                setRunning(false);
            }
            if (envelope.status === 'failed') {
                setRunError(envelope.error || 'Batch run failed');
                setRunning(false);
            }
        });

        const offLog = on('log_entry', (entry: any) => {
            if (entry?.source !== 'batch-picking') return;
            if (entry?.message) setProgressMessage(entry.message);
        });

        return () => {
            offJob();
            offLog();
        };
    }, [jobId, on, onComplete]);

    const toggleSelected = (oid: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(oid)) next.delete(oid);
            else next.add(oid);
            return next;
        });
    };

    const selectAll = () => setSelected(new Set(candidates.map((c) => c.oid)));
    const selectNone = () => setSelected(new Set());

    const selectedList = useMemo(
        () => candidates.filter((c) => selected.has(c.oid)),
        [candidates, selected],
    );

    const handleLaunch = async () => {
        if (selectedList.length === 0) return;
        setLaunching(true);
        setRunError(null);
        setItemResults([]);
        setFinalResult(null);
        setProgress(0);
        setProgressMessage('Queueing…');

        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        const picker_params = { ...pickerParams };
        delete picker_params.image_path;
        Object.keys(picker_params).forEach((k) => {
            if (picker_params[k] === null || picker_params[k] === undefined) delete picker_params[k];
        });

        const body = {
            session_name: sessionName,
            images: selectedList.map((img) => ({ oid: img.oid, name: img.name })),
            picker_params,
            ipp_name: ippName,
        };

        try {
            const url =
                `${API_URL}${TEMPLATE_PICKER_PATH}/batch` +
                (sid ? `?sid=${encodeURIComponent(sid)}` : '');
            const res = await fetch(url, {
                method: 'POST',
                headers,
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `${res.status}`);
            }
            const data = await res.json();
            setJobId(data.job_id || data.jobId || null);
            setRunning(true);
        } catch (err: any) {
            setRunError(err.message || 'Failed to launch batch');
        } finally {
            setLaunching(false);
        }
    };

    const canEdit = !running && !finalResult;
    const canClose = !running;

    return (
        <Dialog open={open} onClose={canClose ? onClose : undefined} maxWidth="md" fullWidth>
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pr: 1 }}>
                <Box sx={{ flex: 1 }}>Run batch auto-picking</Box>
                <IconButton size="small" onClick={onClose} disabled={!canClose}>
                    <CloseIcon fontSize="small" />
                </IconButton>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Session
                        </Typography>
                        <Typography variant="body2">{sessionName || '—'}</Typography>
                    </Box>

                    <Stack direction="row" spacing={2}>
                        <TextField
                            label="Magnification"
                            type="number"
                            size="small"
                            value={magnification}
                            onChange={(e) => setMagnification(Number(e.target.value) || 0)}
                            disabled={!canEdit}
                            fullWidth
                        />
                        <TextField
                            label="Tolerance (±)"
                            type="number"
                            size="small"
                            value={tolerance}
                            onChange={(e) => setTolerance(Math.max(0, Number(e.target.value) || 0))}
                            disabled={!canEdit}
                            fullWidth
                            helperText="0 = exact match"
                        />
                        <TextField
                            label="IPP name"
                            size="small"
                            value={ippName}
                            onChange={(e) => setIppName(e.target.value)}
                            disabled={!canEdit}
                            fullWidth
                        />
                    </Stack>

                    {listError && <Alert severity="error">{listError}</Alert>}

                    <Box>
                        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                            <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                                {loadingList ? 'Loading matching images…'
                                    : `${candidates.length} matching image${candidates.length === 1 ? '' : 's'} · ${selected.size} selected`}
                            </Typography>
                            <Button size="small" onClick={selectAll} disabled={!canEdit || candidates.length === 0}>
                                Select all
                            </Button>
                            <Button size="small" onClick={selectNone} disabled={!canEdit || selected.size === 0}>
                                Select none
                            </Button>
                        </Stack>
                        <Box sx={{ maxHeight: 240, overflowY: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                            {loadingList ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                                    <CircularProgress size={20} />
                                </Box>
                            ) : candidates.length === 0 ? (
                                <Box sx={{ py: 3, textAlign: 'center' }}>
                                    <Typography variant="caption" color="text.secondary">
                                        No matching images found in this session.
                                    </Typography>
                                </Box>
                            ) : (
                                <List dense disablePadding>
                                    {candidates.map((img) => {
                                        const result = itemResults.find((r) => r.image_oid === img.oid);
                                        const isCurrent = currentImage?.oid === img.oid;
                                        return (
                                            <ListItem
                                                key={img.oid}
                                                onClick={canEdit ? () => toggleSelected(img.oid) : undefined}
                                                sx={{ cursor: canEdit ? 'pointer' : 'default', py: 0.25 }}
                                                secondaryAction={
                                                    result ? (
                                                        result.status === 'done' ? (
                                                            <Chip size="small" icon={<CheckIcon sx={{ fontSize: 14 }} />} color="success"
                                                                label={`${result.num_particles} picks`} variant="outlined" />
                                                        ) : result.status === 'skipped' ? (
                                                            <Chip size="small" icon={<SkipIcon sx={{ fontSize: 14 }} />}
                                                                label="skipped" variant="outlined" />
                                                        ) : (
                                                            <Chip size="small" icon={<ErrorIcon sx={{ fontSize: 14 }} />} color="error"
                                                                label={result.error || 'error'} variant="outlined" />
                                                        )
                                                    ) : null
                                                }
                                            >
                                                <ListItemIcon sx={{ minWidth: 32 }}>
                                                    <Checkbox
                                                        edge="start"
                                                        size="small"
                                                        checked={selected.has(img.oid)}
                                                        disabled={!canEdit}
                                                        tabIndex={-1}
                                                        disableRipple
                                                    />
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={
                                                        <Stack direction="row" spacing={1} alignItems="center">
                                                            <Typography variant="body2" noWrap>{img.name}</Typography>
                                                            {isCurrent && <Chip size="small" label="current" variant="outlined" sx={{ height: 18, fontSize: 10 }} />}
                                                        </Stack>
                                                    }
                                                    secondary={
                                                        <Typography variant="caption" color="text.secondary">
                                                            mag {img.magnification ?? '—'}
                                                            {img.pixel_size != null ? ` · ${img.pixel_size.toFixed(3)} Å/px` : ''}
                                                            {img.dimension_x && img.dimension_y ? ` · ${img.dimension_x}×${img.dimension_y}` : ''}
                                                        </Typography>
                                                    }
                                                />
                                            </ListItem>
                                        );
                                    })}
                                </List>
                            )}
                        </Box>
                    </Box>

                    {(running || finalResult || progress > 0) && (
                        <>
                            <Divider />
                            <Box>
                                <Typography variant="caption" color="text.secondary">
                                    {running ? progressMessage || 'Running…' :
                                        finalResult ? `Done — ${finalResult.succeeded} succeeded, ${finalResult.failed} failed` :
                                        progressMessage}
                                </Typography>
                                <LinearProgress
                                    variant="determinate"
                                    value={Math.min(100, Math.max(0, progress))}
                                    sx={{ mt: 0.5, height: 6, borderRadius: 1 }}
                                />
                            </Box>
                        </>
                    )}

                    {runError && <Alert severity="error">{runError}</Alert>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={!canClose}>
                    {finalResult ? 'Close' : 'Cancel'}
                </Button>
                <Button
                    variant="contained"
                    onClick={handleLaunch}
                    disabled={!canEdit || selectedList.length === 0 || launching || loadingList}
                    startIcon={launching ? <CircularProgress size={14} color="inherit" /> : null}
                >
                    {launching ? 'Launching…' : `Launch on ${selectedList.length} image${selectedList.length === 1 ? '' : 's'}`}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
