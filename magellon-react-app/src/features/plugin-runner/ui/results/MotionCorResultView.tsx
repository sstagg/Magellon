import React, { useMemo } from 'react';
import {
    Box,
    Card,
    CardContent,
    Stack,
    Typography,
} from '@mui/material';

interface DriftSample { frame: number; dx: number; dy: number; }
interface MotionCorSummary {
    total_drift_pixels: number;
    max_frame_drift_pixels: number;
    num_frames: number;
}
interface MotionCorOutput {
    aligned_mrc_path?: string;
    log_path?: string | null;
    drift?: DriftSample[];
    summary?: MotionCorSummary;
}

/**
 * Drift overlay — plots the MotionCor shift trajectory as an SVG polyline.
 * Each vertex is a frame; the colour gradient tracks time so you can see the
 * drift direction at a glance.
 */
export const MotionCorResultView: React.FC<{ result: MotionCorOutput }> = ({ result }) => {
    const drift = result?.drift ?? [];
    const summary = result?.summary;

    const { width, height, points, bounds } = useMemo(
        () => layoutDrift(drift, 360, 240),
        [drift],
    );

    return (
        <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Drift trajectory</Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Card variant="outlined" sx={{ flex: 1 }}>
                    <CardContent>
                        <Stat label="Frames" value={`${summary?.num_frames ?? drift.length}`} />
                        <Stat label="Total drift (px)" value={(summary?.total_drift_pixels ?? 0).toFixed(2)} />
                        <Stat label="Peak frame drift (px)" value={(summary?.max_frame_drift_pixels ?? 0).toFixed(2)} />
                        {result.aligned_mrc_path && (
                            <Typography
                                variant="caption"
                                sx={{
                                    color: "text.secondary",
                                    display: 'block',
                                    mt: 1
                                }}>
                                Output: {result.aligned_mrc_path}
                            </Typography>
                        )}
                        {result.log_path && (
                            <Typography
                                variant="caption"
                                sx={{
                                    color: "text.secondary",
                                    display: 'block'
                                }}>
                                Log: {result.log_path}
                            </Typography>
                        )}
                    </CardContent>
                </Card>
                <Card variant="outlined" sx={{ flex: 1 }}>
                    <CardContent>
                        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
                            <rect x={0} y={0} width={width} height={height} fill="#0b0f19" />
                            {/* Axes cross at bounds midpoint */}
                            <line x1={0} x2={width} y1={bounds.midY} y2={bounds.midY} stroke="#263238" strokeWidth={1} />
                            <line y1={0} y2={height} x1={bounds.midX} x2={bounds.midX} stroke="#263238" strokeWidth={1} />

                            {points.length > 1 && (
                                <polyline
                                    points={points.map((p) => `${p.x},${p.y}`).join(' ')}
                                    fill="none"
                                    stroke="#64b5f6"
                                    strokeWidth={1.5}
                                />
                            )}
                            {points.map((p, i) => (
                                <circle
                                    key={i}
                                    cx={p.x}
                                    cy={p.y}
                                    r={2.5}
                                    fill={colourForFrame(i, points.length)}
                                />
                            ))}
                            {points.length > 0 && (
                                <>
                                    <text x={points[0].x + 6} y={points[0].y - 4} fill="#90caf9" fontSize={10} fontFamily="monospace">
                                        f{drift[0]?.frame ?? 1}
                                    </text>
                                    <text x={points[points.length - 1].x + 6} y={points[points.length - 1].y - 4} fill="#ffca28" fontSize={10} fontFamily="monospace">
                                        f{drift[drift.length - 1]?.frame ?? drift.length}
                                    </text>
                                </>
                            )}
                        </svg>
                        {drift.length === 0 && (
                            <Typography variant="caption" sx={{
                                color: "text.secondary"
                            }}>
                                No drift samples parsed from the log.
                            </Typography>
                        )}
                    </CardContent>
                </Card>
            </Stack>
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
// Layout helpers
// ---------------------------------------------------------------------------

function layoutDrift(samples: DriftSample[], width: number, height: number) {
    if (samples.length === 0) {
        return { width, height, points: [] as { x: number; y: number }[], bounds: { midX: width / 2, midY: height / 2 } };
    }
    const xs = samples.map((s) => s.dx);
    const ys = samples.map((s) => s.dy);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    // Add padding and keep aspect fixed.
    const padding = 12;
    const drawW = width - padding * 2;
    const drawH = height - padding * 2;
    const spanX = Math.max(maxX - minX, 0.01);
    const spanY = Math.max(maxY - minY, 0.01);

    const points = samples.map((s) => ({
        x: padding + ((s.dx - minX) / spanX) * drawW,
        y: padding + ((s.dy - minY) / spanY) * drawH,
    }));

    // Origin projected onto axis lines
    const midX = padding + ((0 - minX) / spanX) * drawW;
    const midY = padding + ((0 - minY) / spanY) * drawH;

    return {
        width,
        height,
        points,
        bounds: {
            midX: Math.min(Math.max(midX, 0), width),
            midY: Math.min(Math.max(midY, 0), height),
        },
    };
}

function colourForFrame(idx: number, total: number): string {
    // Blue (early) → yellow (late)
    const t = total <= 1 ? 0 : idx / (total - 1);
    const r = Math.round(80 + t * 175);
    const g = Math.round(180 + t * 40);
    const b = Math.round(240 - t * 200);
    return `rgb(${r},${g},${b})`;
}
