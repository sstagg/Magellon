/**
 * Live host stats cards for the plugins dashboard.
 *
 * Four cards: CPU / RAM / GPU / Network. Polls /system/stats every
 * 2 seconds via useSystemStats. Animates between samples by reusing
 * react-query's keepPreviousData so the bars don't flash.
 *
 * Errors: a single subtle warning banner above the cards. We don't
 * tear down the previous reading on error — same data shown stale
 * is more useful than nothing.
 */
import React from 'react';
import {
    Alert,
    Box,
    Card,
    CardContent,
    LinearProgress,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import { Activity, Cpu, HardDrive, MemoryStick, Server } from 'lucide-react';

import { useSystemStats, type GpuStats } from '../api/systemStatsApi.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number, decimals: number = 1): string {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const k = 1024;
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1);
    return `${(bytes / Math.pow(k, i)).toFixed(decimals)} ${units[i]}`;
}

function formatRate(bytesPerSec: number): string {
    return `${formatBytes(bytesPerSec, 1)}/s`;
}

// ---------------------------------------------------------------------------
// Generic card shell so the four metrics have a consistent layout.
// ---------------------------------------------------------------------------

interface StatCardProps {
    icon: React.ReactNode;
    title: string;
    primary: React.ReactNode;
    secondary?: React.ReactNode;
    /** 0-100 progress bar shown beneath the secondary line. */
    progress?: number;
    /** Color for the progress bar based on threshold (green/yellow/red). */
    progressTone?: 'success' | 'warning' | 'error' | 'primary';
}

const toneForPercent = (p: number): StatCardProps['progressTone'] => {
    if (p >= 90) return 'error';
    if (p >= 75) return 'warning';
    return 'success';
};

const StatCard: React.FC<StatCardProps> = ({
    icon,
    title,
    primary,
    secondary,
    progress,
    progressTone = 'primary',
}) => (
    <Card variant="outlined" sx={{ height: '100%' }}>
        <CardContent>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
                <Box sx={{ color: 'text.secondary', display: 'flex' }}>{icon}</Box>
                <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5 }}>
                    {title}
                </Typography>
            </Stack>
            <Typography variant="h5" sx={{ mb: 0.5 }}>{primary}</Typography>
            {secondary && (
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: progress !== undefined ? 1 : 0 }}>
                    {secondary}
                </Typography>
            )}
            {progress !== undefined && (
                <LinearProgress
                    variant="determinate"
                    value={Math.max(0, Math.min(100, progress))}
                    color={progressTone}
                    sx={{ height: 6, borderRadius: 3 }}
                />
            )}
        </CardContent>
    </Card>
);

// ---------------------------------------------------------------------------
// GPU summary — one card whether you have 0 / 1 / many devices.
// ---------------------------------------------------------------------------

const GpuCard: React.FC<{ gpu: GpuStats | undefined }> = ({ gpu }) => {
    if (!gpu || !gpu.available || gpu.devices.length === 0) {
        return (
            <StatCard
                icon={<HardDrive size={18} />}
                title="GPU"
                primary="—"
                secondary={gpu?.error ?? 'No GPU detected'}
            />
        );
    }
    // First device drives the headline number; we mention how many more there are.
    const first = gpu.devices[0];
    const memUsed = first.memory_used_bytes ?? 0;
    const memTotal = first.memory_total_bytes ?? 0;
    const memPercent = memTotal > 0 ? (memUsed / memTotal) * 100 : 0;
    const utilPercent = first.util_percent ?? 0;
    const others = gpu.devices.length - 1;

    return (
        <Tooltip
            placement="top"
            title={
                <Box>
                    {gpu.devices.map((d) => (
                        <div key={d.index}>
                            #{d.index} {d.name} — util {(d.util_percent ?? 0).toFixed(0)}%, mem{' '}
                            {formatBytes(d.memory_used_bytes ?? 0)} / {formatBytes(d.memory_total_bytes ?? 0)}
                            {d.temperature_c != null ? `, ${d.temperature_c.toFixed(0)}°C` : ''}
                        </div>
                    ))}
                </Box>
            }
        >
            <Box sx={{ height: '100%' }}>
                <StatCard
                    icon={<HardDrive size={18} />}
                    title="GPU"
                    primary={`${utilPercent.toFixed(0)}%`}
                    secondary={
                        <>
                            {first.name}
                            {others > 0 && ` (+${others} more)`} ·{' '}
                            {formatBytes(memUsed)} / {formatBytes(memTotal)}
                        </>
                    }
                    progress={utilPercent}
                    progressTone={toneForPercent(utilPercent)}
                />
            </Box>
        </Tooltip>
    );
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export const SystemStatsCards: React.FC = () => {
    const { data, error, isLoading } = useSystemStats();

    if (isLoading && !data) {
        return (
            <Box
                sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
                    gap: 2,
                    mb: 3,
                }}
            >
                {[0, 1, 2, 3].map((i) => (
                    <Card key={i} variant="outlined" sx={{ minHeight: 110 }}>
                        <CardContent>
                            <Typography variant="overline" sx={{ color: 'text.secondary' }}>
                                Loading…
                            </Typography>
                            <LinearProgress sx={{ mt: 2 }} />
                        </CardContent>
                    </Card>
                ))}
            </Box>
        );
    }

    return (
        <Box sx={{ mb: 3 }}>
            {error && !data && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    Could not read system stats. Check that you're signed in
                    as Administrator.
                </Alert>
            )}
            <Box
                sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
                    gap: 2,
                }}
            >
                <StatCard
                    icon={<Cpu size={18} />}
                    title="CPU"
                    primary={`${data?.cpu.percent.toFixed(0) ?? 0}%`}
                    secondary={
                        <>
                            {data?.cpu.cores ?? 0} cores
                            {data?.cpu.load_avg && data.cpu.load_avg.length > 0 && (
                                <> · load {data.cpu.load_avg.map((v) => v.toFixed(2)).join(' / ')}</>
                            )}
                        </>
                    }
                    progress={data?.cpu.percent ?? 0}
                    progressTone={toneForPercent(data?.cpu.percent ?? 0)}
                />
                <StatCard
                    icon={<MemoryStick size={18} />}
                    title="RAM"
                    primary={`${data?.ram.percent.toFixed(0) ?? 0}%`}
                    secondary={
                        <>
                            {formatBytes(data?.ram.used_bytes ?? 0)} of{' '}
                            {formatBytes(data?.ram.total_bytes ?? 0)}
                        </>
                    }
                    progress={data?.ram.percent ?? 0}
                    progressTone={toneForPercent(data?.ram.percent ?? 0)}
                />
                <GpuCard gpu={data?.gpu} />
                <StatCard
                    icon={<Activity size={18} />}
                    title="Network"
                    primary={<>↓ {formatRate(data?.network.rx_bytes_per_sec ?? 0)}</>}
                    secondary={
                        <>
                            ↑ {formatRate(data?.network.tx_bytes_per_sec ?? 0)}
                            {' · '}
                            total {formatBytes(data?.network.rx_total_bytes ?? 0)} in /{' '}
                            {formatBytes(data?.network.tx_total_bytes ?? 0)} out
                        </>
                    }
                />
            </Box>
        </Box>
    );
};

export default SystemStatsCards;
