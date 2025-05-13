import React from 'react';
import { Box, Container, Typography, Grid, Paper, Button, Stack, useMediaQuery, useTheme, Divider } from "@mui/material";
import { BarChart2, Brain, Cpu, Database, FileText, Image as ImageIcon, Layers, Settings, Upload } from 'lucide-react';

// Dashboard stat card component with responsive design
const StatCard = ({ title, value, icon, color }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    return (
        <Paper sx={{
            p: isMobile ? 2 : 3,
            height: '100%',
            background: `linear-gradient(135deg, ${color}15, ${color}05)`,
            border: `1px solid ${color}20`,
            transition: 'all 0.3s ease'
        }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant={isMobile ? "subtitle1" : "h6"} component="div" gutterBottom>
                        {title}
                    </Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} component="div" sx={{ fontWeight: 'bold', color: color }}>
                        {value}
                    </Typography>
                </Box>
                <Box sx={{
                    backgroundColor: `${color}15`,
                    p: isMobile ? 0.75 : 1,
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    {React.cloneElement(icon, { size: isMobile ? 18 : 24, color: color })}
                </Box>
            </Box>
        </Paper>
    );
};

// Action card component with responsive design
const ActionCard = ({ title, description, icon, color, buttonText, onClick }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    return (
        <Paper sx={{
            p: isMobile ? 2 : 3,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            background: `linear-gradient(135deg, ${color}15, ${color}05)`,
            border: `1px solid ${color}20`,
            transition: 'all 0.3s ease'
        }}>
            <Box display="flex" gap={1.5} alignItems="center" mb={isMobile ? 1 : 2}>
                <Box sx={{
                    backgroundColor: `${color}15`,
                    p: isMobile ? 0.75 : 1,
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    {React.cloneElement(icon, { size: isMobile ? 18 : 24, color: color })}
                </Box>
                <Typography variant={isMobile ? "subtitle1" : "h6"} component="div">
                    {title}
                </Typography>
            </Box>
            <Typography
                variant="body2"
                sx={{
                    mb: isMobile ? 1.5 : 2,
                    flex: 1,
                    // Make description shorter on mobile but still visible
                    display: '-webkit-box',
                    overflow: 'hidden',
                    WebkitBoxOrient: 'vertical',
                    WebkitLineClamp: isMobile ? 2 : 3
                }}
            >
                {description}
            </Typography>
            <Button
                variant="outlined"
                size={isMobile ? "small" : "medium"}
                startIcon={React.cloneElement(icon, { size: isMobile ? 14 : 16 })}
                fullWidth={isTablet}
                sx={{
                    alignSelf: isTablet ? 'stretch' : 'flex-start',
                    borderColor: color,
                    color: color,
                    '&:hover': {
                        borderColor: color,
                        backgroundColor: `${color}15`,
                    }
                }}
                onClick={onClick}
            >
                {buttonText}
            </Button>
        </Paper>
    );
};

// Activity item for recent activity section
const ActivityItem = ({ icon, text, time }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            justifyContent: isMobile ? 'flex-start' : 'space-between',
            alignItems: isMobile ? 'flex-start' : 'center',
            py: 1.5,
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: isMobile ? 0.5 : 0 }}>
                {React.cloneElement(icon, { size: 16 })}
                <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    {text}
                </Typography>
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {time}
            </Typography>
        </Box>
    );
};

// Dashboard component with improved responsiveness
const DashboardView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Statistics data
    const stats = [
        { title: "Total Projects", value: "14", icon: <FileText />, color: "#67e8f9" },
        { title: "Active Sessions", value: "3", icon: <Database />, color: "#818cf8" },
        { title: "Processing Jobs", value: "7", icon: <Cpu />, color: "#8b5cf6" },
        { title: "Processed Images", value: "2.4k", icon: <ImageIcon />, color: "#a78bfa" }
    ];

    // Quick actions
    const actions = [
        {
            title: "Import Data",
            description: "Import new data from microscopes or external sources",
            icon: <Upload />,
            color: "#67e8f9",
            buttonText: "Import Now",
            onClick: () => console.log("Import clicked")
        },
        {
            title: "Process Images",
            description: "Start processing pipeline for image analysis",
            icon: <Layers />,
            color: "#818cf8",
            buttonText: "Start Processing",
            onClick: () => console.log("Process clicked")
        },
        {
            title: "Run 2D Classification",
            description: "Analyze and classify your particle images",
            icon: <Brain />,
            color: "#8b5cf6",
            buttonText: "Start Classification",
            onClick: () => console.log("Classification clicked")
        },
        {
            title: "View Statistics",
            description: "View detailed statistics for your projects",
            icon: <BarChart2 />,
            color: "#a78bfa",
            buttonText: "View Stats",
            onClick: () => console.log("Stats clicked")
        }
    ];

    // Recent activity data
    const activities = [
        {
            icon: <Layers />,
            text: "Job #421 (2D Classification) completed",
            time: "Today, 9:45 AM"
        },
        {
            icon: <Upload />,
            text: "Imported 156 new images from Session #3",
            time: "Today, 8:12 AM"
        },
        {
            icon: <Settings />,
            text: "System maintenance completed",
            time: "Yesterday, 11:30 PM"
        },
        {
            icon: <Brain />,
            text: "Particle picking completed for Dataset A",
            time: "Yesterday, 4:15 PM"
        }
    ];

    return (
        <Container maxWidth="xl" sx={{ px: isMobile ? 2 : 3 }}>
            <Box sx={{ mt: isMobile ? 2 : 4, mb: isMobile ? 3 : 5 }}>
                {/* Responsive header with welcome message */}
                <Typography variant={isMobile ? "h5" : "h4"} component="h1" gutterBottom>
                    Dashboard
                </Typography>
                <Typography
                    variant="body1"
                    sx={{
                        mb: isMobile ? 2 : 4,
                        color: 'text.secondary',
                        fontSize: isMobile ? '0.875rem' : '1rem'
                    }}
                >
                    Welcome to Magellon. Here's an overview of your data and activities.
                </Typography>

                {/* Stats Section */}
                <Typography
                    variant={isMobile ? "h6" : "h5"}
                    component="h2"
                    gutterBottom
                    sx={{ mt: isMobile ? 2 : 4 }}
                >
                    Overview
                </Typography>
                <Grid container spacing={isMobile ? 2 : 3} sx={{ mb: isMobile ? 3 : 5 }}>
                    {stats.map((stat, index) => (
                        <Grid item xs={6} sm={6} md={3} key={index}>
                            <StatCard {...stat} />
                        </Grid>
                    ))}
                </Grid>

                {/* Quick Actions Section */}
                <Typography
                    variant={isMobile ? "h6" : "h5"}
                    component="h2"
                    gutterBottom
                    sx={{ mt: isMobile ? 2 : 4 }}
                >
                    Quick Actions
                </Typography>
                <Grid container spacing={isMobile ? 2 : 3}>
                    {actions.map((action, index) => (
                        <Grid item xs={12} sm={6} md={3} key={index}>
                            <ActionCard {...action} />
                        </Grid>
                    ))}
                </Grid>

                {/* Recent Activity Section */}
                <Typography
                    variant={isMobile ? "h6" : "h5"}
                    component="h2"
                    gutterBottom
                    sx={{ mt: isMobile ? 3 : 5 }}
                >
                    Recent Activity
                </Typography>
                <Paper sx={{ p: isMobile ? 2 : 3, mb: 4 }}>
                    <Stack spacing={isMobile ? 0 : 1.5}>
                        {activities.map((activity, index) => (
                            <ActivityItem
                                key={index}
                                icon={activity.icon}
                                text={activity.text}
                                time={activity.time}
                            />
                        ))}

                        {/* View all button at the bottom for mobile */}
                        <Box sx={{
                            pt: isMobile ? 2 : 1,
                            display: 'flex',
                            justifyContent: 'center'
                        }}>
                            <Button
                                variant="text"
                                size={isMobile ? "small" : "medium"}
                                sx={{ color: '#67e8f9' }}
                            >
                                View All Activity
                            </Button>
                        </Box>
                    </Stack>
                </Paper>
            </Box>
        </Container>
    );
};

export default DashboardView;

