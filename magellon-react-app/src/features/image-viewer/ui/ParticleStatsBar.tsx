import React from 'react';
import {
    Box,
    Typography,
    Divider,
    alpha,
    useTheme,
    Tooltip,
} from '@mui/material';
import {
    AutoFixHigh as AutoFixHighIcon,
    Layers as LayersIcon,
    Assessment as AssessmentIcon,
    TouchApp as TouchAppIcon,
    Close as CloseIcon,
} from '@mui/icons-material';
import { ParticleClass } from '../lib/useParticleOperations.ts';

export interface ParticleStatsBarProps {
    stats: { total: number; manual: number; auto: number; avgConfidence: number; particlesPerClass: Record<string, number> };
    particleClasses: ParticleClass[];
    activeClass: string;
    onActiveClassChange: (classId: string) => void;
    selectedCount: number;
    onDeselectAll: () => void;
}

const StatItem: React.FC<{
    icon: React.ReactNode;
    label: string;
    value: string | number;
    color?: string;
}> = ({ icon, label, value, color }) => {
    const theme = useTheme();
    return (
        <Tooltip title={label} placement="left">
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 0.25,
                py: 0.75,
                px: 0.5,
                borderRadius: 1,
                cursor: 'default',
                '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.08) },
            }}>
                <Box sx={{ color: color || 'text.secondary', display: 'flex' }}>{icon}</Box>
                <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, lineHeight: 1, color: color || 'text.primary' }}>
                    {value}
                </Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary', lineHeight: 1 }}>
                    {label}
                </Typography>
            </Box>
        </Tooltip>
    );
};

export const ParticleStatsBar: React.FC<ParticleStatsBarProps> = ({
    stats,
    particleClasses,
    activeClass,
    onActiveClassChange,
    selectedCount,
    onDeselectAll,
}) => {
    const theme = useTheme();

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 0.5,
            py: 1,
            px: 0.5,
            width: 72,
            flexShrink: 0,
            borderRight: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
            backgroundColor: alpha(theme.palette.background.paper, 0.8),
            overflowY: 'auto',
            overflowX: 'hidden',
        }}>
            {/* Counts */}
            <StatItem icon={<LayersIcon sx={{ fontSize: 16 }} />} label="Total" value={stats.total} />
            <StatItem icon={<TouchAppIcon sx={{ fontSize: 16 }} />} label="Manual" value={stats.manual} color={theme.palette.primary.main} />
            <StatItem icon={<AutoFixHighIcon sx={{ fontSize: 16 }} />} label="Auto" value={stats.auto} color={theme.palette.secondary.main} />
            <StatItem icon={<AssessmentIcon sx={{ fontSize: 16 }} />} label="Conf" value={`${(stats.avgConfidence * 100).toFixed(0)}%`} />

            <Divider flexItem sx={{ my: 0.5 }} />

            {/* Classes */}
            {particleClasses.map(cls => (
                <Tooltip key={cls.id} title={`${cls.name}: ${cls.count}`} placement="left">
                    <Box
                        onClick={() => onActiveClassChange(cls.id)}
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 0.25,
                            py: 0.5,
                            px: 0.5,
                            borderRadius: 1,
                            cursor: 'pointer',
                            backgroundColor: activeClass === cls.id ? alpha(cls.color, 0.2) : 'transparent',
                            border: activeClass === cls.id ? `1.5px solid ${cls.color}` : '1.5px solid transparent',
                            '&:hover': { backgroundColor: alpha(cls.color, 0.15) },
                            transition: 'all 0.15s',
                        }}
                    >
                        <Box sx={{
                            width: 12, height: 12, borderRadius: '50%',
                            backgroundColor: cls.color,
                            border: `1px solid ${alpha(cls.color, 0.8)}`,
                        }} />
                        <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: cls.color, lineHeight: 1 }}>
                            {cls.count}
                        </Typography>
                    </Box>
                </Tooltip>
            ))}

            {/* Selection */}
            {selectedCount > 0 && (
                <>
                    <Divider flexItem sx={{ my: 0.5 }} />
                    <Tooltip title={`${selectedCount} selected — click to deselect`} placement="left">
                        <Box
                            onClick={onDeselectAll}
                            sx={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: 0.25,
                                py: 0.5,
                                cursor: 'pointer',
                                color: theme.palette.info.main,
                                '&:hover': { backgroundColor: alpha(theme.palette.info.main, 0.1) },
                                borderRadius: 1,
                            }}
                        >
                            <CloseIcon sx={{ fontSize: 14 }} />
                            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, lineHeight: 1 }}>
                                {selectedCount}
                            </Typography>
                        </Box>
                    </Tooltip>
                </>
            )}
        </Box>
    );
};
