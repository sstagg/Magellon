import React from 'react';
import { Alert, Box, Button, Chip, CircularProgress, Typography } from '@mui/material';
import {
    Visibility as PreviewIcon,
    ErrorOutlined as ErrorIcon,
    CheckCircle as ValidIcon,
    Layers as BatchIcon,
    Send as DispatchIcon,
    School as TrainIcon,
} from '@mui/icons-material';
import type { TrainedModel } from '../../model/particleSettingsTypes.ts';

interface ConfigureActionsProps {
    canPreview: boolean;
    backendEnabled: boolean;
    isTopazBackend: boolean;
    training: boolean;
    manualTrainingCount: number;
    trainedModel: TrainedModel | null;
    isValid: boolean;
    validationErrorCount: number;
    onToggleErrors: () => void;
    onPreview: () => void;
    onTrainSession: () => void;
    onRun: () => void;
    onRunBatch?: () => void;
}

/** CONFIGURE-state toolbar actions: Preview + Train + Run + Run Batch. */
export const ConfigureActions: React.FC<ConfigureActionsProps> = ({
    canPreview,
    backendEnabled,
    isTopazBackend,
    training,
    manualTrainingCount,
    trainedModel,
    isValid,
    validationErrorCount,
    onToggleErrors,
    onPreview,
    onTrainSession,
    onRun,
    onRunBatch,
}) => (
    <>
        {!canPreview && (
            <Alert
                severity={!backendEnabled ? 'warning' : 'info'}
                sx={{ mb: 0.75, py: 0.25, '& .MuiAlert-message': { fontSize: '0.7rem' } }}
            >
                {!backendEnabled
                    ? 'This backend is disabled by the operator. Enable it in the Plugin Registry before using preview or dispatch.'
                    : isTopazBackend
                        ? 'Topaz currently runs as a queued job and saves an IPP record when it finishes. No-save preview is not available for this backend yet.'
                        : 'This backend does not advertise no-save preview; running will save an IPP record.'}
            </Alert>
        )}
        {canPreview && (
            <Button
                variant="outlined" size="small" fullWidth
                startIcon={<PreviewIcon sx={{ fontSize: 14 }} />} onClick={onPreview}
                sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, mb: 0.75 }}
            >
                Preview &amp; tune (no save)
            </Button>
        )}
        {isTopazBackend && canPreview && (
            <Button
                variant="outlined" size="small" fullWidth
                startIcon={training ? <CircularProgress size={14} /> : <TrainIcon sx={{ fontSize: 14 }} />}
                onClick={onTrainSession}
                disabled={training || manualTrainingCount === 0}
                sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, mb: 0.75 }}
            >
                Train session ({manualTrainingCount})
            </Button>
        )}
        {trainedModel && (
            <Chip
                label={`session model ${Math.round(Number(trainedModel.engine_opts?.threshold ?? -3) * 100) / 100}`}
                size="small"
                variant="outlined"
                sx={{ mb: 0.75, height: 20, fontSize: '0.62rem' }}
            />
        )}
        <Box sx={{ display: 'flex', gap: 0.75 }}>
            <Button
                variant="contained" size="small" fullWidth
                startIcon={<DispatchIcon sx={{ fontSize: 14 }} />} onClick={onRun}
                sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5 }}
            >
                {canPreview ? 'Save current image' : 'Run and save image'}
            </Button>
            {onRunBatch && (
                <Button
                    variant="outlined" size="small" fullWidth
                    startIcon={<BatchIcon sx={{ fontSize: 14 }} />}
                    onClick={onRunBatch}
                    sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5 }}
                >
                    Run batch…
                </Button>
            )}
        </Box>
        <Box sx={{ mt: 0.75, display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {isValid ? (
                <><ValidIcon sx={{ fontSize: 12, color: 'success.main' }} /><Typography
                    variant="caption"
                    sx={{
                        color: "success.main",
                        fontSize: '0.7rem'
                    }}>Ready</Typography></>
            ) : (
                <><ErrorIcon sx={{ fontSize: 12, color: 'warning.main' }} />
                <Typography
                    variant="caption"
                    onClick={onToggleErrors}
                    sx={{
                        color: "warning.main",
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        fontSize: '0.7rem'
                    }}>
                    {validationErrorCount} issue{validationErrorCount !== 1 ? 's' : ''}
                </Typography></>
            )}
        </Box>
    </>
);
