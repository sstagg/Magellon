import { useState } from 'react';
import { Box, useTheme } from "@mui/material";
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useImageViewerStore } from '../../features/image-viewer/model/imageViewerStore.ts';
import type { StatCardProps } from './model/types.ts';
import { initialStats } from './model/dashboardData.tsx';
import { DRAWER_WIDTH, useDrawerOpen } from './model/useDrawerOpen.ts';
import { ActivityFeedSection } from './ui/ActivityFeedSection.tsx';
import { DashboardHeader } from './ui/DashboardHeader.tsx';
import { ProjectsSection } from './ui/ProjectsSection.tsx';
import { QuickActionsSection } from './ui/QuickActionsSection.tsx';
import { RecentlyViewedPanel } from './ui/RecentlyViewedPanel.tsx';
import { SchedulePanel } from './ui/SchedulePanel.tsx';
import { StatCard } from './ui/StatCard.tsx';
import { SystemStatusPanel } from './ui/SystemStatusPanel.tsx';

// Main Dashboard component
const DashboardView = () => {
    const theme = useTheme();
    const navigate = useNavigate();

    // Track drawer state from localStorage to adjust layout
    const isDrawerOpen = useDrawerOpen();

    // Get current user from the store
    const { currentSession: _currentSession } = useImageViewerStore();

    // State for notifications
    const [notifications, _setNotifications] = useState(3);
    const [lastRefresh, setLastRefresh] = useState('Just now');

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    // State for demo data
    const [stats, _setStats] = useState<StatCardProps[]>(initialStats);

    // Handle refresh
    const handleRefresh = () => {
        setLastRefresh('Just now');
    };

    // Navigate to pages
    const navigateTo = (path: string) => {
        navigate(`/en/panel/${path}`);
    };

    return (
        <Box sx={{
            position: 'fixed',
            top: 64, // Account for header
            left: leftMargin,
            right: 0,
            bottom: 0,
            zIndex: 1050, // Below drawer but above content
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Scrollable Content Container */}
            <Box sx={{
                flex: 1,
                overflow: 'auto',
                p: { xs: 1, sm: 2, md: 3 }
            }}>
                {/* Header with welcome message and actions */}
                <DashboardHeader
                    lastRefresh={lastRefresh}
                    notifications={notifications}
                    onRefresh={handleRefresh}
                    navigateTo={navigateTo}
                />

                {/* Main Dashboard Content */}
                <Grid container spacing={{ xs: 2, md: 3 }}>
                    {/* Stats Section - Top Row */}
                    <Grid size={12}>
                        <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: { xs: 2, md: 4 } }}>
                            {stats.map((stat, index) => (
                                <Grid key={index} size={{ xs: 6, lg: 3 }}>
                                    <StatCard {...stat} />
                                </Grid>
                            ))}
                        </Grid>
                    </Grid>

                    {/* Main Content Area - Middle Section */}
                    <Grid size={{ xs: 12, lg: 8 }}>
                        <QuickActionsSection navigateTo={navigateTo} />
                        <ProjectsSection />
                        <ActivityFeedSection />
                    </Grid>

                    {/* Right Sidebar - Panels */}
                    <Grid size={{ xs: 12, lg: 4 }}>
                        <SchedulePanel />
                        <RecentlyViewedPanel />
                        <SystemStatusPanel />
                    </Grid>
                </Grid>
            </Box>
        </Box>
    );
};

export default DashboardView;
