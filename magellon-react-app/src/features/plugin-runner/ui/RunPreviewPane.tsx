import React from 'react';
import { Alert, Box, Chip, CircularProgress, Typography } from '@mui/material';
import { Image as ImageIcon } from 'lucide-react';
import type { Job } from '../../../shared/lib/stores/useJobStore.ts';
import type { PreviewState } from '../model/usePreviewState.ts';
import { ProgressTracker } from './ProgressTracker.tsx';
import { ResultRenderer } from './results/ResultRenderers.tsx';
import { RunStatusBanner } from './RunStatusBanner.tsx';
import { ZoomablePreview } from './ZoomablePreview.tsx';
import { ParticleOverlay } from './ParticleOverlay.tsx';

interface RunPreviewPaneProps {
    pluginId: string;
    usePreviewMode: boolean;
    /** Pre-formatted submit error, when the last job submission failed. */
    submitError: string | null;
    preview: PreviewState;
    tunableKeys: Set<string>;
    currentJob?: Job;
    currentJobId: string | null;
    values: Record<string, unknown>;
}

/** Right-hand column: run status, test-image preview, and plugin results. */
export const RunPreviewPane: React.FC<RunPreviewPaneProps> = ({
    pluginId,
    usePreviewMode,
    submitError,
    preview,
    tunableKeys,
    currentJob,
    currentJobId,
    values,
}) => {
    const { previewUrl, previewError, previewResult, previewRunError, retuning, previewStale } = preview;
    const displayedResult = usePreviewMode ? previewResult : currentJob?.result;
    const showsResult = usePreviewMode ? !!previewResult : currentJob?.status === 'completed';

    return (
        <Box sx={{ position: { md: 'sticky' }, top: { md: 16 } }}>
            {!usePreviewMode && submitError && (
                <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                    {submitError}
                </Alert>
            )}
            {usePreviewMode && previewRunError && (
                <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                    {previewRunError}
                </Alert>
            )}
            {usePreviewMode && previewResult && (
                <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Chip size="small" color="success"
                        label={`${previewResult.num_particles} particle${previewResult.num_particles === 1 ? '' : 's'}`} />
                    {retuning && (
                        <Chip size="small" color="info" icon={<CircularProgress size={10} color="inherit" />} label="Retuning…" />
                    )}
                    {previewStale && !retuning && (
                        <Chip size="small" color="warning" label="Preview stale — re-run Preview" />
                    )}
                    {!retuning && !previewStale && tunableKeys.size > 0 && (
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            Live tune: {tunableKeys.size} field{tunableKeys.size === 1 ? '' : 's'}
                        </Typography>
                    )}
                </Box>
            )}
            {!usePreviewMode && currentJob && (
                <RunStatusBanner job={currentJob} />
            )}
            {!usePreviewMode && currentJobId && (
                <ProgressTracker jobId={currentJobId} />
            )}
            <Typography
                variant="overline"
                sx={{
                    color: "text.secondary",
                    letterSpacing: 0.5,
                    display: 'block',
                    mb: 0.5
                }}>
                Preview
            </Typography>
            {previewError ? (
                <Alert severity="warning">{previewError}</Alert>
            ) : previewUrl ? (
                <Box
                    sx={{
                        borderRadius: 1,
                        overflow: 'hidden',
                        bgcolor: 'grey.900',
                        boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.06)',
                        display: 'flex',
                        justifyContent: 'center',
                    }}
                >
                    <ZoomablePreview
                        src={previewUrl}
                        overlay={
                            <ParticleOverlay
                                result={showsResult ? displayedResult ?? null : null}
                                diameterAngstrom={Number(values['diameter_angstrom']) || undefined}
                                imagePixelSize={Number(values['image_pixel_size']) || undefined}
                            />
                        }
                    />
                </Box>
            ) : (
                <Box
                    sx={{
                        border: '1px dashed',
                        borderColor: 'divider',
                        borderRadius: 1,
                        py: 5,
                        px: 3,
                        textAlign: 'center',
                        color: 'text.secondary',
                        bgcolor: 'action.hover',
                    }}
                >
                    <ImageIcon size={28} style={{ opacity: 0.5 }} />
                    <Typography variant="body2" sx={{ mt: 1 }}>
                        No test image selected
                    </Typography>
                    <Typography variant="caption">
                        Pick one above to preview it here.
                    </Typography>
                </Box>
            )}

            {showsResult && displayedResult && (
                <Box sx={{ mt: 2 }}>
                    <ResultRenderer pluginId={pluginId} result={displayedResult} />
                </Box>
            )}
        </Box>
    );
};
