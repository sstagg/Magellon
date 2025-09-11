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
    Chip,
    Button
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
    Speed,
    ArrowUpward,
    Rocket
} from '@mui/icons-material';

export default function ModernFooter() {
    const theme = useTheme();

    const quickLinks = [
        { label: 'Home', path: '/en/web/home' },
        { label: 'About', path: '/en/web/about' },
        { label: 'Contact', path: '/en/web/contact' },
        { label: 'Launch Panel', path: '/en/panel/images', isAction: true },
    ];

    const features = [
        { label: 'CryoEM Analysis', icon: <Biotech sx={{ fontSize: 16 }} />, color: '#10b981' },
        { label: 'AI Processing', icon: <Speed sx={{ fontSize: 16 }} />, color: '#f59e0b' },
        { label: 'Secure Platform', icon: <Security sx={{ fontSize: 16 }} />, color: '#ef4444' },
        { label: 'Cloud Integration', icon: <CloudQueue sx={{ fontSize: 16 }} />, color: '#3b82f6' },
    ];

    const socialLinks = [
        { icon: <GitHub />, href: 'https://github.com/magellon', label: 'GitHub', color: '#24292e' },
        { icon: <Twitter />, href: 'https://twitter.com/magellon', label: 'Twitter', color: '#1da1f2' },
        { icon: <LinkedIn />, href: 'https://linkedin.com/company/magellon', label: 'LinkedIn', color: '#0077b5' },
    ];

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <Box
            component="footer"
            sx={{
                width: '100%',
                mt: 'auto',
                position: 'relative',
                overflow: 'hidden',
                background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(180deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)'
                    : 'linear-gradient(180deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%)',
                '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '1px',
                    background: 'linear-gradient(90deg, transparent, #67e8f9, #818cf8, #f59e0b, #10b981, transparent)',
                    opacity: 0.8,
                },
                '&::after': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: '-50%',
                    width: '200%',
                    height: '100%',
                    background: `radial-gradient(ellipse 800px 200px at 50% 0%, ${alpha('#67e8f9', 0.03)}, transparent)`,
                    pointerEvents: 'none',
                }
            }}
        >
            {/* Scroll to Top Button */}
            <Box
                sx={{
                    position: 'absolute',
                    top: -28,
                    right: { xs: 20, md: 40 },
                    zIndex: 2,
                }}
            >
                <IconButton
                    onClick={scrollToTop}
                    sx={{
                        width: 56,
                        height: 56,
                        background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                        color: 'white',
                        boxShadow: `0 8px 32px ${alpha(theme.palette.primary.main, 0.3)}`,
                        border: `3px solid ${theme.palette.background.paper}`,
                        transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                        '&:hover': {
                            transform: 'translateY(-4px) scale(1.05)',
                            boxShadow: `0 12px 40px ${alpha(theme.palette.primary.main, 0.4)}`,
                        }
                    }}
                >
                    <ArrowUpward />
                </IconButton>
            </Box>

            <Container maxWidth="xl" sx={{ py: { xs: 6, md: 8 }, position: 'relative', zIndex: 1 }}>
                <Grid container spacing={{ xs: 4, md: 6 }}>
                    {/* Enhanced Brand Section */}
                    <Grid item xs={12} lg={5}>
                        <Box sx={{ mb: 4 }}>
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    mb: 3,
                                    cursor: 'pointer',
                                    transition: 'all 0.3s ease-in-out',
                                    '&:hover': {
                                        transform: 'scale(1.02)',
                                    }
                                }}
                            >
                                <Box
                                    sx={{
                                        position: 'relative',
                                        mr: 2,
                                        '&::before': {
                                            content: '""',
                                            position: 'absolute',
                                            top: '50%',
                                            left: '50%',
                                            transform: 'translate(-50%, -50%)',
                                            width: 60,
                                            height: 60,
                                            background: `radial-gradient(circle, ${alpha('#67e8f9', 0.2)}, transparent 70%)`,
                                            borderRadius: '50%',
                                            animation: 'pulse 3s infinite',
                                        }
                                    }}
                                >
                                    <Science
                                        sx={{
                                            fontSize: 42,
                                            color: 'primary.main',
                                            filter: 'drop-shadow(0 0 20px rgba(103, 232, 249, 0.5))',
                                            position: 'relative',
                                            zIndex: 1,
                                        }}
                                    />
                                </Box>
                                <Box>
                                    <Typography
                                        variant="h3"
                                        sx={{
                                            fontWeight: 900,
                                            fontSize: { xs: '2rem', md: '2.5rem' },
                                            background: theme.palette.mode === 'dark'
                                                ? 'linear-gradient(135deg, #67e8f9 0%, #818cf8 50%, #a855f7 100%)'
                                                : 'linear-gradient(135deg, #0891b2 0%, #6366f1 50%, #8b5cf6 100%)',
                                            backgroundClip: 'text',
                                            WebkitBackgroundClip: 'text',
                                            WebkitTextFillColor: 'transparent',
                                            letterSpacing: '-1px',
                                            mb: 0.5,
                                        }}
                                    >
                                        Magellon
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: 'primary.main',
                                            fontWeight: 600,
                                            letterSpacing: '2px',
                                            textTransform: 'uppercase',
                                            opacity: 0.8,
                                        }}
                                    >
                                        Structural Biology AI
                                    </Typography>
                                </Box>
                            </Box>

                            <Typography
                                variant="h6"
                                color="text.primary"
                                sx={{
                                    mb: 2,
                                    fontWeight: 600,
                                    lineHeight: 1.4,
                                }}
                            >
                                Revolutionizing molecular discovery
                            </Typography>

                            <Typography
                                variant="body1"
                                color="text.secondary"
                                sx={{
                                    mb: 4,
                                    lineHeight: 1.8,
                                    fontSize: '1.1rem',
                                }}
                            >
                                Empowering researchers worldwide with AI-powered CryoEM analysis to unlock the secrets of life at the molecular level.
                            </Typography>

                            {/* Enhanced Feature Pills */}
                            <Box sx={{ mb: 4 }}>
                                <Typography
                                    variant="subtitle2"
                                    color="text.secondary"
                                    sx={{ mb: 2, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1px' }}
                                >
                                    Our Capabilities
                                </Typography>
                                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                                    {features.map((feature, index) => (
                                        <Chip
                                            key={index}
                                            icon={React.cloneElement(feature.icon, { sx: { color: feature.color + ' !important' } })}
                                            label={feature.label}
                                            size="medium"
                                            variant="outlined"
                                            sx={{
                                                borderColor: alpha(feature.color, 0.3),
                                                backgroundColor: alpha(feature.color, 0.05),
                                                color: 'text.primary',
                                                fontWeight: 600,
                                                px: 1,
                                                '&:hover': {
                                                    backgroundColor: alpha(feature.color, 0.1),
                                                    borderColor: alpha(feature.color, 0.5),
                                                    transform: 'translateY(-2px)',
                                                    boxShadow: `0 4px 12px ${alpha(feature.color, 0.2)}`,
                                                },
                                                transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                            }}
                                        />
                                    ))}
                                </Stack>
                            </Box>

                            {/* CTA Button */}
                            <Button
                                variant="contained"
                                size="large"
                                startIcon={<Rocket />}
                                sx={{
                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                    borderRadius: 3,
                                    px: 4,
                                    py: 1.5,
                                    fontWeight: 700,
                                    textTransform: 'none',
                                    boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
                                    transition: 'all 0.3s ease',
                                    '&:hover': {
                                        transform: 'translateY(-2px)',
                                        boxShadow: '0 12px 40px rgba(102, 126, 234, 0.4)',
                                    }
                                }}
                            >
                                Start Your Analysis
                            </Button>
                        </Box>
                    </Grid>

                    {/* Quick Links */}
                    <Grid item xs={12} sm={6} lg={2}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                position: 'relative',
                                '&::after': {
                                    content: '""',
                                    position: 'absolute',
                                    bottom: -8,
                                    left: 0,
                                    width: 24,
                                    height: 3,
                                    background: 'linear-gradient(90deg, #67e8f9, #818cf8)',
                                    borderRadius: 2,
                                }
                            }}
                        >
                            Navigation
                        </Typography>
                        <Stack spacing={2}>
                            {quickLinks.map((link, index) => (
                                <Box key={index} sx={{ position: 'relative' }}>
                                    <Link
                                        component="button"
                                        variant="body1"
                                        sx={{
                                            color: link.isAction ? 'primary.main' : 'text.secondary',
                                            textDecoration: 'none',
                                            textAlign: 'left',
                                            background: 'none',
                                            border: 'none',
                                            cursor: 'pointer',
                                            padding: '8px 0',
                                            fontSize: '1rem',
                                            fontWeight: link.isAction ? 600 : 500,
                                            transition: 'all 0.3s ease',
                                            position: 'relative',
                                            display: 'flex',
                                            alignItems: 'center',
                                            '&:hover': {
                                                color: 'primary.main',
                                                transform: 'translateX(8px)',
                                            }
                                        }}
                                    >
                                        {link.label}
                                        {link.isAction && (
                                            <Launch sx={{ fontSize: 16, ml: 1, opacity: 0.8 }} />
                                        )}
                                    </Link>
                                </Box>
                            ))}
                        </Stack>
                    </Grid>

                    {/* Contact Information */}
                    <Grid item xs={12} sm={6} lg={2.5}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                position: 'relative',
                                '&::after': {
                                    content: '""',
                                    position: 'absolute',
                                    bottom: -8,
                                    left: 0,
                                    width: 24,
                                    height: 3,
                                    background: 'linear-gradient(90deg, #f59e0b, #10b981)',
                                    borderRadius: 2,
                                }
                            }}
                        >
                            Get In Touch
                        </Typography>
                        <Stack spacing={3}>
                            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                                <Box
                                    sx={{
                                        p: 1,
                                        borderRadius: 2,
                                        background: alpha('#67e8f9', 0.1),
                                        border: `1px solid ${alpha('#67e8f9', 0.2)}`,
                                        mt: 0.5,
                                    }}
                                >
                                    <LocationOn sx={{ fontSize: 18, color: '#67e8f9' }} />
                                </Box>
                                <Box>
                                    <Typography variant="body2" color="text.primary" fontWeight={600}>
                                        Headquarters
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        123 Research Drive<br />
                                        Science Park, CA 94025
                                    </Typography>
                                </Box>
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box
                                    sx={{
                                        p: 1,
                                        borderRadius: 2,
                                        background: alpha('#10b981', 0.1),
                                        border: `1px solid ${alpha('#10b981', 0.2)}`,
                                    }}
                                >
                                    <Email sx={{ fontSize: 18, color: '#10b981' }} />
                                </Box>
                                <Link
                                    href="mailto:info@magellon.org"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        fontWeight: 500,
                                        '&:hover': {
                                            color: '#10b981',
                                            textDecoration: 'underline',
                                        },
                                        transition: 'all 0.3s ease'
                                    }}
                                >
                                    info@magellon.org
                                </Link>
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box
                                    sx={{
                                        p: 1,
                                        borderRadius: 2,
                                        background: alpha('#f59e0b', 0.1),
                                        border: `1px solid ${alpha('#f59e0b', 0.2)}`,
                                    }}
                                >
                                    <Phone sx={{ fontSize: 18, color: '#f59e0b' }} />
                                </Box>
                                <Link
                                    href="tel:+1-555-SCIENCE"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        fontWeight: 500,
                                        '&:hover': {
                                            color: '#f59e0b',
                                            textDecoration: 'underline',
                                        },
                                        transition: 'all 0.3s ease'
                                    }}
                                >
                                    +1 (555) SCIENCE
                                </Link>
                            </Box>
                        </Stack>
                    </Grid>

                    {/* Social & Status */}
                    <Grid item xs={12} lg={2.5}>
                        <Typography
                            variant="h6"
                            sx={{
                                fontWeight: 700,
                                mb: 3,
                                color: 'text.primary',
                                position: 'relative',
                                '&::after': {
                                    content: '""',
                                    position: 'absolute',
                                    bottom: -8,
                                    left: 0,
                                    width: 24,
                                    height: 3,
                                    background: 'linear-gradient(90deg, #818cf8, #a855f7)',
                                    borderRadius: 2,
                                }
                            }}
                        >
                            Stay Connected
                        </Typography>

                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3, fontWeight: 500 }}>
                            Follow our latest research breakthroughs
                        </Typography>

                        {/* Enhanced Social Links */}
                        <Box sx={{ display: 'flex', gap: 2, mb: 4 }}>
                            {socialLinks.map((social, index) => (
                                <IconButton
                                    key={index}
                                    href={social.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    aria-label={social.label}
                                    sx={{
                                        width: 48,
                                        height: 48,
                                        borderRadius: 3,
                                        background: `linear-gradient(135deg, ${alpha(social.color, 0.1)}, ${alpha(social.color, 0.05)})`,
                                        border: `2px solid ${alpha(social.color, 0.2)}`,
                                        color: social.color,
                                        transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                        '&:hover': {
                                            background: alpha(social.color, 0.1),
                                            borderColor: alpha(social.color, 0.4),
                                            transform: 'translateY(-4px) rotate(5deg)',
                                            boxShadow: `0 8px 25px ${alpha(social.color, 0.3)}`,
                                        }
                                    }}
                                >
                                    {social.icon}
                                </IconButton>
                            ))}
                        </Box>

                        {/* Enhanced Status Badge */}
                        <Box
                            sx={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 1.5,
                                px: 3,
                                py: 2,
                                borderRadius: 3,
                                background: `linear-gradient(135deg, ${alpha('#10b981', 0.1)}, ${alpha('#059669', 0.05)})`,
                                border: `2px solid ${alpha('#10b981', 0.3)}`,
                                backdropFilter: 'blur(10px)',
                            }}
                        >
                            <Box
                                sx={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: '50%',
                                    background: 'linear-gradient(45deg, #10b981, #059669)',
                                    boxShadow: '0 0 10px rgba(16, 185, 129, 0.5)',
                                    animation: 'pulse 2s infinite',
                                    '@keyframes pulse': {
                                        '0%': {
                                            transform: 'scale(1)',
                                            opacity: 1
                                        },
                                        '50%': {
                                            transform: 'scale(1.2)',
                                            opacity: 0.7
                                        },
                                        '100%': {
                                            transform: 'scale(1)',
                                            opacity: 1
                                        },
                                    }
                                }}
                            />
                            <Typography variant="body2" sx={{
                                color: '#10b981',
                                fontWeight: 700,
                                fontSize: '0.9rem'
                            }}>
                                All Systems Online
                            </Typography>
                        </Box>
                    </Grid>
                </Grid>

                {/* Enhanced Bottom Section */}
                <Box sx={{ mt: { xs: 6, md: 8 } }}>
                    <Divider sx={{
                        mb: 4,
                        border: 'none',
                        height: '2px',
                        background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.3)}, ${alpha(theme.palette.secondary.main, 0.3)}, transparent)`,
                        borderRadius: 1,
                    }} />

                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: { xs: 'column', md: 'row' },
                            justifyContent: 'space-between',
                            alignItems: { xs: 'center', md: 'center' },
                            gap: 3,
                            textAlign: { xs: 'center', md: 'left' }
                        }}
                    >
                        <Box>
                            <Typography
                                variant="body1"
                                color="text.secondary"
                                sx={{ fontWeight: 500, mb: 0.5 }}
                            >
                                © {new Date().getFullYear()} Magellon. All rights reserved.
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 2, justifyContent: { xs: 'center', md: 'flex-start' } }}>
                                <Link
                                    href="/privacy"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        fontSize: '0.9rem',
                                        '&:hover': {
                                            color: 'primary.main',
                                            textDecoration: 'underline'
                                        },
                                        transition: 'color 0.3s ease'
                                    }}
                                >
                                    Privacy Policy
                                </Link>
                                <Typography color="text.secondary">•</Typography>
                                <Link
                                    href="/terms"
                                    color="text.secondary"
                                    sx={{
                                        textDecoration: 'none',
                                        fontSize: '0.9rem',
                                        '&:hover': {
                                            color: 'primary.main',
                                            textDecoration: 'underline'
                                        },
                                        transition: 'color 0.3s ease'
                                    }}
                                >
                                    Terms of Service
                                </Link>
                            </Box>
                        </Box>

                        <Typography
                            variant="h6"
                            sx={{
                                fontSize: '1.1rem',
                                fontWeight: 600,
                                background: 'linear-gradient(45deg, #667eea, #764ba2)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                letterSpacing: '0.5px',
                            }}
                        >
                            Advancing structural biology through innovation ✨
                        </Typography>
                    </Box>
                </Box>
            </Container>

            <style jsx>{`
                @keyframes pulse {
                    0%, 100% { transform: scale(1); opacity: 1; }
                    50% { transform: scale(1.05); opacity: 0.8; }
                }
            `}</style>
        </Box>
    );
}