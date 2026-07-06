import {
    Avatar,
    Box,
    Card,
    CardContent,
    Grid,
    Typography
} from '@mui/material';
import { AdminPanelSettings, Person } from '@mui/icons-material';
import { CheckCircle, XCircle } from 'lucide-react';
import type { UserData } from '../model/types.ts';

interface UserStatsCardsProps {
    users: UserData[];
    totalUsers: number;
}

export default function UserStatsCards({ users, totalUsers }: UserStatsCardsProps) {
    const activeUsers = users.filter(u => u.active);
    const inactiveUsers = users.filter(u => !u.active);
    const failedLoginUsers = users.filter(u => u.access_failed_count && u.access_failed_count > 0);

    const stats = [
        { label: 'Total Users', value: totalUsers, bgcolor: 'primary.main', icon: <Person /> },
        { label: 'Active Users', value: activeUsers.length, bgcolor: 'success.main', icon: <CheckCircle /> },
        { label: 'Inactive Users', value: inactiveUsers.length, bgcolor: 'error.main', icon: <XCircle /> },
        { label: 'Users with Failed Logins', value: failedLoginUsers.length, bgcolor: 'warning.main', icon: <AdminPanelSettings /> }
    ];

    return (
        <Grid container spacing={3} sx={{ mb: 3 }}>
            {stats.map((stat) => (
                <Grid
                    key={stat.label}
                    size={{
                        xs: 12,
                        sm: 6,
                        md: 3
                    }}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Avatar sx={{ bgcolor: stat.bgcolor }}>
                                    {stat.icon}
                                </Avatar>
                                <Box>
                                    <Typography variant="h4">{stat.value}</Typography>
                                    <Typography variant="body2" sx={{
                                        color: "text.secondary"
                                    }}>{stat.label}</Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            ))}
        </Grid>
    );
}
