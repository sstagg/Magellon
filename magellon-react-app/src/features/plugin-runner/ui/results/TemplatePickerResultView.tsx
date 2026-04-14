import React from 'react';
import {
    Box,
    Card,
    CardContent,
    Chip,
    Stack,
    Typography,
} from '@mui/material';

interface ParticlePick {
    x: number;
    y: number;
    score: number;
    template_index?: number;
}

interface TemplatePickerOutput {
    particles?: ParticlePick[];
    num_particles?: number;
    num_templates?: number;
    image_binning?: number;
    target_pixel_size?: number;
}

/**
 * Renders a small summary for template-picker runs: counts plus the score
 * distribution of the returned particles. The full picked-overlay on the
 * micrograph lives in the image viewer — this is the plugin-runner quick view.
 */
export const TemplatePickerResultView: React.FC<{ result: TemplatePickerOutput }> = ({ result }) => {
    const particles = result.particles ?? [];
    const scores = particles.map((p) => p.score).filter((s) => Number.isFinite(s));
    const minScore = scores.length ? Math.min(...scores) : 0;
    const maxScore = scores.length ? Math.max(...scores) : 0;
    const meanScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;

    return (
        <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Particle picks</Typography>
            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
                        <Chip label={`${result.num_particles ?? particles.length} particles`} color="primary" />
                        <Chip label={`${result.num_templates ?? 0} templates`} variant="outlined" />
                        {result.image_binning && <Chip label={`bin ${result.image_binning}`} variant="outlined" />}
                        {result.target_pixel_size && <Chip label={`${result.target_pixel_size.toFixed(2)} Å/px`} variant="outlined" />}
                    </Stack>
                    <Stat label="Min score" value={minScore.toFixed(3)} />
                    <Stat label="Mean score" value={meanScore.toFixed(3)} />
                    <Stat label="Max score" value={maxScore.toFixed(3)} />
                </CardContent>
            </Card>
        </Box>
    );
};

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
    <Stack direction="row" justifyContent="space-between" sx={{ py: 0.5 }}>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
        <Typography variant="body2" fontFamily="monospace">{value}</Typography>
    </Stack>
);
