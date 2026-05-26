import React, { useState } from 'react';
import {
    Box,
    Chip,
    Collapse,
    IconButton,
    LinearProgress,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import { ExpandLess, ExpandMore } from '@mui/icons-material';
import type { DetectionResult } from '../api/PtolemyDetectionService.ts';

interface DetectionInfoPanelProps {
    result: DetectionResult;
}

// Same score ramp as ImageViewer so colors stay in sync.
function scoreToColor(score: number, smin: number, smax: number): string {
    const t = smax === smin ? 1 : Math.max(0, Math.min(1, (score - smin) / (smax - smin)));
    const r = Math.round(255 * (1 - t));
    const g = Math.round(220 * t);
    return `rgb(${r},${g},0)`;
}

export const DetectionInfoPanel: React.FC<DetectionInfoPanelProps> = ({ result }) => {
    const [expanded, setExpanded] = useState(false);

    const { category, detections, grid_angle, grid_pitch } = result;
    const isHole = category === 'HoleDetection';
    const label = isHole ? 'Hole' : 'Square';
    const chipColor = isHole ? '#00e5ff' : '#ffeb3b';

    if (!detections.length) return null;

    const scores = detections.map(d => d.score);
    const smin = Math.min(...scores);
    const smax = Math.max(...scores);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;

    const hasArea = detections.some(d => d.area !== undefined);
    const hasBrightness = detections.some(d => d.brightness != null);

    return (
        <Box
            sx={{
                width: '100%',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                bgcolor: 'background.paper',
                overflow: 'hidden',
            }}
        >
            {/* Header row */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 1.5,
                    py: 0.75,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' },
                }}
                onClick={() => setExpanded(v => !v)}
            >
                <Box
                    sx={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        bgcolor: chipColor,
                        flexShrink: 0,
                    }}
                />
                <Typography variant="caption" sx={{ flex: 1, fontWeight: 600 }}>
                    {label} Detection — {detections.length} found
                </Typography>
                <Chip
                    size="small"
                    label={`avg score ${avgScore.toFixed(2)}`}
                    sx={{ height: 18, fontSize: '0.65rem' }}
                />
                <Tooltip title={expanded ? 'Collapse' : 'Expand table'}>
                    <IconButton size="small" sx={{ p: 0.25 }}>
                        {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Score distribution mini-bar */}
            <Box sx={{ px: 1.5, pb: 0.5 }}>
                <LinearProgress
                    variant="determinate"
                    value={avgScore * 100}
                    sx={{
                        height: 3,
                        borderRadius: 1,
                        bgcolor: 'action.disabledBackground',
                        '& .MuiLinearProgress-bar': {
                            bgcolor: scoreToColor(avgScore, 0, 1),
                        },
                    }}
                />
            </Box>

            {/* Grid stats — angle and pitch */}
            {(grid_angle != null || grid_pitch != null) && (
                <Box sx={{ display: 'flex', gap: 1, px: 1.5, pb: 0.75, flexWrap: 'wrap' }}>
                    {grid_angle != null && (
                        <Chip
                            size="small"
                            label={`angle ${grid_angle.toFixed(1)}°`}
                            sx={{ height: 18, fontSize: '0.65rem', fontFamily: 'monospace' }}
                        />
                    )}
                    {grid_pitch != null && (
                        <Chip
                            size="small"
                            label={`pitch ${Math.round(grid_pitch)} px`}
                            sx={{ height: 18, fontSize: '0.65rem', fontFamily: 'monospace' }}
                        />
                    )}
                </Box>
            )}

            <Collapse in={expanded} unmountOnExit>
                <Box sx={{ overflowX: 'auto', maxHeight: 220, overflowY: 'auto' }}>
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow>
                                <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontWeight: 700 }}>#</TableCell>
                                <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontWeight: 700 }}>Score</TableCell>
                                {hasArea && (
                                    <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontWeight: 700 }}>
                                        Area (px²)
                                    </TableCell>
                                )}
                                {hasBrightness && (
                                    <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontWeight: 700 }}>
                                        Brightness
                                    </TableCell>
                                )}
                                <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontWeight: 700 }}>
                                    Center (col, row)
                                </TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {detections.map((det, i) => {
                                const color = scoreToColor(det.score, smin, smax);
                                return (
                                    <TableRow key={i} hover>
                                        <TableCell sx={{ py: 0.25, px: 1, fontSize: '0.7rem' }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <Box
                                                    sx={{
                                                        width: 8,
                                                        height: 8,
                                                        borderRadius: '50%',
                                                        bgcolor: color,
                                                        flexShrink: 0,
                                                    }}
                                                />
                                                {i + 1}
                                            </Box>
                                        </TableCell>
                                        <TableCell sx={{ py: 0.25, px: 1, fontSize: '0.7rem' }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <LinearProgress
                                                    variant="determinate"
                                                    value={det.score * 100}
                                                    sx={{
                                                        width: 40,
                                                        height: 4,
                                                        borderRadius: 1,
                                                        bgcolor: 'action.disabledBackground',
                                                        '& .MuiLinearProgress-bar': { bgcolor: color },
                                                    }}
                                                />
                                                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                                                    {det.score.toFixed(3)}
                                                </Typography>
                                            </Box>
                                        </TableCell>
                                        {hasArea && (
                                            <TableCell sx={{ py: 0.25, px: 1, fontSize: '0.7rem', fontFamily: 'monospace' }}>
                                                {Math.round(det.area).toLocaleString()}
                                            </TableCell>
                                        )}
                                        {hasBrightness && (
                                            <TableCell sx={{ py: 0.25, px: 1, fontSize: '0.7rem', fontFamily: 'monospace' }}>
                                                {det.brightness != null ? det.brightness.toFixed(1) : '—'}
                                            </TableCell>
                                        )}
                                        <TableCell sx={{ py: 0.25, px: 1, fontSize: '0.7rem', fontFamily: 'monospace' }}>
                                            {det.center[0]}, {det.center[1]}
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </Box>
            </Collapse>
        </Box>
    );
};
