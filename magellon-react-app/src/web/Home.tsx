import React from 'react';
import {
    Box,
    Container,
    Typography,
    Button,
    Grid,
    Card,
    CardContent,
    Avatar,
    Chip,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Science,
    Speed,
    Security,
    CloudQueue,
    ArrowForward,
    PlayArrow,
    TrendingUp,
    Biotech,
    Psychology,

} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

export const Home = () => {
    const navigate = useNavigate();
    const theme = useTheme();

    const features = [
        {
            icon: <Biotech sx={{ fontSize: 40 }} />,
            title: "Advanced CryoEM Analysis",
            description: "State-of-the-art algorithms for high-resolution structural analysis and reconstruction.",
            color: '#67e8f9'
        },
        {
            icon: <Speed sx={{ fontSize: 40 }} />,
            title: "Lightning Fast Processing",
            description: "Optimized workflows that reduce processing time by up to 90% compared to traditional methods.",
            color: '#818cf8'
        },
        {
            icon: <Psychology sx={{ fontSize: 40 }} />,
            title: "AI-Powered Insights",
            description: "Machine learning algorithms that automatically identify and classify molecular structures.",
            color: '#f59e0b'
        },
        {
            icon: <Psychology sx={{ fontSize: 40 }} />,
            title: "Precision Analytics",
            description: "Sub-angstrom resolution analysis with industry-leading accuracy and reliability.",
            color: '#10b981'
        },
        {
            icon: <Security sx={{ fontSize: 40 }} />,
            title: "Secure & Compliant",
            description: "Enterprise-grade security with full compliance for pharmaceutical research standards.",
            color: '#ef4444'
        },
        {
            icon: <CloudQueue sx={{ fontSize: 40 }} />,
            title: "Cloud Integration",
            description: "Seamless cloud processing with unlimited scalability and global accessibility.",
            color: '#8b5cf6'
        },
    ];

    const stats = [
        { value: "50K+", label: "Structures Analyzed" },
        { value: "99.9%", label: "Uptime Guarantee" },
        { value: "45%", label: "Faster Results" },
        { value: "500+", label: "Research Teams" },
    ];

    return (
        <Box sx={{ width: '100%' }}>
            {/* Hero Section */}
            <Box
                sx={{
                    position: 'relative',
                    minHeight: { xs: '80vh', md: '85vh' }, // Reduced height to allow footer to show
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    overflow: 'hidden',
                    background: theme.palette.mode === 'dark'
                        ? 'radial-gradient(ellipse at center, rgba(103, 232, 249, 0.1) 0%, transparent 70%)'
                        : 'radial-gradient(ellipse at center, rgba(8, 145, 178, 0.05) 0%, transparent 70%)',
                }}
            >
                {/* Animated Background Elements */}
                <Box
                    sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        '&::before': {
                            content: '""',
                            position: 'absolute',
                            top: '20%',
                            right: '10%',
                            width: '300px',
                            height: '300px',
                            background: 'radial-gradient(circle, rgba(103, 232, 249, 0.1) 0%, transparent 70%)',
                            borderRadius: '50%',
                            animation: 'float 6s ease-in-out infinite',
                        },
                        '&::after': {
                            content: '""',
                            position: 'absolute',
                            bottom: '20%',
                            left: '5%',
                            width: '200px',
                            height: '200px',
                            background: 'radial-gradient(circle, rgba(129, 140, 248, 0.1) 0%, transparent 70%)',
                            borderRadius: '50%',
                            animation: 'float 8s ease-in-out infinite reverse',
                        },
                        '@keyframes float': {
                            '0%, 100%': { transform: 'translateY(0px)' },
                            '50%': { transform: 'translateY(-20px)' },
                        },
                    }}
                />

                <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 2 }}>
                    <Grid container spacing={4} alignItems="center">
                        <Grid item xs={12} md={6}>
                            <Box sx={{ mb: 3 }}>
                                <Chip
                                    label="Next-Gen CryoEM Platform"
                                    sx={{
                                        mb: 3,
                                        background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                                        color: 'white',
                                        fontWeight: 600,
                                        fontSize: '0.9rem',
                                        px: 2,
                                        py: 1,
                                    }}
                                />
                                <Typography
                                    variant="h1"
                                    sx={{
                                        fontSize: { xs: '2.5rem', sm: '3.5rem', md: '4.5rem' },
                                        fontWeight: 800,
                                        lineHeight: 1.1,
                                        background: theme.palette.mode === 'dark'
                                            ? 'linear-gradient(45deg, #ffffff, #67e8f9)'
                                            : 'linear-gradient(45deg, #0f172a, #0891b2)',
                                        backgroundClip: 'text',
                                        WebkitBackgroundClip: 'text',
                                        WebkitTextFillColor: 'transparent',
                                        mb: 2,
                                    }}
                                >
                                    Revolutionizing
                                    <br />
                                    Structural Biology
                                </Typography>
                                <Typography
                                    variant="h5"
                                    sx={{
                                        color: 'text.secondary',
                                        fontWeight: 400,
                                        lineHeight: 1.6,
                                        mb: 4,
                                        maxWidth: '500px',
                                    }}
                                >
                                    Unlock the secrets of molecular structures with AI-powered CryoEM analysis.
                                    Faster, more accurate, and infinitely scalable.
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                                    <Button
                                        variant="contained"
                                        size="large"
                                        endIcon={<ArrowForward />}
                                        onClick={() => navigate('/en/panel')}
                                        sx={{
                                            px: 4,
                                            py: 1.5,
                                            fontSize: '1.1rem',
                                            fontWeight: 600,
                                            borderRadius: 3,
                                            background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                                            '&:hover': {
                                                background: 'linear-gradient(45deg, #22d3ee, #a5b4fc)',
                                                transform: 'translateY(-2px)',
                                                boxShadow: '0 12px 40px rgba(103, 232, 249, 0.4)',
                                            },
                                            transition: 'all 0.3s ease-in-out',
                                        }}
                                    >
                                        Start Analysis
                                    </Button>
                                    <Button
                                        variant="outlined"
                                        size="large"
                                        startIcon={<PlayArrow />}
                                        sx={{
                                            px: 4,
                                            py: 1.5,
                                            fontSize: '1.1rem',
                                            fontWeight: 600,
                                            borderRadius: 3,
                                            borderColor: 'primary.main',
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                transform: 'translateY(-2px)',
                                            },
                                            transition: 'all 0.3s ease-in-out',
                                        }}
                                    >
                                        Watch Demo
                                    </Button>
                                </Box>
                            </Box>
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <Box
                                sx={{
                                    position: 'relative',
                                    display: 'flex',
                                    justifyContent: 'center',
                                    alignItems: 'center',
                                    height: '400px',
                                }}
                            >
                                {/* Animated Molecular Structure Visualization */}
                                <Box
                                    sx={{
                                        width: '350px',
                                        height: '350px',
                                        position: 'relative',
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                >
                                    {[...Array(3)].map((_, i) => (
                                        <Box
                                            key={i}
                                            sx={{
                                                position: 'absolute',
                                                width: `${200 + i * 50}px`,
                                                height: `${200 + i * 50}px`,
                                                border: `2px solid ${alpha('#67e8f9', 0.3 - i * 0.1)}`,
                                                borderRadius: '50%',
                                                animation: `rotate${i} ${10 + i * 5}s linear infinite`,
                                                '@keyframes rotate0': {
                                                    '0%': { transform: 'rotate(0deg)' },
                                                    '100%': { transform: 'rotate(360deg)' },
                                                },
                                                '@keyframes rotate1': {
                                                    '0%': { transform: 'rotate(0deg)' },
                                                    '100%': { transform: 'rotate(-360deg)' },
                                                },
                                                '@keyframes rotate2': {
                                                    '0%': { transform: 'rotate(0deg)' },
                                                    '100%': { transform: 'rotate(360deg)' },
                                                },
                                            }}
                                        />
                                    ))}
                                    <Science
                                        sx={{
                                            fontSize: 80,
                                            color: 'primary.main',
                                            filter: 'drop-shadow(0 0 20px rgba(103, 232, 249, 0.5))',
                                            animation: 'pulse 2s ease-in-out infinite',
                                            '@keyframes pulse': {
                                                '0%, 100%': { transform: 'scale(1)' },
                                                '50%': { transform: 'scale(1.1)' },
                                            },
                                        }}
                                    />
                                </Box>
                            </Box>
                        </Grid>
                    </Grid>
                </Container>
            </Box>

            {/* Stats Section */}
            <Container maxWidth="lg" sx={{ py: 8 }}>
                <Grid container spacing={4}>
                    {stats.map((stat, index) => (
                        <Grid item xs={6} md={3} key={index}>
                            <Box sx={{ textAlign: 'center' }}>
                                <Typography
                                    variant="h3"
                                    sx={{
                                        fontWeight: 800,
                                        background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                                        backgroundClip: 'text',
                                        WebkitBackgroundClip: 'text',
                                        WebkitTextFillColor: 'transparent',
                                        mb: 1,
                                    }}
                                >
                                    {stat.value}
                                </Typography>
                                <Typography variant="body1" color="text.secondary" sx={{ fontWeight: 500 }}>
                                    {stat.label}
                                </Typography>
                            </Box>
                        </Grid>
                    ))}
                </Grid>
            </Container>

            {/* Features Section */}
            <Box sx={{ py: { xs: 8, md: 12 }, backgroundColor: alpha(theme.palette.primary.main, 0.03) }}>
                <Container maxWidth="xl">
                    <Box sx={{ textAlign: 'center', mb: { xs: 6, md: 10 } }}>
                        <Typography
                            variant="h2"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                fontSize: { xs: '2rem', sm: '2.5rem', md: '3rem' },
                                background: theme.palette.mode === 'dark'
                                    ? 'linear-gradient(45deg, #ffffff, #67e8f9)'
                                    : 'linear-gradient(45deg, #0f172a, #0891b2)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}
                        >
                            Cutting-Edge Features
                        </Typography>
                        <Typography
                            variant="h6"
                            color="text.secondary"
                            sx={{
                                maxWidth: '700px',
                                mx: 'auto',
                                fontSize: { xs: '1.1rem', md: '1.25rem' },
                                lineHeight: 1.6
                            }}
                        >
                            Experience the next generation of CryoEM analysis with our comprehensive suite of tools
                        </Typography>
                    </Box>

                    <Grid
                        container
                        spacing={{ xs: 3, sm: 4, md: 5 }}
                        sx={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            justifyContent: 'center',
                            alignItems: 'stretch'
                        }}
                    >
                        {features.map((feature, index) => (
                            <Grid
                                item
                                xs={12}
                                sm={6}
                                lg={4}
                                key={index}
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column'
                                }}
                            >
                                <Card
                                    sx={{
                                        height: '100%',
                                        minHeight: '320px',
                                        borderRadius: 4,
                                        border: 'none',
                                        backgroundColor: alpha(theme.palette.background.paper, 0.8),
                                        backdropFilter: 'blur(20px)',
                                        position: 'relative',
                                        overflow: 'hidden',
                                        transition: 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                        '&::before': {
                                            content: '""',
                                            position: 'absolute',
                                            top: 0,
                                            left: 0,
                                            right: 0,
                                            height: '4px',
                                            background: `linear-gradient(90deg, ${feature.color}, ${alpha(feature.color, 0.7)})`,
                                            transform: 'scaleX(0)',
                                            transformOrigin: 'left',
                                            transition: 'transform 0.4s ease',
                                        },
                                        '&:hover': {
                                            transform: 'translateY(-12px) scale(1.02)',
                                            boxShadow: `0 25px 80px ${alpha(feature.color, 0.25)}`,
                                            '&::before': {
                                                transform: 'scaleX(1)',
                                            }
                                        },
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 3, sm: 4 },
                                        height: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        justifyContent: 'space-between'
                                    }}>
                                        <Box>
                                            <Avatar
                                                sx={{
                                                    width: { xs: 60, sm: 70 },
                                                    height: { xs: 60, sm: 70 },
                                                    mb: 3,
                                                    background: `linear-gradient(135deg, ${feature.color}, ${alpha(feature.color, 0.7)})`,
                                                    boxShadow: `0 12px 40px ${alpha(feature.color, 0.3)}`,
                                                    transition: 'all 0.3s ease',
                                                    '&:hover': {
                                                        transform: 'scale(1.1) rotate(5deg)',
                                                        boxShadow: `0 15px 50px ${alpha(feature.color, 0.4)}`,
                                                    }
                                                }}
                                            >
                                                {feature.icon}
                                            </Avatar>
                                            <Typography
                                                variant="h5"
                                                sx={{
                                                    fontWeight: 700,
                                                    mb: 2,
                                                    fontSize: { xs: '1.3rem', sm: '1.5rem' },
                                                    color: 'text.primary'
                                                }}
                                            >
                                                {feature.title}
                                            </Typography>
                                        </Box>
                                        <Typography
                                            variant="body1"
                                            color="text.secondary"
                                            sx={{
                                                lineHeight: 1.8,
                                                fontSize: { xs: '0.95rem', sm: '1rem' }
                                            }}
                                        >
                                            {feature.description}
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>

                    {/* Optional: Add a subtle animation for the grid */}
                    <style jsx>{`
                        @media (min-width: 960px) {
                            .MuiGrid-item:nth-child(1) { animation-delay: 0.1s; }
                            .MuiGrid-item:nth-child(2) { animation-delay: 0.2s; }
                            .MuiGrid-item:nth-child(3) { animation-delay: 0.3s; }
                            .MuiGrid-item:nth-child(4) { animation-delay: 0.4s; }
                            .MuiGrid-item:nth-child(5) { animation-delay: 0.5s; }
                            .MuiGrid-item:nth-child(6) { animation-delay: 0.6s; }
                        }
                    `}</style>
                </Container>
            </Box>

            {/* CTA Section */}
            <Container maxWidth="lg" sx={{ py: 12 }}>
                <Box
                    sx={{
                        textAlign: 'center',
                        background: theme.palette.mode === 'dark'
                            ? 'linear-gradient(135deg, rgba(103, 232, 249, 0.1) 0%, rgba(129, 140, 248, 0.1) 100%)'
                            : 'linear-gradient(135deg, rgba(8, 145, 178, 0.05) 0%, rgba(99, 102, 241, 0.05) 100%)',
                        borderRadius: 4,
                        p: 8,
                        border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
                    }}
                >
                    <TrendingUp sx={{ fontSize: 60, color: 'primary.main', mb: 3 }} />
                    <Typography variant="h3" sx={{ fontWeight: 700, mb: 2 }}>
                        Ready to Transform Your Research?
                    </Typography>
                    <Typography variant="h6" color="text.secondary" sx={{ mb: 4, maxWidth: '600px', mx: 'auto' }}>
                        Join leading research institutions worldwide and accelerate your discoveries with Magellon's
                        advanced CryoEM platform.
                    </Typography>
                    <Button
                        variant="contained"
                        size="large"
                        endIcon={<ArrowForward />}
                        onClick={() => navigate('/en/panel')}
                        sx={{
                            px: 6,
                            py: 2,
                            fontSize: '1.2rem',
                            fontWeight: 600,
                            borderRadius: 3,
                            background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                            '&:hover': {
                                background: 'linear-gradient(45deg, #22d3ee, #a5b4fc)',
                                transform: 'translateY(-3px)',
                                boxShadow: '0 15px 50px rgba(103, 232, 249, 0.4)',
                            },
                            transition: 'all 0.3s ease-in-out',
                        }}
                    >
                        Get Started Today
                    </Button>
                </Box>
            </Container>
        </Box>
    );
};