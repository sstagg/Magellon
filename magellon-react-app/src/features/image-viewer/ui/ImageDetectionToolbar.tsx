import React, { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Divider,
    IconButton,
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
    dispatchPtolemyDetection,
    PtolemyDetectionMode,
    PtolemyDispatchResponse,
} from '../api/PtolemyDetectionService.ts';

interface ImageDetectionToolbarProps {
    selectedImage: ImageInfoDto;
    sessionName: string;
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

export const ImageDetectionToolbar: React.FC<ImageDetectionToolbarProps> = ({
    selectedImage,
    sessionName,
}) => {
    const [busyMode, setBusyMode] = useState<PtolemyDetectionMode | null>(null);
    const [lastDispatch, setLastDispatch] = useState<PtolemyDispatchResponse | null>(null);
    const [actionsAnchor, setActionsAnchor] = useState<HTMLElement | null>(null);
    const [snackbar, setSnackbar] = useState<SnackbarState>({
        open: false,
        message: '',
        severity: 'info',
    });

    const imagePath = useMemo(
        () => buildImagePath(selectedImage, sessionName),
        [selectedImage, sessionName],
    );

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

    const disabled = !selectedImage.name || !sessionName || !!busyMode;

    return (
        <>
            <Paper elevation={1} sx={{ px: 1, py: 0.5, width: '100%' }}>
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
                                color="success"
                                variant="outlined"
                                label={lastDispatch.category}
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
