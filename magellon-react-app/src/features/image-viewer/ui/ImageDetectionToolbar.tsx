import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Divider,
    IconButton,
    LinearProgress,
    Menu,
    MenuItem,
    Paper,
    Snackbar,
    Tooltip,
} from '@mui/material';
import {
    Apps as SquareIcon,
    BlurCircular as HoleIcon,
    MoreVert,
} from '@mui/icons-material';
import type ImageInfoDto from '../../../entities/image/types.ts';
import type {
    DetectionResult,
    PtolemyDetectionMode,
    PtolemyDispatchResponse} from '../api/PtolemyDetectionService.ts';
import {
    dispatchPtolemyDetection,
    getImageDetections,
    getJobStatus
} from '../api/PtolemyDetectionService.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import { apiErrorMessage } from '../../../shared/api/apiError.ts';

interface ImageDetectionToolbarProps {
    selectedImage: ImageInfoDto;
    sessionName: string;
    onDetectionComplete?: (result: DetectionResult) => void;
}

type SnackbarState = {
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
};

function imageNameWithExtension(name: string): string {
    return /\.[a-z0-9]+$/i.test(name) ? name : `${name}.mrc`;
}

function buildImagePath(image: ImageInfoDto, sessionName: string): string | null {
    if (image.path) return image.path;
    if (!image.name || !sessionName) return null;
    return `/gpfs/${sessionName.toLowerCase()}/home/original/${imageNameWithExtension(image.name)}`;
}

const MODE_LABEL: Record<PtolemyDetectionMode, string> = {
    square: 'Square detection',
    hole: 'Hole detection',
};

// HTTP poll fallback interval / max attempts — only fires when socket.io
// is unavailable or the completion event is missed during a reconnect.
const POLL_INTERVAL_MS = 3_000;
const POLL_MAX_ATTEMPTS = 40;   // 2 min timeout

export const ImageDetectionToolbar: React.FC<ImageDetectionToolbarProps> = ({
    selectedImage,
    sessionName,
    onDetectionComplete,
}) => {
    const { emit, on, connected } = useSocket();

    const [busyMode, setBusyMode] = useState<PtolemyDetectionMode | null>(null);
    const [polling, setPolling] = useState(false);
    const [lastDispatch, setLastDispatch] = useState<PtolemyDispatchResponse | null>(null);
    const [actionsAnchor, setActionsAnchor] = useState<HTMLElement | null>(null);
    const [snackbar, setSnackbar] = useState<SnackbarState>({
        open: false,
        message: '',
        severity: 'info',
    });

    // Refs for current job so the stable socket listener can access them
    // without causing useEffect re-runs.
    const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollAttemptsRef = useRef(0);
    const activeJobRef = useRef<{ jobId: string; imageId: string } | null>(null);

    const imagePath = useMemo(
        () => buildImagePath(selectedImage, sessionName),
        [selectedImage, sessionName],
    );

    const clearPoll = useCallback(() => {
        if (pollTimerRef.current !== null) {
            clearTimeout(pollTimerRef.current);
            pollTimerRef.current = null;
        }
    }, []);

    // Cancel any running poll/subscription on image change
    useEffect(() => {
        return () => {
            clearPoll();
            if (activeJobRef.current) {
                emit('leave_job_room', { job_id: activeJobRef.current.jobId });
                activeJobRef.current = null;
            }
            setPolling(false);
        };
    }, [selectedImage.oid]);  // eslint-disable-line react-hooks/exhaustive-deps

    const handleDetectionResult = useCallback(async (imageId: string) => {
        try {
            const detResp = await getImageDetections(imageId);
            const result = detResp.data;
            onDetectionComplete?.(result);
            setSnackbar({
                open: true,
                message: `Found ${result.detections.length} ${result.category === 'SquareDetection' ? 'square' : 'hole'}(s)`,
                severity: 'success',
            });
        } catch {
            setSnackbar({ open: true, message: 'Detection done but could not fetch results', severity: 'warning' });
        }
    }, [onDetectionComplete]);

    // Stable socket.io listener — fires as soon as CoreService's
    // TaskOutputProcessor emits import_progress after writing the result.
    useEffect(() => {
        const off = on<{ job_id?: string; event?: string; status?: string }>('import_progress', (data) => {
            const active = activeJobRef.current;
            if (!active || data?.job_id !== active.jobId) return;
            if (data?.event !== 'task_complete') return;

            clearPoll();
            setPolling(false);
            activeJobRef.current = null;
            emit('leave_job_room', { job_id: active.jobId });

            if (data.status === 'completed') {
                handleDetectionResult(active.imageId);
            } else {
                setSnackbar({ open: true, message: `Detection ${data.status ?? 'failed'}`, severity: 'error' });
            }
        });
        return off;
    }, [on, emit, clearPoll, handleDetectionResult]);

    // Join/leave job room when a job becomes active and socket connects
    useEffect(() => {
        const active = activeJobRef.current;
        if (!connected || !active) return;
        emit('join_job_room', { job_id: active.jobId });
    }, [connected, emit, polling]);  // `polling` toggling = job started/stopped

    // HTTP fallback poll — runs in parallel with socket.io but backs off
    // as socket.io normally delivers first.
    const startFallbackPoll = useCallback((jobId: string, imageId: string) => {
        pollAttemptsRef.current = 0;

        const tick = async () => {
            // If socket.io already resolved this job, bail out.
            if (!activeJobRef.current || activeJobRef.current.jobId !== jobId) return;

            if (pollAttemptsRef.current >= POLL_MAX_ATTEMPTS) {
                setPolling(false);
                activeJobRef.current = null;
                setSnackbar({ open: true, message: 'Detection timed out waiting for result', severity: 'warning' });
                return;
            }
            pollAttemptsRef.current += 1;

            try {
                const statusResp = await getJobStatus(jobId);
                const status = statusResp.data.status;

                if (status === 'completed') {
                    clearPoll();
                    setPolling(false);
                    activeJobRef.current = null;
                    emit('leave_job_room', { job_id: jobId });
                    await handleDetectionResult(imageId);
                } else if (status === 'failed' || status === 'cancelled') {
                    clearPoll();
                    setPolling(false);
                    activeJobRef.current = null;
                    setSnackbar({ open: true, message: `Detection ${status}`, severity: 'error' });
                } else {
                    pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
                }
            } catch {
                pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS * 2);
            }
        };

        pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    }, [clearPoll, emit, handleDetectionResult]);

    const dispatch = async (mode: PtolemyDetectionMode) => {
        if (!imagePath) {
            setSnackbar({
                open: true,
                message: 'Cannot dispatch detection without an image path',
                severity: 'warning',
            });
            return;
        }

        setBusyMode(mode);
        try {
            const response = await dispatchPtolemyDetection(mode, {
                image_path: imagePath,
                image_id: selectedImage.oid,
                session_name: sessionName,
            });
            setLastDispatch(response.data);
            setSnackbar({
                open: true,
                message: `${MODE_LABEL[mode]} dispatched`,
                severity: 'success',
            });
            if (selectedImage.oid) {
                const jobId = response.data.job_id;
                const imageId = selectedImage.oid;
                activeJobRef.current = { jobId, imageId };
                setPolling(true);
                // Subscribe via socket.io (primary)
                emit('join_job_room', { job_id: jobId });
                // HTTP poll as fallback
                startFallbackPoll(jobId, imageId);
            }
        } catch (error) {
            setSnackbar({
                open: true,
                message: apiErrorMessage(error, `${MODE_LABEL[mode]} failed`),
                severity: 'error',
            });
        } finally {
            setBusyMode(null);
            setActionsAnchor(null);
        }
    };

    const disabled = !selectedImage.name || !sessionName || !!busyMode || polling;

    return (
        <>
            <Paper elevation={1} sx={{ px: 1, py: 0.5, width: '100%' }}>
                {polling && <LinearProgress sx={{ height: 2, mb: 0.25 }} />}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                    <Tooltip title="Run Ptolemy square detection">
                        <span>
                            <IconButton
                                size="small"
                                color="primary"
                                onClick={() => dispatch('square')}
                                disabled={disabled}
                                aria-label="Run square detection"
                                sx={{ p: 0.35 }}
                            >
                                {busyMode === 'square' ? <CircularProgress size={16} /> : <SquareIcon sx={{ fontSize: 17 }} />}
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Run Ptolemy hole detection">
                        <span>
                            <IconButton
                                size="small"
                                color="primary"
                                onClick={() => dispatch('hole')}
                                disabled={disabled}
                                aria-label="Run hole detection"
                                sx={{ p: 0.35 }}
                            >
                                {busyMode === 'hole' ? <CircularProgress size={16} /> : <HoleIcon sx={{ fontSize: 17 }} />}
                            </IconButton>
                        </span>
                    </Tooltip>

                    <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

                    {lastDispatch ? (
                        <>
                            <Chip
                                size="small"
                                color={polling ? 'default' : 'success'}
                                variant="outlined"
                                label={polling ? `${lastDispatch.category} running…` : lastDispatch.category}
                                sx={{ height: 22, fontSize: '0.68rem' }}
                            />
                            <Chip
                                size="small"
                                label={`job ${lastDispatch.job_id.slice(0, 8)}`}
                                sx={{ height: 22, fontSize: '0.68rem' }}
                            />
                        </>
                    ) : (
                        <Chip
                            size="small"
                            variant="outlined"
                            label="Ptolemy"
                            sx={{ height: 22, fontSize: '0.68rem' }}
                        />
                    )}

                    <Box sx={{ flex: 1 }} />

                    <Tooltip title="Detection actions">
                        <span>
                            <IconButton
                                size="small"
                                onClick={(event) => setActionsAnchor(event.currentTarget)}
                                disabled={disabled}
                                aria-label="Detection actions"
                                sx={{ p: 0.25 }}
                            >
                                <MoreVert sx={{ fontSize: 18 }} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Menu
                        anchorEl={actionsAnchor}
                        open={Boolean(actionsAnchor)}
                        onClose={() => setActionsAnchor(null)}
                        slotProps={{ paper: { sx: { minWidth: 200 } } }}
                    >
                        <MenuItem onClick={() => dispatch('square')}>
                            <SquareIcon sx={{ fontSize: 18, mr: 1 }} /> Square detection
                        </MenuItem>
                        <MenuItem onClick={() => dispatch('hole')}>
                            <HoleIcon sx={{ fontSize: 18, mr: 1 }} /> Hole detection
                        </MenuItem>
                    </Menu>
                </Box>
            </Paper>

            <Snackbar
                open={snackbar.open}
                autoHideDuration={3500}
                onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            >
                <Alert
                    severity={snackbar.severity}
                    onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
                    sx={{ width: '100%' }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </>
    );
};
