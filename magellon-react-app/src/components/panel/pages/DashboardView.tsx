import React from 'react';
import { Box, Container, Typography, Grid, Paper, Button, Stack } from "@mui/material";
import { BarChart2, Brain, Cpu, Database, FileText, Image as ImageIcon, LayersIcon, Settings, Upload } from 'lucide-react';

// Dashboard stat card component
const StatCard = ({ title, value, icon, color }) => (
    <Paper sx={{ p: 3, height: '100%', background: `linear-gradient(135deg, ${color}15, ${color}05)`, border: `1px solid ${color}20` }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box>
                <Typography variant="h6" component="div" gutterBottom>
                    {title}
                </Typography>
                <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', color: color }}>
                    {value}
                </Typography>
            </Box>
            <Box sx={{
                backgroundColor: `${color}15`,
                p: 1,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                {React.cloneElement(icon, { size: 24, color: color })}
            </Box>
        </Box>
    </Paper>
);

// Action card component
const ActionCard = ({ title, description, icon, color, buttonText, onClick }) => (
    <Paper sx={{
        p: 3,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: `linear-gradient(135deg, ${color}15, ${color}05)`,
        border: `1px solid ${color}20`
    }}>
        <Box display="flex" gap={2} alignItems="center" mb={2}>
            <Box sx={{
                backgroundColor: `${color}15`,
                p: 1,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                {React.cloneElement(icon, { size: 24, color: color })}
            </Box>
            <Typography variant="h6" component="div">
                {title}
            </Typography>
        </Box>
        <Typography variant="body2" sx={{ mb: 2, flex: 1 }}>
            {description}
        </Typography>
        <Button
            variant="outlined"
            startIcon={React.cloneElement(icon, { size: 16 })}
            sx={{
                alignSelf: 'flex-start',
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

// Dashboard component
const DashboardView = () => {
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
            icon: <LayersIcon />,
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

    return (
        <Container maxWidth="xl">
            <Box sx={{ mt: 4, mb: 5 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Dashboard
                </Typography>
                <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
                    Welcome to Magellon. Here's an overview of your data and activities.
                </Typography>

                {/* Stats Section */}
                <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
                    Overview
                </Typography>
                <Grid container spacing={3} sx={{ mb: 5 }}>
                    {stats.map((stat, index) => (
                        <Grid item xs={12} sm={6} md={3} key={index}>
                            <StatCard {...stat} />
                        </Grid>
                    ))}
                </Grid>

                {/* Quick Actions Section */}
                <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
                    Quick Actions
                </Typography>
                <Grid container spacing={3}>
                    {actions.map((action, index) => (
                        <Grid item xs={12} sm={6} md={3} key={index}>
                            <ActionCard {...action} />
                        </Grid>
                    ))}
                </Grid>

                {/* Recent Activity Section */}
                <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 5 }}>
                    Recent Activity
                </Typography>
                <Paper sx={{ p: 3, mb: 4 }}>
                    <Stack spacing={2}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <LayersIcon size={16} />
                                <Typography>Job #421 (2D Classification) completed</Typography>
                            </Box>
                            <Typography variant="caption">Today, 9:45 AM</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Upload size={16} />
                                <Typography>Imported 156 new images from Session #3</Typography>
                            </Box>
                            <Typography variant="caption">Today, 8:12 AM</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Settings size={16} />
                                <Typography>System maintenance completed</Typography>
                            </Box>
                            <Typography variant="caption">Yesterday, 11:30 PM</Typography>
                        </Box>
                    </Stack>
                </Paper>
            </Box>
        </Container>
    );
};

export default DashboardView;