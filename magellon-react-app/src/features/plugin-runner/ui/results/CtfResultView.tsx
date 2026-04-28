import React from 'react';
import {
    Box,
    Stack,
    Typography,
    Card,
    CardContent,
} from '@mui/material';

interface CtfResult {
    defocus_u?: number;
    defocus_v?: number;
    astigmatism_angle?: number;
    additional_phase_shift?: number | null;
    cc?: number;
    resolution_limit?: number;
}

interface CtfOutput {
    result?: CtfResult;
    star_path?: string;
    diagnostic_image_path?: string | null;
}

/**
 * CTF result renderer — shows the scalar fit values and a schematic Thon-ring
 * sketch. The SVG is illustrative (ellipse eccentricity = astigmatism), not a
 * pixel-accurate plot; for the real power spectrum, the ``diagnostic_image_path``
 * artifact on disk is still the source of truth.
 */
export const CtfResultView: React.FC<{ result: CtfOutput }> = ({ result }) => {
    const r = result?.result ?? {};
    const defocusU = r.defocus_u ?? 0;
    const defocusV = r.defocus_v ?? 0;
    const astigDeg = r.astigmatism_angle ?? 0;
    const meanDefocus = (defocusU + defocusV) / 2;
    const astigMag = Math.abs(defocusU - defocusV);

    return (
        <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>CTF fit</Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Card variant="outlined" sx={{ flex: 1 }}>
                    <CardContent>
                        <Stat label="Defocus U (Å)" value={defocusU.toFixed(0)} />
                        <Stat label="Defocus V (Å)" value={defocusV.toFixed(0)} />
                        <Stat label="Mean defocus (Å)" value={meanDefocus.toFixed(0)} />
                        <Stat label="Astigmatism (Å)" value={astigMag.toFixed(0)} />
                        <Stat label="Astig. angle (°)" value={astigDeg.toFixed(1)} />
                        {r.additional_phase_shift != null && (
                            <Stat label="Phase shift (rad)" value={r.additional_phase_shift.toFixed(3)} />
                        )}
                        <Stat label="CC" value={(r.cc ?? 0).toFixed(3)} />
                        <Stat label="Fit extent (Å)" value={(r.resolution_limit ?? 0).toFixed(2)} />
                    </CardContent>
                </Card>
                <Card variant="outlined" sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <CardContent>
                        <ThonRingSketch defocusU={defocusU} defocusV={defocusV} angleDeg={astigDeg} />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                display: 'block',
                                mt: 1,
                                textAlign: 'center'
                            }}>
                            Schematic — ellipse eccentricity follows astigmatism
                        </Typography>
                    </CardContent>
                </Card>
            </Stack>
            {result.diagnostic_image_path && (
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        mt: 1,
                        display: 'block'
                    }}>
                    Diagnostic image: {result.diagnostic_image_path}
                </Typography>
            )}
        </Box>
    );
};

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
    <Stack
        direction="row"
        sx={{
            justifyContent: "space-between",
            py: 0.5
        }}>
        <Typography variant="body2" sx={{
            color: "text.secondary"
        }}>{label}</Typography>
        <Typography variant="body2" sx={{
            fontFamily: "monospace"
        }}>{value}</Typography>
    </Stack>
);

// ---------------------------------------------------------------------------

interface ThonRingSketchProps {
    defocusU: number;
    defocusV: number;
    angleDeg: number;
}

const ThonRingSketch: React.FC<ThonRingSketchProps> = ({ defocusU, defocusV, angleDeg }) => {
    const size = 200;
    const cx = size / 2;
    const cy = size / 2;

    // Draw four concentric ellipses at proportional radii. Radii ratio reflects
    // the defocus ratio so a perfect astigmatic sample shows elongated rings.
    const maxDefocus = Math.max(defocusU, defocusV, 1);
    const ratio = defocusV > 0 ? defocusU / defocusV : 1;
    const baseRx = (size / 2) * 0.85;
    const baseRy = baseRx / ratio;

    const rings = [1.0, 0.75, 0.5, 0.28].map((s) => ({ rx: baseRx * s, ry: baseRy * s }));

    return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <rect width={size} height={size} fill="#0b0f19" />
            <g transform={`rotate(${angleDeg} ${cx} ${cy})`} fill="none" strokeLinecap="round">
                {rings.map((r, i) => (
                    <ellipse
                        key={i}
                        cx={cx}
                        cy={cy}
                        rx={r.rx}
                        ry={r.ry}
                        stroke={i === 0 ? '#90caf9' : '#64b5f6'}
                        strokeOpacity={1 - i * 0.2}
                        strokeWidth={1.5}
                    />
                ))}
            </g>
            {/* Center dot */}
            <circle cx={cx} cy={cy} r={2} fill="#ffca28" />
        </svg>
    );
};
