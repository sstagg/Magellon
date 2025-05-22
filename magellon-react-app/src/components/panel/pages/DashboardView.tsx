import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Paper,
    Button,
    Stack,
    useMediaQuery,
    useTheme,
    Divider,
    alpha,
    Card,
    CardContent,
    Avatar,
    LinearProgress,
    IconButton,
    Tooltip,
    Badge,
    Chip
} from "@mui/material";


import Grid from '@mui/material/Grid';


import {
    BarChart2,
    Brain,
    Cpu,
    Database,
    FileText,
    Image as ImageIcon,
    Layers,
    Settings,
    Upload,
    ChevronRight,
    Bell,
    Calendar,
    CheckCircle,
    Clock,
    AlertCircle,
    Info,
    Server,
    Microscope,
    FilePlus,
    BarChart,
    RefreshCw,
    FolderPlus
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useImageViewerStore } from '../../features/session_viewer/store/imageViewerStore';

const DRAWER_WIDTH = 240;

// Custom chart component for the metrics card
const MetricChart = ({ data, color, height = 40 }) => {
    const theme = useTheme();
    const maxValue = Math.max(...data);

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'flex-end',
            height,
            gap: 0.5,
            mt: 1
        }}>
            {data.map((value, index) => (
                <Box
                    key={index}
                    sx={{
                        height: `${(value / maxValue) * 100}%`,
                        width: '4px',
                        backgroundColor: alpha(color, 0.7),
                        borderRadius: '2px',
                        transition: 'height 0.3s ease',
                        '&:hover': {
                            backgroundColor: color,
                            transform: 'scaleY(1.1)',
                        }
                    }}
                />
            ))}
        </Box>
    );
};

// Dashboard stat card component with sparkline chart
const StatCard = ({ title, value, subtitle, icon, color, chartData = [] }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    return (
        <Paper
            elevation={1}
            sx={{
                p: { xs: 1.5, sm: 2, md: 2.5 },
                height: '100%',
                width: '100%',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3,
                }
            }}
        >
            <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                    <Typography
                        variant="body2"
                        component="div"
                        gutterBottom
                        sx={{
                            fontWeight: 500,
                            color: 'text.secondary',
                            fontSize: { xs: '0.75rem', sm: '0.875rem' },
                            mb: 0.5
                        }}
                    >
                        {title}
                    </Typography>
                    <Typography
                        variant={isMobile ? "h6" : "h5"}
                        component="div"
                        sx={{
                            fontWeight: 'bold',
                            color: theme.palette.text.primary,
                            lineHeight: 1.2,
                            fontSize: { xs: '1.25rem', sm: '1.5rem', md: '1.75rem' }
                        }}
                    >
                        {value}
                    </Typography>
                    {subtitle && (
                        <Typography
                            variant="caption"
                            sx={{
                                color: 'text.secondary',
                                display: 'block',
                                mt: 0.5,
                                fontSize: { xs: '0.7rem', sm: '0.75rem' }
                            }}
                        >
                            {subtitle}
                        </Typography>
                    )}
                </Box>
                <Box sx={{
                    backgroundColor: alpha(color, 0.15),
                    p: { xs: 0.75, sm: 1 },
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                }}>
                    {React.cloneElement(icon, {
                        size: isMobile ? 16 : isTablet ? 18 : 20,
                        color: color
                    })}
                </Box>
            </Box>

            {chartData.length > 0 && (
                <Box sx={{ mt: 'auto', pt: 1 }}>
                    <MetricChart data={chartData} color={color} />
                </Box>
            )}
        </Paper>
    );
};

// Quick action card component
const QuickActionCard = ({ title, icon, color, onClick, featured = false }) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={featured ? 2 : 1}
            sx={{
                p: { xs: 1, sm: 1.5 },
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                borderRadius: 2,
                cursor: 'pointer',
                height: '100%',
                background: featured
                    ? `linear-gradient(135deg, ${alpha(color, 0.2)}, ${alpha(color, 0.1)})`
                    : alpha(theme.palette.background.paper, 0.7),
                border: `1px solid ${featured ? alpha(color, 0.3) : alpha(theme.palette.divider, 0.8)}`,
                transition: 'all 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 2,
                    background: featured
                        ? `linear-gradient(135deg, ${alpha(color, 0.25)}, ${alpha(color, 0.15)})`
                        : alpha(theme.palette.background.paper, 0.9),
                }
            }}
            onClick={onClick}
        >
            <Box sx={{
                backgroundColor: alpha(color, featured ? 0.2 : 0.1),
                p: 0.7,
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                {React.cloneElement(icon, {
                    size: 18,
                    color: color
                })}
            </Box>
            <Typography
                variant="body2"
                sx={{
                    fontWeight: featured ? 600 : 500,
                    color: featured ? color : 'text.primary',
                }}
            >
                {title}
            </Typography>
        </Paper>
    );
};

// Activity item component
const ActivityItem = ({ icon, text, time, status = "default" }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const getStatusColor = () => {
        switch (status) {
            case "success": return theme.palette.success.main;
            case "warning": return theme.palette.warning.main;
            case "error": return theme.palette.error.main;
            case "info": return theme.palette.info.main;
            default: return theme.palette.primary.main;
        }
    };

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            py: 1.5,
            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`
        }}>
            <Avatar
                sx={{
                    width: 32,
                    height: 32,
                    backgroundColor: alpha(getStatusColor(), 0.1),
                }}
            >
                {React.cloneElement(icon, {
                    size: 16,
                    color: getStatusColor()
                })}
            </Avatar>

            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 500,
                        color: 'text.primary',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                    }}
                >
                    {text}
                </Typography>
                <Typography
                    variant="caption"
                    sx={{
                        color: 'text.secondary',
                        display: 'block'
                    }}
                >
                    {time}
                </Typography>
            </Box>

            {!isMobile && (
                <Tooltip title="View details">
                    <IconButton size="small">
                        <ChevronRight size={16} />
                    </IconButton>
                </Tooltip>
            )}
        </Box>
    );
};

// Recently viewed item component
const RecentlyViewedItem = ({ name, type, time, onClick }) => {
    const theme = useTheme();

    const getIcon = () => {
        switch (type) {
            case "image": return <ImageIcon size={16} />;
            case "session": return <Database size={16} />;
            case "project": return <FileText size={16} />;
            default: return <FileText size={16} />;
        }
    };

    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                p: 1,
                borderRadius: 1,
                cursor: 'pointer',
                '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.05)
                }
            }}
            onClick={onClick}
        >
            <Box
                sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1,
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    color: theme.palette.primary.main
                }}
            >
                {getIcon()}
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 500,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                    }}
                >
                    {name}
                </Typography>
                <Typography
                    variant="caption"
                    sx={{ color: 'text.secondary', display: 'block' }}
                >
                    {time}
                </Typography>
            </Box>
        </Box>
    );
};

// Project card component
const ProjectCard = ({ name, progress, status, lastUpdated, onClick }) => {
    const theme = useTheme();

    const getStatusColor = () => {
        switch (status) {
            case "completed": return theme.palette.success.main;
            case "in-progress": return theme.palette.info.main;
            case "paused": return theme.palette.warning.main;
            default: return theme.palette.grey[500];
        }
    };

    const getStatusLabel = () => {
        switch (status) {
            case "completed": return "Completed";
            case "in-progress": return "In Progress";
            case "paused": return "Paused";
            default: return "Unknown";
        }
    };

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                borderRadius: 2,
                cursor: 'pointer',
                height: '100%',
                transition: 'all 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 2
                }
            }}
            onClick={onClick}
        >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{name}</Typography>
                <Chip
                    label={getStatusLabel()}
                    size="small"
                    sx={{
                        backgroundColor: alpha(getStatusColor(), 0.1),
                        color: getStatusColor(),
                        fontWeight: 500,
                        borderRadius: '4px'
                    }}
                />
            </Box>

            <Box sx={{ mt: 2, mb: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">Progress</Typography>
                    <Typography variant="caption" fontWeight={500}>{progress}%</Typography>
                </Box>
                <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: alpha(getStatusColor(), 0.1),
                        '& .MuiLinearProgress-bar': {
                            backgroundColor: getStatusColor()
                        }
                    }}
                />
            </Box>

            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                Last updated: {lastUpdated}
            </Typography>
        </Paper>
    );
};

// Main Dashboard component
const DashboardView = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));
    const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

    // Track drawer state from localStorage to adjust layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Listen for drawer state changes
    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    // Get current user from the store
    const { currentSession } = useImageViewerStore();

    // State for notifications
    const [notifications, setNotifications] = useState(3);
    const [lastRefresh, setLastRefresh] = useState('Just now');

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    // State for demo data
    const [stats, setStats] = useState([
        {
            title: "Total Projects",
            value: "14",
            subtitle: "+2 this month",
            icon: <FileText />,
            color: "#67e8f9",
            chartData: [3, 6, 5, 8, 4, 7, 9, 5, 10, 12, 11, 14]
        },
        {
            title: "Active Sessions",
            value: "3",
            subtitle: "From 2 sessions",
            icon: <Database />,
            color: "#818cf8",
            chartData: [2, 3, 3, 4, 3, 5, 4, 3, 1, 3, 2, 3]
        },
        {
            title: "Processing Jobs",
            value: "7",
            subtitle: "5 completed",
            icon: <Cpu />,
            color: "#8b5cf6",
            chartData: [12, 9, 8, 10, 7, 5, 6, 8, 9, 4, 5, 7]
        },
        {
            title: "Processed Images",
            value: "2.4k",
            subtitle: "+340 today",
            icon: <ImageIcon />,
            color: "#a78bfa",
            chartData: [400, 600, 800, 950, 1200, 1350, 1500, 1680, 1890, 2100, 2250, 2400]
        }
    ]);

    // Mock activity data
    const activities = [
        {
            icon: <CheckCircle />,
            text: "Job #421 (2D Classification) completed",
            time: "10 minutes ago",
            status: "success"
        },
        {
            icon: <Upload />,
            text: "Imported 156 new images from Session #3",
            time: "45 minutes ago",
            status: "info"
        },
        {
            icon: <Settings />,
            text: "System maintenance scheduled for tonight",
            time: "2 hours ago",
            status: "warning"
        },
        {
            icon: <Brain />,
            text: "Particle picking completed for Dataset A",
            time: "Yesterday at 4:15 PM",
            status: "success"
        },
        {
            icon: <AlertCircle />,
            text: "Storage usage approaching 80% capacity",
            time: "Yesterday at 11:30 AM",
            status: "warning"
        }
    ];

    // Mock projects data
    const projects = [
        {
            name: "COVID-19 Spike Protein",
            progress: 85,
            status: "in-progress",
            lastUpdated: "Today at 9:45 AM"
        },
        {
            name: "Ribosome Structure Analysis",
            progress: 100,
            status: "completed",
            lastUpdated: "Yesterday at 3:12 PM"
        },
        {
            name: "Membrane Protein Study",
            progress: 45,
            status: "in-progress",
            lastUpdated: "May 19, 2025"
        }
    ];

    // Mock recently viewed data
    const recentlyViewed = [
        {
            name: "24may21_Sample459-01_00039gr",
            type: "image",
            time: "12 minutes ago"
        },
        {
            name: "Ribosome Dataset (May 2025)",
            type: "session",
            time: "3 hours ago"
        },
        {
            name: "Membrane Protein Analysis",
            type: "project",
            time: "Yesterday at 5:30 PM"
        }
    ];

    // System resource usage
    const systemResources = [
        { name: "CPU", usage: 24 },
        { name: "Memory", usage: 42 },
        { name: "Storage", usage: 68 },
        { name: "Network", usage: 35 }
    ];

    // Handle refresh
    const handleRefresh = () => {
        setLastRefresh('Just now');
    };

    // Navigate to pages
    const navigateTo = (path) => {
        navigate(`/en/panel/${path}`);
    };

    // Calculate greeting based on time of day
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 18) return "Good afternoon";
        return "Good evening";
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
                                <Typography variant="caption" color="text.secondary">
                                    Last updated: {lastRefresh}
                                </Typography>
                                <IconButton size="small" onClick={handleRefresh} sx={{ ml: 0.5 }}>
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
                        {/* Quick Actions */}
                        <Box sx={{ mb: { xs: 2, md: 4 } }}>
                            <Box sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                mb: 2
                            }}>
                                <Typography
                                    variant="h6"
                                    sx={{ fontWeight: 600, fontSize: { xs: '1.1rem', md: '1.25rem' } }}
                                >
                                    Quick Actions
                                </Typography>

                                {isDesktop && (
                                    <Button
                                        variant="text"
                                        endIcon={<ChevronRight size={16} />}
                                        size="small"
                                    >
                                        View All
                                    </Button>
                                )}
                            </Box>

                            <Grid container spacing={1.5}>
                                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                    <QuickActionCard
                                        title="Import Data"
                                        icon={<Upload />}
                                        color="#67e8f9"
                                        onClick={() => navigateTo('import-job')}
                                        featured
                                    />
                                </Grid>
                                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                    <QuickActionCard
                                        title="View Images"
                                        icon={<ImageIcon />}
                                        color="#818cf8"
                                        onClick={() => navigateTo('images')}
                                    />
                                </Grid>
                                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                    <QuickActionCard
                                        title="Process Data"
                                        icon={<Layers />}
                                        color="#8b5cf6"
                                        onClick={() => navigateTo('run-job')}
                                    />
                                </Grid>
                                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                    <QuickActionCard
                                        title="MRC Viewer"
                                        icon={<Microscope />}
                                        color="#a78bfa"
                                        onClick={() => navigateTo('mrc-viewer')}
                                    />
                                </Grid>
                                {!isMobile && (
                                    <>
                                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                            <QuickActionCard
                                                title="Run Job"
                                                icon={<Cpu />}
                                                color="#f471b5"
                                                onClick={() => navigateTo('run-job')}
                                            />
                                        </Grid>
                                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                            <QuickActionCard
                                                title="New Project"
                                                icon={<FolderPlus />}
                                                color="#f97316"
                                                onClick={() => {}}
                                            />
                                        </Grid>
                                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                            <QuickActionCard
                                                title="Statistics"
                                                icon={<BarChart />}
                                                color="#10b981"
                                                onClick={() => {}}
                                            />
                                        </Grid>
                                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                                            <QuickActionCard
                                                title="Settings"
                                                icon={<Settings />}
                                                color="#6b7280"
                                                onClick={() => navigateTo('settings')}
                                            />
                                        </Grid>
                                    </>
                                )}
                            </Grid>
                        </Box>

                        {/* Projects Section */}
                        <Box sx={{ mb: { xs: 2, md: 4 } }}>
                            <Box sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                mb: 2
                            }}>
                                <Typography
                                    variant="h6"
                                    sx={{ fontWeight: 600, fontSize: { xs: '1.1rem', md: '1.25rem' } }}
                                >
                                    Active Projects
                                </Typography>

                                <Button
                                    variant="text"
                                    endIcon={<ChevronRight size={16} />}
                                    size="small"
                                >
                                    View All
                                </Button>
                            </Box>

                            <Grid container spacing={2}>
                                {projects.map((project, index) => (
                                    <Grid key={index} size={{ xs: 12, sm: 6, md: 4 }}>
                                        <ProjectCard
                                            {...project}
                                            onClick={() => {}}
                                        />
                                    </Grid>
                                ))}
                            </Grid>
                        </Box>

                        {/* Activity Feed */}
                        <Box sx={{ mb: { xs: 2, md: 4 } }}>
                            <Box sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                mb: 2
                            }}>
                                <Typography
                                    variant="h6"
                                    sx={{ fontWeight: 600, fontSize: { xs: '1.1rem', md: '1.25rem' } }}
                                >
                                    Recent Activity
                                </Typography>

                                <Button
                                    variant="text"
                                    endIcon={<ChevronRight size={16} />}
                                    size="small"
                                >
                                    View All
                                </Button>
                            </Box>

                            <Paper
                                elevation={1}
                                sx={{
                                    borderRadius: 2,
                                    overflow: 'hidden'
                                }}
                            >
                                <Box sx={{ p: { xs: 1, sm: 2 } }}>
                                    {activities.map((activity, index) => (
                                        <ActivityItem
                                            key={index}
                                            {...activity}
                                        />
                                    ))}
                                </Box>
                            </Paper>
                        </Box>
                    </Grid>

                    {/* Right Sidebar - Panels */}
                    <Grid size={{ xs: 12, lg: 4 }}>
                        {/* Calendar Card */}
                        <Paper elevation={1} sx={{ borderRadius: 2, mb: 3, overflow: 'hidden' }}>
                            <Box sx={{
                                p: 2,
                                backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                borderBottom: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
                            }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                                        Today's Schedule
                                    </Typography>
                                    <Calendar size={18} color={theme.palette.primary.main} />
                                </Box>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                                    Wednesday, May 21, 2025
                                </Typography>
                            </Box>

                            <Box sx={{ p: 2 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                                    <Box sx={{
                                        width: 36,
                                        height: 36,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        borderRadius: 1,
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1)
                                    }}>
                                        <Clock size={16} color={theme.palette.primary.main} />
                                    </Box>
                                    <Box>
                                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                            Team Progress Meeting
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            11:00 AM - 12:00 PM
                                        </Typography>
                                    </Box>
                                </Box>

                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    <Box sx={{
                                        width: 36,
                                        height: 36,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        borderRadius: 1,
                                        backgroundColor: alpha(theme.palette.info.main, 0.1)
                                    }}>
                                        <Clock size={16} color={theme.palette.info.main} />
                                    </Box>
                                    <Box>
                                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                            Data Processing Review
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            3:30 PM - 4:30 PM
                                        </Typography>
                                    </Box>
                                </Box>

                                <Button
                                    fullWidth
                                    variant="text"
                                    size="small"
                                    endIcon={<ChevronRight size={16} />}
                                    sx={{ mt: 2 }}
                                >
                                    View Calendar
                                </Button>
                            </Box>
                        </Paper>

                        {/* Recently Viewed */}
                        <Paper elevation={1} sx={{ borderRadius: 2, mb: 3, overflow: 'hidden' }}>
                            <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                                    Recently Viewed
                                </Typography>
                            </Box>

                            <Box sx={{ p: 1 }}>
                                {recentlyViewed.map((item, index) => (
                                    <RecentlyViewedItem
                                        key={index}
                                        {...item}
                                        onClick={() => {}}
                                    />
                                ))}

                                <Button
                                    fullWidth
                                    variant="text"
                                    size="small"
                                    endIcon={<ChevronRight size={16} />}
                                    sx={{ mt: 1 }}
                                >
                                    View History
                                </Button>
                            </Box>
                        </Paper>

                        {/* System Status */}
                        <Paper elevation={1} sx={{ borderRadius: 2, overflow: 'hidden' }}>
                            <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                                        System Status
                                    </Typography>
                                    <Chip
                                        label="Healthy"
                                        size="small"
                                        icon={<CheckCircle size={12} />}
                                        sx={{
                                            backgroundColor: alpha(theme.palette.success.main, 0.1),
                                            color: theme.palette.success.main,
                                            fontWeight: 500,
                                            '& .MuiChip-icon': {
                                                color: theme.palette.success.main
                                            }
                                        }}
                                    />
                                </Box>
                            </Box>

                            <Box sx={{ p: 2 }}>
                                {systemResources.map((resource, index) => (
                                    <Box key={index} sx={{ mb: 2.5 }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                                {resource.name} Usage
                                            </Typography>
                                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                                {resource.usage}%
                                            </Typography>
                                        </Box>
                                        <LinearProgress
                                            variant="determinate"
                                            value={resource.usage}
                                            sx={{
                                                height: 6,
                                                borderRadius: 3,
                                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                '& .MuiLinearProgress-bar': {
                                                    backgroundColor: resource.usage > 80
                                                        ? theme.palette.error.main
                                                        : resource.usage > 60
                                                            ? theme.palette.warning.main
                                                            : theme.palette.primary.main
                                                }
                                            }}
                                        />
                                    </Box>
                                ))}

                                <Divider sx={{ my: 2 }} />

                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    <Server size={16} color={theme.palette.info.main} />
                                    <Typography variant="body2">
                                        Last maintenance: 2 days ago
                                    </Typography>
                                </Box>

                                <Button
                                    fullWidth
                                    variant="outlined"
                                    size="small"
                                    startIcon={<Info size={16} />}
                                    sx={{ mt: 2 }}
                                >
                                    System Details
                                </Button>
                            </Box>
                        </Paper>
                    </Grid>
                </Grid>
            </Box>
        </Box>
    );
};

export default DashboardView;