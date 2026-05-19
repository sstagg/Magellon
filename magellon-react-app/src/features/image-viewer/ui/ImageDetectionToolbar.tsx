import React, { useEffect, useMemo, useRef, useState } from 'react';
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
import ImageInfoDto from '../../../entities/image/types.ts';
import {
    DetectionResult,
    dispatchPtolemyDetection,
    getImageDetections,
    getJobStatus,
    PtolemyDetectionMode,
    PtolemyDispatchResponse,
} from '../api/PtolemyDetectionService.ts';

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
    return `/gpfs/home/${sessionName.toLowerCase()}/original/${imageNameWithExtension(image.name)}`;
}

const MODE_LABEL: Record<PtolemyDetectionMode, string> = {
    square: 'Square detection',
    hole: 'Hole detection',
};

const POLL_INTERVAL_MS = 2_000;
const POLL_MAX_ATTEMPTS = 60;   // 2 min timeout

export const ImageDetectionToolbar: React.FC<ImageDetectionToolbarProps> = ({
    selectedImage,
    sessionName,
    onDetectionComplete,
}) => {
    const [busyMode, setBusyMode] = useState<PtolemyDetectionMode | null>(null);
    const [polling, setPolling] = useState(false);
    const [lastDispatch, setLastDispatch] = useState<PtolemyDispatchResponse | null>(null);
    const [actionsAnchor, setActionsAnchor] = useState<HTMLElement | null>(null);
    const [snackbar, setSnackbar] = useState<SnackbarState>({
        open: false,
        message: '',
        severity: 'info',
    });
    const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollAttemptsRef = useRef(0);

    const imagePath = useMemo(
        () => buildImagePath(selectedImage, sessionName),
        [selectedImage, sessionName],
    );

    // Cancel any ongoing poll when the image changes
    useEffect(() => {
        return () => {
            if (pollTimerRef.current !== null) {
                clearTimeout(pollTimerRef.current);
                pollTimerRef.current = null;
            }
            setPolling(false);
        };
    }, [selectedImage.oid]);

    const pollUntilDone = (jobId: string, imageId: string) => {
        pollAttemptsRef.current = 0;
        setPolling(true);

        const tick = async () => {
            if (pollAttemptsRef.current >= POLL_MAX_ATTEMPTS) {
                setPolling(false);
                setSnackbar({ open: true, message: 'Detection timed out waiting for result', severity: 'warning' });
                return;
            }
            pollAttemptsRef.current += 1;

            try {
                const statusResp = await getJobStatus(jobId);
                const status = statusResp.data.status;

                if (status === 'completed') {
                    setPolling(false);
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
                } else if (status === 'failed' || status === 'cancelled') {
                    setPolling(false);
                    setSnackbar({ open: true, message: `Detection ${status}`, severity: 'error' });
                } else {
                    pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
                }
            } catch {
                // network hiccup — retry
                pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS * 2);
            }
        };

        pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    };

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
                pollUntilDone(response.data.job_id, selectedImage.oid);
            }
        } catch (error: any) {
            setSnackbar({
                open: true,
                message: error?.response?.data?.detail || error?.message || `${MODE_LABEL[mode]} failed`,
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
