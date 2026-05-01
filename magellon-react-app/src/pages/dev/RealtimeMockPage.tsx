// Real-time SPA monitoring — mock UI demonstrating the closed-loop
// concept Magellon should reach for parity with cryoSPARC Live + Smart EPU.
//
// Streams synthetic per-micrograph events at a configurable rate. Shows:
//  - Live CTF resolution scatter (one dot per micrograph)
//  - Particle count over time
//  - 2D class averages updating every N micrographs (mock blob images)
//  - Rules panel with one-click filters that visibly drop micrographs
//
// All data is generated client-side. No backend wiring — this is a
// concept demo for design review.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Box,
    Button,
    Chip,
    Container,
    Divider,
    FormControl,
    FormControlLabel,
    Grid,
    InputLabel,
    LinearProgress,
    MenuItem,
    Paper,
    Select,
    Slider,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import { Pause, Play, RotateCcw, Activity, AlertCircle, Square, CheckCircle2 } from 'lucide-react';

// ── Synthetic data ─────────────────────────────────────────────────

interface Micrograph {
    id: number;
    timestamp: number;        // sec since session start
    square_id: string;        // grid square label e.g. "G3-S12"
    ctf_resolution_a: number; // Å, lower = better
    defocus_um: number;
    particle_count: number;
    drift_a: number;          // Å of beam-induced drift
    accepted: boolean;
    drop_reason?: string;
}

interface ClassAverage {
    id: number;
    n_particles: number;
    score: number;            // 0-1 quality score
    iteration: number;
    color_seed: number;       // for the mock blob
}

interface Rule {
    id: string;
    label: string;
    enabled: boolean;
    description: string;
    apply: (m: Micrograph) => string | null; // returns reason or null if accepted
}

// Pseudo-random number sequence so re-renders are stable.
function mulberry32(seed: number): () => number {
    let s = seed >>> 0;
    return () => {
        s = (s + 0x6d2b79f5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function makeMicrograph(id: number, t: number, rng: () => number): Micrograph {
    // Resolution is mostly 3.0–4.5 Å with occasional bad ones at 6–10 Å
    // (drift, ice contamination, off-axis, etc).
    const isBad = rng() < 0.18;
    const ctf = isBad ? 5 + rng() * 5 : 2.8 + rng() * 1.6;
    const drift = isBad ? 5 + rng() * 10 : 1 + rng() * 2;
    // Particle counts loosely correlate with CTF quality.
    const nParticles = isBad
        ? Math.round(rng() * 80)
        : Math.round(150 + rng() * 250);
    const defocus = 0.5 + rng() * 2.5;
    const square = `G${1 + Math.floor(rng() * 6)}-S${1 + Math.floor(rng() * 30)}`;
    return {
        id,
        timestamp: t,
        square_id: square,
        ctf_resolution_a: ctf,
        defocus_um: defocus,
        particle_count: nParticles,
        drift_a: drift,
        accepted: true,
    };
}

// ── Inline mock 2D class average ───────────────────────────────────
// SVG-based blob that looks roughly molecule-shaped. Real Class2D
// averages would be ~80×80 grayscale arrays from RELION; for a mock
// this gives a plausible shape per `seed`.
function MockClassAverage({ score, seed, nParticles }: { score: number; seed: number; nParticles: number }) {
    const rng = mulberry32(seed);
    const blobs = useMemo(() => {
        const lobes: { cx: number; cy: number; rx: number; ry: number; opacity: number }[] = [];
        const nLobes = 3 + Math.floor(rng() * 4);
        for (let i = 0; i < nLobes; i++) {
            lobes.push({
                cx: 30 + rng() * 40,
                cy: 30 + rng() * 40,
                rx: 8 + rng() * 14,
                ry: 8 + rng() * 14,
                opacity: 0.5 + rng() * 0.5,
            });
        }
        return lobes;
    }, [seed]);
    const borderColor = score > 0.75 ? '#4caf50' : score > 0.5 ? '#ff9800' : '#f44336';
    return (
        <Box
            sx={{
                position: 'relative',
                width: '100%',
                aspectRatio: '1',
                border: `2px solid ${borderColor}`,
                borderRadius: 1,
                overflow: 'hidden',
                background: 'radial-gradient(ellipse at center, #444 0%, #1a1a1a 100%)',
            }}
        >
            <svg viewBox="0 0 100 100" width="100%" height="100%">
                {blobs.map((b, i) => (
                    <ellipse
                        key={i}
                        cx={b.cx}
                        cy={b.cy}
                        rx={b.rx}
                        ry={b.ry}
                        fill="#cfe8fc"
                        opacity={b.opacity}
                        style={{ filter: 'blur(2px)' }}
                    />
                ))}
            </svg>
            <Box
                sx={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    px: 0.5,
                    py: 0.25,
                    fontSize: '0.65rem',
                    background: 'rgba(0,0,0,0.55)',
                    color: '#fff',
                    display: 'flex',
                    justifyContent: 'space-between',
                }}
            >
                <span>{nParticles}p</span>
                <span style={{ color: borderColor }}>{(score * 100).toFixed(0)}</span>
            </Box>
        </Box>
    );
}

// ── Charts (inline SVG, no extra deps) ─────────────────────────────

function ScatterChart({
    points,
    width = 600,
    height = 200,
    xLabel,
    yLabel,
    yMin,
    yMax,
    threshold,
}: {
    points: { x: number; y: number; accepted: boolean }[];
    width?: number;
    height?: number;
    xLabel: string;
    yLabel: string;
    yMin: number;
    yMax: number;
    threshold?: number;
}) {
    const xMax = Math.max(60, ...points.map(p => p.x));
    const padL = 40, padB = 24, padT = 8, padR = 8;
    const plotW = width - padL - padR;
    const plotH = height - padB - padT;
    const xScale = (x: number) => padL + (x / xMax) * plotW;
    const yScale = (y: number) => padT + (1 - (y - yMin) / (yMax - yMin)) * plotH;
    return (
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
            <line x1={padL} y1={padT} x2={padL} y2={padT + plotH} stroke="#666" />
            <line x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} stroke="#666" />
            {/* gridlines */}
            {[0.25, 0.5, 0.75].map(f => (
                <line
                    key={f}
                    x1={padL}
                    y1={padT + plotH * f}
                    x2={padL + plotW}
                    y2={padT + plotH * f}
                    stroke="#eee"
                    strokeDasharray="2 4"
                />
            ))}
            {threshold !== undefined && (
                <>
                    <line
                        x1={padL}
                        y1={yScale(threshold)}
                        x2={padL + plotW}
                        y2={yScale(threshold)}
                        stroke="#f44336"
                        strokeDasharray="6 4"
                        strokeWidth={1.5}
                    />
                    <text x={padL + 4} y={yScale(threshold) - 4} fill="#f44336" fontSize="11">
                        threshold {threshold.toFixed(1)}
                    </text>
                </>
            )}
            {points.map((p, i) => (
                <circle
                    key={i}
                    cx={xScale(p.x)}
                    cy={yScale(p.y)}
                    r={3}
                    fill={p.accepted ? '#4caf50' : '#f44336'}
                    opacity={0.75}
                />
            ))}
            {/* axis labels */}
            <text x={padL + plotW / 2} y={height - 4} textAnchor="middle" fontSize="11" fill="#666">
                {xLabel}
            </text>
            <text
                x={-(padT + plotH / 2)}
                y={12}
                textAnchor="middle"
                fontSize="11"
                fill="#666"
                transform={`rotate(-90)`}
            >
                {yLabel}
            </text>
            {/* y-axis ticks */}
            {[yMin, yMin + (yMax - yMin) / 2, yMax].map((v, i) => (
                <text key={i} x={padL - 6} y={yScale(v) + 4} textAnchor="end" fontSize="10" fill="#666">
                    {v.toFixed(1)}
                </text>
            ))}
            {/* x-axis ticks */}
            {[0, xMax / 2, xMax].map((v, i) => (
                <text
                    key={i}
                    x={xScale(v)}
                    y={padT + plotH + 14}
                    textAnchor="middle"
                    fontSize="10"
                    fill="#666"
                >
                    {Math.round(v)}
                </text>
            ))}
        </svg>
    );
}

function CumulativeBar({
    accepted,
    rejected,
}: {
    accepted: number;
    rejected: number;
}) {
    const total = accepted + rejected || 1;
    const acceptedPct = (accepted / total) * 100;
    return (
        <Box sx={{ width: '100%' }}>
            <Box
                sx={{
                    height: 24,
                    width: '100%',
                    borderRadius: 1,
                    overflow: 'hidden',
                    display: 'flex',
                    border: '1px solid rgba(0,0,0,0.1)',
                }}
            >
                <Box sx={{ width: `${acceptedPct}%`, bgcolor: '#4caf50' }} />
                <Box sx={{ width: `${100 - acceptedPct}%`, bgcolor: '#f44336' }} />
            </Box>
            <Stack direction="row" sx={{ mt: 0.5, fontSize: '0.85rem', justifyContent: 'space-between' }}>
                <Box component="span" sx={{ color: '#388e3c' }}>{accepted} accepted</Box>
                <Box component="span" sx={{ color: '#d32f2f' }}>{rejected} rejected ({((rejected / total) * 100).toFixed(0)}%)</Box>
            </Stack>
        </Box>
    );
}

// ── Page ───────────────────────────────────────────────────────────

export const RealtimeMockPage: React.FC = () => {
    const [running, setRunning] = useState(true);
    const [rateMs, setRateMs] = useState(900); // ms between micrographs

    // Rule thresholds.
    const [maxCtfA, setMaxCtfA] = useState(5.0);
    const [minParticles, setMinParticles] = useState(80);
    const [maxDriftA, setMaxDriftA] = useState(8.0);
    const [rule_ctf, setRuleCtf] = useState(true);
    const [rule_particles, setRuleParticles] = useState(true);
    const [rule_drift, setRuleDrift] = useState(false);

    // Data buffers.
    const [micrographs, setMicrographs] = useState<Micrograph[]>([]);
    const [classes, setClasses] = useState<ClassAverage[]>(() => {
        const arr: ClassAverage[] = [];
        for (let i = 0; i < 12; i++) {
            arr.push({ id: i, n_particles: 0, score: 0, iteration: 0, color_seed: 1 + i * 11 });
        }
        return arr;
    });
    const tStart = useRef<number>(Date.now());
    const idCounter = useRef<number>(0);
    const rng = useRef(mulberry32(42));

    // Streaming loop.
    useEffect(() => {
        if (!running) return;
        const handle = window.setInterval(() => {
            const t = (Date.now() - tStart.current) / 1000;
            const m = makeMicrograph(idCounter.current++, t, rng.current);
            // Apply rules.
            const reasons: string[] = [];
            if (rule_ctf && m.ctf_resolution_a > maxCtfA) reasons.push(`CTF ${m.ctf_resolution_a.toFixed(1)}>${maxCtfA}`);
            if (rule_particles && m.particle_count < minParticles)
                reasons.push(`particles ${m.particle_count}<${minParticles}`);
            if (rule_drift && m.drift_a > maxDriftA) reasons.push(`drift ${m.drift_a.toFixed(1)}>${maxDriftA}`);
            if (reasons.length > 0) {
                m.accepted = false;
                m.drop_reason = reasons.join('; ');
            }
            setMicrographs(prev => [...prev.slice(-499), m]);
            // Every 5 micrographs, "advance" the 2D classification: bump
            // n_particles + score for some classes.
            if (m.accepted && idCounter.current % 5 === 0) {
                setClasses(prev =>
                    prev.map(c => {
                        const r = rng.current();
                        if (r < 0.6) {
                            return {
                                ...c,
                                n_particles: c.n_particles + Math.round(rng.current() * 40),
                                score: Math.min(1, c.score + 0.02 + rng.current() * 0.04),
                                iteration: c.iteration + 1,
                            };
                        }
                        return c;
                    })
                );
            }
        }, rateMs);
        return () => window.clearInterval(handle);
    }, [running, rateMs, rule_ctf, rule_particles, rule_drift, maxCtfA, minParticles, maxDriftA]);

    const accepted = micrographs.filter(m => m.accepted).length;
    const rejected = micrographs.length - accepted;
    const acceptedParticles = micrographs.filter(m => m.accepted).reduce((s, m) => s + m.particle_count, 0);
    const sortedClasses = [...classes].sort((a, b) => b.n_particles - a.n_particles);

    const ctfPoints = micrographs.map(m => ({ x: m.id, y: m.ctf_resolution_a, accepted: m.accepted }));
    const partPoints = micrographs.map(m => ({ x: m.id, y: m.particle_count, accepted: m.accepted }));

    const reset = () => {
        setMicrographs([]);
        idCounter.current = 0;
        tStart.current = Date.now();
        rng.current = mulberry32(42);
        setClasses(prev => prev.map(c => ({ ...c, n_particles: 0, score: 0, iteration: 0 })));
    };

    return (
        <Container maxWidth="xl" sx={{ py: 3 }}>
            <Stack direction="row" spacing={2} sx={{ mb: 2, alignItems: 'center' }}>
                <Activity size={28} />
                <Typography variant="h4" component="h1" sx={{ flex: 1 }}>
                    Realtime SPA — concept mock
                </Typography>
                <Chip
                    icon={running ? <Activity size={14} /> : <Pause size={14} />}
                    label={running ? 'streaming' : 'paused'}
                    color={running ? 'success' : 'default'}
                    size="small"
                />
                <Tooltip title={running ? 'pause stream' : 'resume stream'}>
                    <Button
                        variant="contained"
                        size="small"
                        onClick={() => setRunning(r => !r)}
                        startIcon={running ? <Pause size={14} /> : <Play size={14} />}
                    >
                        {running ? 'Pause' : 'Resume'}
                    </Button>
                </Tooltip>
                <Tooltip title="reset stream + classes">
                    <Button variant="outlined" size="small" onClick={reset} startIcon={<RotateCcw size={14} />}>
                        Reset
                    </Button>
                </Tooltip>
            </Stack>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Mock data, no backend. Demonstrates the cryoSPARC-Live-style closed-loop UX
                Magellon should target: incoming micrographs scored in real time, rules drop
                bad targets visibly, 2D classes update as particles accumulate.
            </Typography>

            <Grid container spacing={2}>
                {/* Top — CTF stream + particles */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper sx={{ p: 2 }}>
                        <Stack direction="row" sx={{ mb: 1, justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="subtitle1">CTF resolution stream</Typography>
                            <Chip label={`${micrographs.length} micrographs`} size="small" />
                        </Stack>
                        <ScatterChart
                            points={ctfPoints}
                            xLabel="micrograph #"
                            yLabel="CTF Å (lower better)"
                            yMin={2}
                            yMax={12}
                            threshold={rule_ctf ? maxCtfA : undefined}
                        />
                    </Paper>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper sx={{ p: 2 }}>
                        <Stack direction="row" sx={{ mb: 1, justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="subtitle1">Particles per micrograph</Typography>
                            <Chip label={`${acceptedParticles.toLocaleString()} kept`} size="small" color="success" />
                        </Stack>
                        <ScatterChart
                            points={partPoints}
                            xLabel="micrograph #"
                            yLabel="particles"
                            yMin={0}
                            yMax={500}
                            threshold={rule_particles ? minParticles : undefined}
                        />
                    </Paper>
                </Grid>

                {/* Acceptance bar */}
                <Grid size={12}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                            Session-level acceptance
                        </Typography>
                        <CumulativeBar accepted={accepted} rejected={rejected} />
                    </Paper>
                </Grid>

                {/* Rules */}
                <Grid size={{ xs: 12, md: 4 }}>
                    <Paper sx={{ p: 2, height: '100%' }}>
                        <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center' }}>
                            <AlertCircle size={18} />
                            <Typography variant="subtitle1">Rules</Typography>
                        </Stack>
                        <Stack spacing={2}>
                            <Box>
                                <FormControlLabel
                                    control={<Switch checked={rule_ctf} onChange={(_, v) => setRuleCtf(v)} />}
                                    label={`Drop CTF > ${maxCtfA.toFixed(1)} Å`}
                                />
                                <Slider
                                    value={maxCtfA}
                                    min={3}
                                    max={10}
                                    step={0.1}
                                    disabled={!rule_ctf}
                                    onChange={(_, v) => setMaxCtfA(v as number)}
                                />
                            </Box>
                            <Box>
                                <FormControlLabel
                                    control={
                                        <Switch checked={rule_particles} onChange={(_, v) => setRuleParticles(v)} />
                                    }
                                    label={`Skip if < ${minParticles} particles`}
                                />
                                <Slider
                                    value={minParticles}
                                    min={0}
                                    max={300}
                                    step={5}
                                    disabled={!rule_particles}
                                    onChange={(_, v) => setMinParticles(v as number)}
                                />
                            </Box>
                            <Box>
                                <FormControlLabel
                                    control={<Switch checked={rule_drift} onChange={(_, v) => setRuleDrift(v)} />}
                                    label={`Drop drift > ${maxDriftA.toFixed(1)} Å`}
                                />
                                <Slider
                                    value={maxDriftA}
                                    min={1}
                                    max={20}
                                    step={0.5}
                                    disabled={!rule_drift}
                                    onChange={(_, v) => setMaxDriftA(v as number)}
                                />
                            </Box>
                        </Stack>
                        <Divider sx={{ my: 2 }} />
                        <FormControl fullWidth size="small">
                            <InputLabel>Stream rate</InputLabel>
                            <Select
                                value={rateMs}
                                label="Stream rate"
                                onChange={e => setRateMs(Number(e.target.value))}
                            >
                                <MenuItem value={300}>3 / sec (fast)</MenuItem>
                                <MenuItem value={900}>~1 / sec (typical)</MenuItem>
                                <MenuItem value={3000}>1 / 3 sec (calm)</MenuItem>
                            </Select>
                        </FormControl>
                    </Paper>
                </Grid>

                {/* 2D class averages */}
                <Grid size={{ xs: 12, md: 8 }}>
                    <Paper sx={{ p: 2, height: '100%' }}>
                        <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center' }}>
                            <Square size={18} />
                            <Typography variant="subtitle1">2D class averages</Typography>
                            <Chip
                                label={`iter ${Math.max(...classes.map(c => c.iteration), 0)}`}
                                size="small"
                            />
                        </Stack>
                        <Grid container spacing={1.5}>
                            {sortedClasses.map(c => (
                                <Grid key={c.id} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
                                    <MockClassAverage
                                        score={c.score}
                                        seed={c.color_seed}
                                        nParticles={c.n_particles}
                                    />
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </Grid>

                {/* Recent micrographs table */}
                <Grid size={12}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="subtitle1" sx={{ mb: 1 }}>
                            Recent micrographs (last 10)
                        </Typography>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>#</TableCell>
                                        <TableCell>Square</TableCell>
                                        <TableCell align="right">Time (s)</TableCell>
                                        <TableCell align="right">CTF (Å)</TableCell>
                                        <TableCell align="right">Defocus (µm)</TableCell>
                                        <TableCell align="right">Particles</TableCell>
                                        <TableCell align="right">Drift (Å)</TableCell>
                                        <TableCell>Status</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {[...micrographs].slice(-10).reverse().map(m => (
                                        <TableRow key={m.id} hover>
                                            <TableCell>{m.id}</TableCell>
                                            <TableCell>{m.square_id}</TableCell>
                                            <TableCell align="right">{m.timestamp.toFixed(1)}</TableCell>
                                            <TableCell align="right" sx={{
                                                color: m.ctf_resolution_a > 5 ? '#d32f2f' : 'inherit',
                                                fontWeight: m.ctf_resolution_a > 5 ? 600 : 400,
                                            }}>
                                                {m.ctf_resolution_a.toFixed(2)}
                                            </TableCell>
                                            <TableCell align="right">{m.defocus_um.toFixed(2)}</TableCell>
                                            <TableCell align="right">{m.particle_count}</TableCell>
                                            <TableCell align="right">{m.drift_a.toFixed(1)}</TableCell>
                                            <TableCell>
                                                {m.accepted ? (
                                                    <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                                        <CheckCircle2 size={14} color="#4caf50" />
                                                        <Box component="span" sx={{ color: '#388e3c' }}>kept</Box>
                                                    </Stack>
                                                ) : (
                                                    <Tooltip title={m.drop_reason || ''}>
                                                        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                                            <AlertCircle size={14} color="#f44336" />
                                                            <Box component="span" sx={{ color: '#d32f2f' }}>{m.drop_reason}</Box>
                                                        </Stack>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {micrographs.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={8}>
                                                <Box sx={{ p: 2, textAlign: 'center' }}>
                                                    <LinearProgress sx={{ mb: 1 }} />
                                                    <Typography variant="body2" color="text.secondary">
                                                        Waiting for first micrograph…
                                                    </Typography>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </Grid>
            </Grid>
        </Container>
    );
};
