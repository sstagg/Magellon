import React from 'react';
import {
    Grid,
    Paper,
    Box,
    Typography,
    Avatar,
    LinearProgress,
    alpha,
    useTheme
} from '@mui/material';
import {
    Science as ScienceIcon,
    ThermostatOutlined as ThermostatIcon,
    Speed as SpeedIcon,
} from '@mui/icons-material';
import {Microscope, Zap} from 'lucide-react';
import { useMicroscopeStore } from './MicroscopeStore';

interface StatusCardProps {
    title: string;
    value: string;
    subtitle: string;
    icon: React.ReactNode;
    color: string;
    progress?: number;
}

const StatusCard: React.FC<StatusCardProps> = ({
                                                   title,
                                                   value,
                                                   subtitle,
                                                   icon,
                                                   color,
                                                   progress
                                               }) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                height: '100%',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3
                }
            }}
        >
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        {title}
                    </Typography>
                    <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
                        {value}
                    </Typography>
                    {subtitle && (
                        <Typography variant="caption" color="text.secondary">
                            {subtitle}
                        </Typography>
                    )}
                </Box>
                <Avatar
                    sx={{
                        backgroundColor: alpha(color, 0.15),
                        color: color,
                        width: 40,
                        height: 40
                    }}
                >
                    {icon}
                </Avatar>
            </Box>
            {progress !== undefined && (
                <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                        mt: 1,
                        backgroundColor: alpha(color, 0.1),
                        '& .MuiLinearProgress-bar': {
                            backgroundColor: color
                        }
                    }}
                />
            )}
        </Paper>
    );
};

export const StatusCards: React.FC = () => {
    const { isConnected, microscopeStatus } = useMicroscopeStore();

    const statusCards = [
        {
            title: 'Microscope',
            value: microscopeStatus?.model || 'Disconnected',
            subtitle: isConnected ? 'Ready' : 'Not Connected',
            icon: <Microscope />,
            color: isConnected ? '#4caf50' : '#f44336'
        },
        {
            title: 'High Tension',
            value: microscopeStatus ? `${microscopeStatus.highTension / 1000} kV` : '--',
            subtitle: 'Stable',
            icon: <Zap size={20} />,
            color: '#ff9800'
        },
        {
            title: 'Temperature',
            value: microscopeStatus ? `${microscopeStatus.temperature.toFixed(1)}°C` : '--',
            subtitle: 'Optimal',
            icon: <ThermostatIcon />,
            color: '#2196f3'
        },
        {
            title: 'Vacuum',
            value: '5.2e-8 Pa',
            subtitle: 'Excellent',
            icon: <SpeedIcon />,
            color: '#4caf50'
        }
    ];

    return (
        <Paper elevation={1} sx={{ p: 2, borderRadius: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                System Status
            </Typography>
            <Grid container spacing={2}>
                {statusCards.map((card, index) => (
                    <Grid item xs={6} xl={3} key={index}>
                        <StatusCard {...card} />
                    </Grid>
                ))}
            </Grid>
        </Paper>
    );
};