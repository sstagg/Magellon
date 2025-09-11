import React from 'react';
import {
    Container,
    Typography,
    Link,
    Grid,
    Box,
    Divider,
    IconButton,
    alpha,
    useTheme,
    Stack,
    Chip
} from '@mui/material';
import {
    Science,
    GitHub,
    Twitter,
    LinkedIn,
    Email,
    Phone,
    LocationOn,
    Launch,
    Biotech,
    Security,
    CloudQueue,
    Speed
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

export default function WebFooter() {
    const theme = useTheme();
    const navigate = useNavigate();

    const quickLinks = [
        { label: 'Home', path: '/en/web/home' },
        { label: 'About', path: '/en/web/about' },
        { label: 'Contact', path: '/en/web/contact' },
        { label: 'Launch Panel', path: '/en/panel/images' },
    ];

    const features = [
        { label: 'CryoEM Analysis', icon: <Biotech sx={{ fontSize: 16 }} /> },
        { label: 'AI Processing', icon: <Speed sx={{ fontSize: 16 }} /> },
        { label: 'Secure Platform', icon: <Security sx={{ fontSize: 16 }} /> },
        { label: 'Cloud Integration', icon: <CloudQueue sx={{ fontSize: 16 }} /> },
    ];

    const socialLinks = [
        { icon: <GitHub />, href: 'https://github.com/magellon', label: 'GitHub' },
        { icon: <Twitter />, href: 'https://twitter.com/magellon', label: 'Twitter' },
        { icon: <LinkedIn />, href: 'https://linkedin.com/company/magellon', label: 'LinkedIn' },
    ];

    return (
        <Box
            component="footer"
            sx={{
                width: '100%',
                mt: 'auto',
                background: theme.palette.mode === 'dark'
                    ? `linear-gradient(135deg, ${alpha('#0a1929', 0.98)} 0%, ${alpha('#1e293b', 0.98)} 100%)`
                    : `linear-gradient(135deg, ${alpha('#f8fafc', 0.98)} 0%, ${alpha('#e2e8f0', 0.98)} 100%)`,
                backdropFilter: 'blur(24px)',
                borderTop: `1px solid ${alpha(theme.palette.divider, 0.12)}`,
                position: 'relative',
                overflow: 'hidden',
                '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '2px',
                    background: 'linear-gradient(90deg, #67e8f9, #818cf8, #f59e0b, #10b981)',
                    opacity: 0.6,
                }
            }}
        >
            <Container maxWidth="xl" sx={{ py: { xs: 4, md: 6 } }}>
                <Grid container spacing={{ xs: 4, md: 6 }}>
                    {/* Brand Section */}
                    <Grid item xs={12} md={4}>
                        <Box sx={{ mb: 3 }}>
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    mb: 2,
                                    cursor: 'pointer',
                                    transition: 'all 0.3s ease-in-out',
                                    '&:hover': {
                                        transform: 'scale(1.02)',
                                    }
                                }}
                                onClick={() => navigate('/en/web/home')}
                            >
                                <Science
                                    sx={{
                                        mr: 1.5,
                                        fontSize: 36,
                                        color: 'primary.main',
                                        filter: 'drop-shadow(0 0 12px rgba(103, 232, 249, 0.4))'
                                    }}
                                />
                                <Typography
                                    variant="h4"
                                    sx={{
                                        fontWeight: 800,
                                        fontSize: '1.8rem',
                                        background: theme.palette.mode === 'dark'
                                            ? 'linear-gradient(45deg, #67e8f9, #818cf8)'
                                            : 'linear-gradient(45deg, #0891b2, #6366f1)',
                                        backgroundClip: 'text',
                                        WebkitBackgroundClip: 'text',
                                        WebkitTextFillColor: 'transparent',
                                        letterSpacing: '-0.5px'
                                    }}
                                >
                                    Magellon
                                </Typography>
                            </Box>
                            <Typography
                                variant="body1"
                                color="text.secondary"
                                sx={{
                                    mb: 3,
                                    lineHeight: 1.7,
                                    fontSize: '1rem'
                                }}
                            >
                                Revolutionizing structural biology with AI-powered CryoEM analysis.
                                Empowering researchers worldwide to unlock molecular secrets.
                            </Typography>

                            {/* Feature Chips */}
                            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                                {features.map((feature, index) => (
                                    <Chip
                                        key={index}
                                        icon={feature.icon}
                                        label={feature.label}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            borderColor: alpha(theme.palette.primary.main, 0.3),
                                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                transform: 'translateY(-1px)',
                                            },
                                            transition: 'all 0.2s ease',
                                            '& .MuiChip-label': {
                                                fontSize: '0.75rem',
                                                fontWeight: 500,
                                            }
                                        }}
                                    />
                                ))}
                            </Stack>
                        </Box>
                    </Grid>

                    {/* Quick Links */}
                    <Grid item xs={12} sm={6} md={2}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                fontSize: '1.1rem'
                            }}
                        >
                            Quick Links
                        </Typography>
                        <Stack spacing={1.5}>
                            {quickLinks.map((link, index) => (
                                <Link
                                    key={index}
                                    component="button"
                                    variant="body2"
                                    onClick={() => navigate(link.path)}
                                    sx={{
                                        color: 'text.secondary',
                                        textDecoration: 'none',
                                        textAlign: 'left',
                                        background: 'none',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: 0,
                                        fontSize: '0.95rem',
                                        fontWeight: 500,
                                        transition: 'all 0.3s ease',
                                        position: 'relative',
                                        '&:hover': {
                                            color: 'primary.main',
                                            transform: 'translateX(4px)',
                                        },
                                        '&::before': {
                                            content: '""',
                                            position: 'absolute',
                                            left: '-12px',
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            width: '4px',
                                            height: '4px',
                                            borderRadius: '50%',
                                            backgroundColor: 'primary.main',
                                            opacity: 0,
                                            transition: 'opacity 0.3s ease',
                                        },
                                        '&:hover::before': {
                                            opacity: 1,
                                        }
                                    }}
                                >
                                    {link.label}
                                    {link.label === 'Launch Panel' && (
                                        <Launch sx={{ fontSize: 14, ml: 0.5, opacity: 0.7 }} />
                                    )}
                                </Link>
                            ))}
                        </Stack>
                    </Grid>

                    {/* Contact Information */}
                    <Grid item xs={12} sm={6} md={3}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                fontSize: '1.1rem'
                            }}
                        >
                            Contact Info
                        </Typography>
                        <Stack spacing={2}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <LocationOn sx={{ fontSize: 18, color: 'primary.main' }} />
                                <Typography variant="body2" color="text.secondary">
                                    123 Research Drive<br />
                                    Science Park, CA 94025
                                </Typography>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Email sx={{ fontSize: 18, color: 'primary.main' }} />
                                <Link
                                    href="mailto:info@magellon.org"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        '&:hover': { color: 'primary.main' },
                                        transition: 'color 0.3s ease'
                                    }}
                                >
                                    info@magellon.org
                                </Link>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Phone sx={{ fontSize: 18, color: 'primary.main' }} />
                                <Link
                                    href="tel:+1-555-SCIENCE"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        '&:hover': { color: 'primary.main' },
                                        transition: 'color 0.3s ease'
                                    }}
                                >
                                    +1 (555) SCIENCE
                                </Link>
                            </Box>
                        </Stack>
                    </Grid>

                    {/* Connect & Resources */}
                    <Grid item xs={12} md={3}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                fontSize: '1.1rem'
                            }}
                        >
                            Connect & Learn
                        </Typography>

                        {/* Social Links */}
                        <Box sx={{ mb: 3 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Follow our research
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                {socialLinks.map((social, index) => (
                                    <IconButton
                                        key={index}
                                        href={social.href}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        aria-label={social.label}
                                        sx={{
                                            width: 44,
                                            height: 44,
                                            border: `2px solid ${alpha(theme.palette.primary.main, 0.3)}`,
                                            background: alpha(theme.palette.primary.main, 0.05),
                                            color: 'primary.main',
                                            transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                            '&:hover': {
                                                background: alpha(theme.palette.primary.main, 0.15),
                                                borderColor: alpha(theme.palette.primary.main, 0.6),
                                                transform: 'translateY(-2px) scale(1.05)',
                                                boxShadow: `0 8px 25px ${alpha(theme.palette.primary.main, 0.3)}`,
                                            }
                                        }}
                                    >
                                        {social.icon}
                                    </IconButton>
                                ))}
                            </Box>
                        </Box>

                        {/* Status Badge */}
                        <Box
                            sx={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 1,
                                px: 2,
                                py: 1,
                                borderRadius: 2,
                                backgroundColor: alpha('#10b981', 0.1),
                                border: `1px solid ${alpha('#10b981', 0.3)}`,
                            }}
                        >
                            <Box
                                sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    backgroundColor: '#10b981',
                                    animation: 'pulse 2s infinite',
                                    '@keyframes pulse': {
                                        '0%': { opacity: 1 },
                                        '50%': { opacity: 0.5 },
                                        '100%': { opacity: 1 },
                                    }
                                }}
                            />
                            <Typography variant="caption" sx={{ color: '#10b981', fontWeight: 600 }}>
                                All Systems Operational
                            </Typography>
                        </Box>
                    </Grid>
                </Grid>

                {/* Bottom Section */}
                <Box sx={{ mt: { xs: 4, md: 6 } }}>
                    <Divider sx={{
                        mb: 3,
                        borderColor: alpha(theme.palette.divider, 0.2),
                        background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.3)}, transparent)`
                    }} />

                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: { xs: 'column', sm: 'row' },
                            justifyContent: 'space-between',
                            alignItems: { xs: 'center', sm: 'center' },
                            gap: 2,
                            textAlign: { xs: 'center', sm: 'left' }
                        }}
                    >
                        <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ fontSize: '0.9rem' }}
                        >
                            © {new Date().getFullYear()} Magellon. All rights reserved. |{' '}
                            <Link
                                href="/privacy"
                                color="inherit"
                                sx={{
                                    textDecoration: 'none',
                                    '&:hover': { color: 'primary.main' },
                                    transition: 'color 0.3s ease'
                                }}
                            >
                                Privacy Policy
                            </Link>
                            {' '} | {' '}
                            <Link
                                href="/terms"
                                color="inherit"
                                sx={{
                                    textDecoration: 'none',
                                    '&:hover': { color: 'primary.main' },
                                    transition: 'color 0.3s ease'
                                }}
                            >
                                Terms of Service
                            </Link>
                        </Typography>

                        <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{
                                fontSize: '0.85rem',
                                fontStyle: 'italic',
                                opacity: 0.8
                            }}
                        >
                            Advancing structural biology through innovation
                        </Typography>
                    </Box>
                </Box>
            </Container>
        </Box>
    );
}