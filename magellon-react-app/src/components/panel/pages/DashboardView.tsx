import React from 'react';
import {
    Box,
    Container,
    Typography,
    Paper,
    Button,
    Stack,
    useMediaQuery,
    useTheme,
    Divider,
    alpha
} from "@mui/material";
import Grid from '@mui/material/Grid'; // Import Grid v2
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
    ChevronRight
} from 'lucide-react';

// Dashboard stat card component with responsive design
const StatCard = ({ title, value, icon, color }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    return (
        <Paper
            elevation={1}
            sx={{
                p: { xs: 1.5, sm: 2, md: 3 },
                height: '100%',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3,
                }
            }}
        >
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography
                        variant="body1"
                        component="div"
                        gutterBottom
                        sx={{
                            fontWeight: 500,
                            fontSize: { xs: '0.875rem', sm: '1rem' }
                        }}
                    >
                        {title}
                    </Typography>
                    <Typography
                        variant={isMobile ? "h6" : isTablet ? "h5" : "h4"}
                        component="div"
                        sx={{
                            fontWeight: 'bold',
                            color: color,
                            lineHeight: 1.2
                        }}
                    >
                        {value}
                    </Typography>
                </Box>
                <Box sx={{
                    backgroundColor: alpha(color, 0.15),
                    p: { xs: 1, sm: 1.25, md: 1.5 },
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    {React.cloneElement(icon, {
                        size: isMobile ? 18 : isTablet ? 22 : 24,
                        color: color
                    })}
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
        <Paper
            elevation={1}
            sx={{
                p: { xs: 1.5, sm: 2, md: 3 },
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3,
                }
            }}
        >
            <Box display="flex" gap={1.5} alignItems="center" mb={isMobile ? 1 : 2}>
                <Box sx={{
                    backgroundColor: alpha(color, 0.15),
                    p: { xs: 0.75, sm: 1 },
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    {React.cloneElement(icon, {
                        size: isMobile ? 16 : isTablet ? 20 : 24,
                        color: color
                    })}
                </Box>
                <Typography
                    variant={isMobile ? "body1" : "h6"}
                    component="div"
                    sx={{
                        fontWeight: 500,
                        fontSize: { xs: '0.9rem', sm: '1rem', md: '1.25rem' }
                    }}
                >
                    {title}
                </Typography>
            </Box>

            <Typography
                variant="body2"
                sx={{
                    mb: { xs: 1.5, sm: 2 },
                    flex: 1,
                    fontSize: { xs: '0.75rem', sm: '0.875rem' },
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
                endIcon={<ChevronRight size={isMobile ? 12 : 16} />}
                fullWidth={isMobile || isTablet}
                sx={{
                    mt: 'auto',
                    alignSelf: 'flex-start',
                    width: isMobile || isTablet ? '100%' : 'auto',
                    borderColor: color,
                    color: color,
                    fontWeight: 500,
                    borderRadius: 1.5,
                    '&:hover': {
                        borderColor: color,
                        backgroundColor: alpha(color, 0.1),
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
            px: { xs: 0.5, sm: 1 },
            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.6)}`
        }}>
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                mb: isMobile ? 0.5 : 0,
                width: isMobile ? '100%' : 'auto'
            }}>
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        bgcolor: theme.palette.mode === 'dark' ? alpha('#fff', 0.05) : alpha('#000', 0.03),
                        borderRadius: '50%',
                        p: 0.75
                    }}
                >
                    {React.cloneElement(icon, { size: 14 })}
                </Box>
                <Typography
                    variant="body2"
                    sx={{
                        color: 'text.primary',
                        fontSize: { xs: '0.8rem', sm: '0.875rem' }
                    }}
                >
                    {text}
                </Typography>
            </Box>
            <Typography
                variant="caption"
                sx={{
                    color: 'text.secondary',
                    fontSize: { xs: '0.7rem', sm: '0.75rem' },
                    ml: isMobile ? 3.5 : 0
                }}
            >
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
        <Container
            maxWidth="xl"
            sx={{
                px: { xs: 1, sm: 2, md: 3 },
                py: { xs: 1, md: 2 }
            }}
        >
            <Box sx={{ mt: { xs: 1, sm: 2, md: 4 }, mb: { xs: 2, sm: 3, md: 5 } }}>
                {/* Responsive header with welcome message */}
                <Typography
                    variant={isMobile ? "h5" : "h4"}
                    component="h1"
                    gutterBottom
                    sx={{
                        fontSize: { xs: '1.5rem', sm: '1.8rem', md: '2.125rem' },
                        fontWeight: 700
                    }}
                >
                    Dashboard
                </Typography>

                <Typography
                    variant="body1"
                    sx={{
                        mb: { xs: 2, sm: 3, md: 4 },
                        color: 'text.secondary',
                        fontSize: { xs: '0.875rem', sm: '1rem' }
                    }}
                >
                    Welcome to Magellon. Here's an overview of your data and activities.
                </Typography>

                {/* Stats Section */}
                <Box sx={{ mb: { xs: 3, sm: 4, md: 5 } }}>
                    <Typography
                        variant={isMobile ? "h6" : "h5"}
                        component="h2"
                        gutterBottom
                        sx={{
                            mt: { xs: 2, sm: 3, md: 4 },
                            fontSize: { xs: '1.15rem', sm: '1.3rem', md: '1.5rem' },
                            fontWeight: 600
                        }}
                    >
                        Overview
                    </Typography>

                    {/* Updated Grid using v2 pattern with explicit size props */}
                    <Grid
                        container
                        spacing={{ xs: 1.5, sm: 2, md: 3 }}
                        sx={{ mb: { xs: 2, sm: 3, md: 4 } }}
                    >
                        {stats.map((stat, index) => (
                            <Grid
                                key={index}
                                size={{ xs: 6, md: 3 }}
                            >
                                <StatCard {...stat} />
                            </Grid>
                        ))}
                    </Grid>
                </Box>

                {/* Quick Actions Section */}
                <Box sx={{ mb: { xs: 3, sm: 4, md: 5 } }}>
                    <Typography
                        variant={isMobile ? "h6" : "h5"}
                        component="h2"
                        gutterBottom
                        sx={{
                            fontSize: { xs: '1.15rem', sm: '1.3rem', md: '1.5rem' },
                            fontWeight: 600
                        }}
                    >
                        Quick Actions
                    </Typography>

                    <Grid
                        container
                        spacing={{ xs: 1.5, sm: 2, md: 3 }}
                    >
                        {actions.map((action, index) => (
                            <Grid
                                key={index}
                                size={{ xs: 12, sm: 6, md: 3 }}
                            >
                                <ActionCard {...action} />
                            </Grid>
                        ))}
                    </Grid>
                </Box>

                {/* Recent Activity Section */}
                <Box sx={{ mb: { xs: 4, sm: 5 } }}>
                    <Typography
                        variant={isMobile ? "h6" : "h5"}
                        component="h2"
                        gutterBottom
                        sx={{
                            mt: { xs: 2, sm: 3, md: 4 },
                            fontSize: { xs: '1.15rem', sm: '1.3rem', md: '1.5rem' },
                            fontWeight: 600
                        }}
                    >
                        Recent Activity
                    </Typography>

                    <Paper
                        elevation={1}
                        sx={{
                            p: { xs: 1.5, sm: 2, md: 3 },
                            mb: 4,
                            borderRadius: 2
                        }}
                    >
                        <Stack spacing={{ xs: 0, sm: 0.5, md: 1 }}>
                            {activities.map((activity, index) => (
                                <ActivityItem
                                    key={index}
                                    icon={activity.icon}
                                    text={activity.text}
                                    time={activity.time}
                                />
                            ))}

                            {/* View all button at the bottom */}
                            <Box sx={{
                                pt: { xs: 1.5, sm: 2 },
                                display: 'flex',
                                justifyContent: 'center'
                            }}>
                                <Button
                                    variant="text"
                                    size={isMobile ? "small" : "medium"}
                                    endIcon={<ChevronRight size={16} />}
                                    sx={{
                                        color: '#67e8f9',
                                        fontWeight: 500
                                    }}
                                >
                                    View All Activity
                                </Button>
                            </Box>
                        </Stack>
                    </Paper>
                </Box>
            </Box>
        </Container>
    );
};

export default DashboardView;