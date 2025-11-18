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
    Analytics,
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
            icon: <Analytics sx={{ fontSize: 40 }} />,
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
                    py: { xs: 8, md: 12 },
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
            <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
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
            <Box sx={{ py: { xs: 8, md: 12 }, backgroundColor: alpha(theme.palette.primary.main, 0.02) }}>
                <Container maxWidth="lg">
                    <Box sx={{ textAlign: 'center', mb: { xs: 6, md: 8 } }}>
                        <Chip
                            label="POWERFUL FEATURES"
                            sx={{
                                mb: 3,
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                color: 'primary.main',
                                fontWeight: 600,
                                fontSize: '0.85rem',
                                px: 2,
                            }}
                        />
                        <Typography
                            variant="h2"
                            sx={{
                                fontWeight: 800,
                                mb: 2,
                                fontSize: { xs: '2rem', sm: '2.5rem', md: '3rem' },
                                background: theme.palette.mode === 'dark'
                                    ? 'linear-gradient(45deg, #ffffff, #67e8f9)'
                                    : 'linear-gradient(45deg, #0f172a, #0891b2)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}
                        >
                            Everything You Need
                        </Typography>
                        <Typography
                            variant="h6"
                            color="text.secondary"
                            sx={{
                                maxWidth: '650px',
                                mx: 'auto',
                                fontSize: { xs: '1rem', md: '1.15rem' },
                                lineHeight: 1.7,
                                fontWeight: 400
                            }}
                        >
                            Comprehensive tools designed to accelerate your research workflow
                        </Typography>
                    </Box>

                    <Box
                        sx={{
                            display: 'grid',
                            gridTemplateColumns: {
                                xs: '1fr',
                                sm: 'repeat(2, 1fr)',
                                md: 'repeat(3, 1fr)',
                            },
                            gap: 4,
                        }}
                    >
                        {features.map((feature, index) => (
                            <Card
                                key={index}
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    borderRadius: 4,
                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    backgroundColor: theme.palette.background.paper,
                                    position: 'relative',
                                    overflow: 'hidden',
                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                    boxShadow: 'none',
                                    '&::before': {
                                        content: '""',
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        right: 0,
                                        height: '4px',
                                        background: `linear-gradient(90deg, ${feature.color}, ${alpha(feature.color, 0.6)})`,
                                        opacity: 0,
                                        transition: 'opacity 0.3s ease',
                                    },
                                    '&:hover': {
                                        transform: 'translateY(-8px)',
                                        boxShadow: `0 20px 40px ${alpha(feature.color, 0.2)}`,
                                        borderColor: alpha(feature.color, 0.3),
                                        '&::before': {
                                            opacity: 1,
                                        }
                                    },
                                }}
                            >
                                <CardContent sx={{
                                    p: 4,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    textAlign: 'center',
                                    flexGrow: 1
                                }}>
                                    <Avatar
                                        sx={{
                                            width: 64,
                                            height: 64,
                                            mb: 3,
                                            background: alpha(feature.color, 0.1),
                                            color: feature.color,
                                        }}
                                    >
                                        {feature.icon}
                                    </Avatar>
                                    <Typography
                                        variant="h6"
                                        sx={{
                                            fontWeight: 700,
                                            mb: 1.5,
                                            fontSize: '1.15rem',
                                        }}
                                    >
                                        {feature.title}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        sx={{
                                            lineHeight: 1.7,
                                            fontSize: '0.95rem'
                                        }}
                                    >
                                        {feature.description}
                                    </Typography>
                                </CardContent>
                            </Card>
                        ))}
                    </Box>
                </Container>
            </Box>

            {/* CTA Section */}
            <Box sx={{ py: { xs: 10, md: 14 } }}>
                <Container maxWidth="md">
                    <Box
                        sx={{
                            textAlign: 'center',
                            background: theme.palette.mode === 'dark'
                                ? 'linear-gradient(135deg, rgba(103, 232, 249, 0.08) 0%, rgba(129, 140, 248, 0.08) 100%)'
                                : 'linear-gradient(135deg, rgba(8, 145, 178, 0.04) 0%, rgba(99, 102, 241, 0.04) 100%)',
                            borderRadius: 4,
                            p: { xs: 6, md: 8 },
                            border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`,
                            position: 'relative',
                            overflow: 'hidden',
                            '&::before': {
                                content: '""',
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                background: 'radial-gradient(circle at 50% 50%, rgba(103, 232, 249, 0.05) 0%, transparent 70%)',
                                pointerEvents: 'none',
                            }
                        }}
                    >
                        <Box sx={{ position: 'relative', zIndex: 1 }}>
                            <Box
                                sx={{
                                    display: 'inline-flex',
                                    p: 2,
                                    borderRadius: '50%',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                    mb: 3,
                                }}
                            >
                                <TrendingUp sx={{ fontSize: 48, color: 'primary.main' }} />
                            </Box>
                            <Typography
                                variant="h3"
                                sx={{
                                    fontWeight: 800,
                                    mb: 2,
                                    fontSize: { xs: '1.75rem', md: '2.5rem' },
                                    background: theme.palette.mode === 'dark'
                                        ? 'linear-gradient(45deg, #ffffff, #67e8f9)'
                                        : 'linear-gradient(45deg, #0f172a, #0891b2)',
                                    backgroundClip: 'text',
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                }}
                            >
                                Ready to Transform Your Research?
                            </Typography>
                            <Typography
                                variant="body1"
                                color="text.secondary"
                                sx={{
                                    mb: 4,
                                    maxWidth: '550px',
                                    mx: 'auto',
                                    fontSize: { xs: '1rem', md: '1.1rem' },
                                    lineHeight: 1.7,
                                }}
                            >
                                Join leading research institutions worldwide and accelerate your discoveries
                                with Magellon's advanced CryoEM platform.
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
                                <Button
                                    variant="contained"
                                    size="large"
                                    endIcon={<ArrowForward />}
                                    onClick={() => navigate('/en/panel')}
                                    sx={{
                                        px: 5,
                                        py: 1.75,
                                        fontSize: '1.1rem',
                                        fontWeight: 600,
                                        borderRadius: 2.5,
                                        background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                                        boxShadow: '0 8px 32px rgba(103, 232, 249, 0.25)',
                                        '&:hover': {
                                            background: 'linear-gradient(45deg, #22d3ee, #a5b4fc)',
                                            transform: 'translateY(-2px)',
                                            boxShadow: '0 12px 40px rgba(103, 232, 249, 0.35)',
                                        },
                                        transition: 'all 0.3s ease-in-out',
                                    }}
                                >
                                    Get Started Free
                                </Button>
                                <Button
                                    variant="outlined"
                                    size="large"
                                    onClick={() => navigate('/en/web/contact')}
                                    sx={{
                                        px: 5,
                                        py: 1.75,
                                        fontSize: '1.1rem',
                                        fontWeight: 600,
                                        borderRadius: 2.5,
                                        borderWidth: 2,
                                        '&:hover': {
                                            borderWidth: 2,
                                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                            transform: 'translateY(-2px)',
                                        },
                                        transition: 'all 0.3s ease-in-out',
                                    }}
                                >
                                    Contact Sales
                                </Button>
                            </Box>
                        </Box>
                    </Box>
                </Container>
            </Box>
        </Box>
    );
};