import { Badge, Box, Button, IconButton, Tooltip, Typography, useMediaQuery, useTheme } from "@mui/material";
import { Bell, FilePlus, RefreshCw } from 'lucide-react';

interface DashboardHeaderProps {
    lastRefresh: string;
    notifications: number;
    onRefresh: () => void;
    navigateTo: (path: string) => void;
}

// Calculate greeting based on time of day
const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
};

// Header with welcome message and actions
export const DashboardHeader = ({ lastRefresh, notifications, onRefresh, navigateTo }: DashboardHeaderProps) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    return (
        <Box sx={{
            mb: { xs: 2, sm: 3, md: 4 },
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            justifyContent: 'space-between',
            alignItems: { xs: 'flex-start', md: 'center' },
            gap: 2
        }}>
            <Box>
                <Typography
                    variant={isMobile ? "h5" : "h4"}
                    component="h1"
                    sx={{
                        fontSize: { xs: '1.5rem', sm: '1.8rem', md: '2.125rem' },
                        fontWeight: 700
                    }}
                >
                    {getGreeting()}, User
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                    <Typography
                        variant="body1"
                        sx={{
                            color: 'text.secondary',
                            fontSize: { xs: '0.875rem', sm: '1rem' }
                        }}
                    >
                        Here's what's happening with your projects today
                    </Typography>

                    <Box sx={{ display: 'flex', alignItems: 'center', ml: 2 }}>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            Last updated: {lastRefresh}
                        </Typography>
                        <IconButton size="small" onClick={onRefresh} sx={{ ml: 0.5 }}>
                            <RefreshCw size={14} />
                        </IconButton>
                    </Box>
                </Box>
            </Box>

            <Box sx={{
                display: 'flex',
                gap: 1,
                mt: { xs: 1, md: 0 },
                width: { xs: '100%', md: 'auto' }
            }}>
                <Button
                    variant="contained"
                    startIcon={<FilePlus size={18} />}
                    size={isMobile ? "small" : "medium"}
                    onClick={() => navigateTo('import-job')}
                    fullWidth={isMobile}
                >
                    New Import
                </Button>

                <Tooltip title="Notifications">
                    <IconButton color="primary" sx={{ ml: 1 }}>
                        <Badge badgeContent={notifications} color="error">
                            <Bell size={20} />
                        </Badge>
                    </IconButton>
                </Tooltip>
            </Box>
        </Box>
    );
};
