import React from 'react';
import {
    Grid,
    Paper,
    Box,
    Typography,
    Avatar,
    alpha,
    useTheme
} from '@mui/material';
import { GridOn as GridIcon } from '@mui/icons-material';
import {
    Focus,
    Activity,
    ScanLine,
    MapPin,
    TargetIcon
} from 'lucide-react';
import { useMicroscopeStore } from './microscopeStore';

interface QuickActionCardProps {
    title: string;
    icon: React.ReactNode;
    color: string;
    onClick: () => void;
    disabled?: boolean;
}

const QuickActionCard: React.FC<QuickActionCardProps> = ({
                                                             title,
                                                             icon,
                                                             color,
                                                             onClick,
                                                             disabled = false
                                                         }) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.6 : 1,
                borderRadius: 2,
                transition: 'all 0.2s ease',
                '&:hover': disabled ? {} : {
                    transform: 'translateY(-2px)',
                    boxShadow: 2,
                    backgroundColor: alpha(color, 0.05)
                }
            }}
            onClick={disabled ? undefined : onClick}
        >
            <Avatar
                sx={{
                    backgroundColor: alpha(color, 0.1),
                    color: color,
                    width: 32,
                    height: 32
                }}
            >
                {icon}
            </Avatar>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {title}
            </Typography>
        </Paper>
    );
};

export const QuickActions: React.FC = () => {
    const { isConnected } = useMicroscopeStore();

    const quickActions = [
        {
            title: 'Eucentric Height',
            icon: <TargetIcon />,
            color: '#2196f3',
            action: () => console.log('Eucentric height')
        },
        {
            title: 'Auto Focus',
            icon: <Focus size={20} />,
            color: '#4caf50',
            action: () => console.log('Auto focus')
        },
        {
            title: 'Auto Stigmate',
            icon: <ScanLine size={20} />,
            color: '#ff9800',
            action: () => console.log('Auto stigmate')
        },
        {
            title: 'Drift Measure',
            icon: <Activity size={20} />,
            color: '#9c27b0',
            action: () => console.log('Drift measure')
        },
        {
            title: 'Acquire Atlas',
            icon: <GridIcon />,
            color: '#f44336',
            action: () => console.log('Acquire atlas')
        },
        {
            title: 'Reset Stage',
            icon: <MapPin size={20} />,
            color: '#607d8b',
            action: () => console.log('Reset stage')
        }
    ];

    return (
        <Paper elevation={1} sx={{ p: 2, mb: 3, borderRadius: 2 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                Quick Actions
            </Typography>
            <Grid container spacing={1}>
                {quickActions.map((action, index) => (
                    <Grid item xs={6} sm={4} md={2} key={index}>
                        <QuickActionCard
                            title={action.title}
                            icon={action.icon}
                            color={action.color}
                            disabled={!isConnected}
                            onClick={action.action}
                        />
                    </Grid>
                ))}
            </Grid>
        </Paper>
    );
};