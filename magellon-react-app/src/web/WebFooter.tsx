import React from "react";
import {
    Container,
    Typography,
    Link,
    Grid,
    Box,
    IconButton,
    Divider,
    alpha,
    useTheme,
    Chip,
} from "@mui/material";
import {
    Science,
    Facebook,
    Twitter,
    LinkedIn,
    GitHub,
    Email,
    Phone,
    LocationOn,
    ArrowUpward,
} from "@mui/icons-material";

export default function WebFooter() {
    const theme = useTheme();

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const footerLinks = {
        platform: [
            { label: "CryoEM Analysis", href: "#" },
            { label: "Data Processing", href: "#" },
            { label: "3D Reconstruction", href: "#" },
            { label: "AI Insights", href: "#" },
        ],
        company: [
            { label: "About Us", href: "/en/web/about" },
            { label: "Careers", href: "#" },
            { label: "News", href: "#" },
            { label: "Partners", href: "#" },
        ],
        resources: [
            { label: "Documentation", href: "#" },
            { label: "API Reference", href: "#" },
            { label: "Tutorials", href: "#" },
            { label: "Support", href: "#" },
        ],
        legal: [
            { label: "Privacy Policy", href: "#" },
            { label: "Terms of Service", href: "#" },
            { label: "Security", href: "#" },
            { label: "Compliance", href: "#" },
        ],
    };

    const socialLinks = [
        { icon: <LinkedIn />, href: "https://linkedin.com", label: "LinkedIn" },
        { icon: <Twitter />, href: "https://twitter.com", label: "Twitter" },
        { icon: <GitHub />, href: "https://github.com", label: "GitHub" },
        { icon: <Facebook />, href: "https://facebook.com", label: "Facebook" },
    ];

    return (
        <Box
            component="footer"
            sx={{
                background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)'
                    : 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)',
                borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            {/* Background Pattern */}
            <Box
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    opacity: 0.03,
                    backgroundImage: theme.palette.mode === 'dark'
                        ? 'radial-gradient(circle at 25% 25%, #67e8f9 0%, transparent 50%), radial-gradient(circle at 75% 75%, #818cf8 0%, transparent 50%)'
                        : 'radial-gradient(circle at 25% 25%, #0891b2 0%, transparent 50%), radial-gradient(circle at 75% 75%, #6366f1 0%, transparent 50%)',
                }}
            />

            <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
                {/* Main Footer Content */}
                <Box sx={{ py: 6 }}>
                    <Grid container spacing={4}>
                        {/* Brand Section */}
                        <Grid item xs={12} md={4}>
                            <Box sx={{ mb: 3 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <Science
                                        sx={{
                                            mr: 1,
                                            fontSize: 32,
                                            color: 'primary.main',
                                            filter: 'drop-shadow(0 0 8px rgba(103, 232, 249, 0.3))'
                                        }}
                                    />
                                    <Typography
                                        variant="h5"
                                        sx={{
                                            fontWeight: 700,
                                            background: theme.palette.mode === 'dark'
                                                ? 'linear-gradient(45deg, #67e8f9, #818cf8)'
                                                : 'linear-gradient(45deg, #0891b2, #6366f1)',
                                            backgroundClip: 'text',
                                            WebkitBackgroundClip: 'text',
                                            WebkitTextFillColor: 'transparent',
                                        }}
                                    >
                                        Magellon
                                    </Typography>
                                </Box>
                                <Typography variant="body1" color="text.secondary" sx={{ mb: 3, lineHeight: 1.7 }}>
                                    Pioneering the future of structural biology with AI-powered CryoEM analysis.
                                    Trusted by leading research institutions worldwide.
                                </Typography>
                                <Chip
                                    label="Next-Gen Platform"
                                    size="small"
                                    sx={{
                                        background: alpha(theme.palette.primary.main, 0.1),
                                        color: 'primary.main',
                                        fontWeight: 600,
                                    }}
                                />
                            </Box>

                            {/* Contact Info */}
                            <Box sx={{ mb: 3 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                    <Email sx={{ fontSize: 18, mr: 1, color: 'text.secondary' }} />
                                    <Typography variant="body2" color="text.secondary">
                                        research@magellon.org
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                    <Phone sx={{ fontSize: 18, mr: 1, color: 'text.secondary' }} />
                                    <Typography variant="body2" color="text.secondary">
                                        +1 (555) 123-4567
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                    <LocationOn sx={{ fontSize: 18, mr: 1, color: 'text.secondary' }} />
                                    <Typography variant="body2" color="text.secondary">
                                        San Francisco, CA
                                    </Typography>
                                </Box>
                            </Box>
                        </Grid>

                        {/* Links Sections */}
                        <Grid item xs={6} md={2}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>
                                Platform
                            </Typography>
                            {footerLinks.platform.map((link, index) => (
                                <Link
                                    key={index}
                                    href={link.href}
                                    color="text.secondary"
                                    sx={{
                                        display: 'block',
                                        mb: 1,
                                        textDecoration: 'none',
                                        transition: 'all 0.2s ease-in-out',
                                        '&:hover': {
                                            color: 'primary.main',
                                            transform: 'translateX(4px)',
                                        }
                                    }}
                                >
                                    {link.label}
                                </Link>
                            ))}
                        </Grid>

                        <Grid item xs={6} md={2}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>
                                Company
                            </Typography>
                            {footerLinks.company.map((link, index) => (
                                <Link
                                    key={index}
                                    href={link.href}
                                    color="text.secondary"
                                    sx={{
                                        display: 'block',
                                        mb: 1,
                                        textDecoration: 'none',
                                        transition: 'all 0.2s ease-in-out',
                                        '&:hover': {
                                            color: 'primary.main',
                                            transform: 'translateX(4px)',
                                        }
                                    }}
                                >
                                    {link.label}
                                </Link>
                            ))}
                        </Grid>

                        <Grid item xs={6} md={2}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>
                                Resources
                            </Typography>
                            {footerLinks.resources.map((link, index) => (
                                <Link
                                    key={index}
                                    href={link.href}
                                    color="text.secondary"
                                    sx={{
                                        display: 'block',
                                        mb: 1,
                                        textDecoration: 'none',
                                        transition: 'all 0.2s ease-in-out',
                                        '&:hover': {
                                            color: 'primary.main',
                                            transform: 'translateX(4px)',
                                        }
                                    }}
                                >
                                    {link.label}
                                </Link>
                            ))}
                        </Grid>

                        <Grid item xs={6} md={2}>
                            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, color: 'text.primary' }}>
                                Legal
                            </Typography>
                            {footerLinks.legal.map((link, index) => (
                                <Link
                                    key={index}
                                    href={link.href}
                                    color="text.secondary"
                                    sx={{
                                        display: 'block',
                                        mb: 1,
                                        textDecoration: 'none',
                                        transition: 'all 0.2s ease-in-out',
                                        '&:hover': {
                                            color: 'primary.main',
                                            transform: 'translateX(4px)',
                                        }
                                    }}
                                >
                                    {link.label}
                                </Link>
                            ))}
                        </Grid>
                    </Grid>
                </Box>

                <Divider sx={{ opacity: 0.1 }} />

                {/* Bottom Footer */}
                <Box
                    sx={{
                        py: 3,
                        display: 'flex',
                        flexDirection: { xs: 'column', sm: 'row' },
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 2,
                    }}
                >
                    <Typography variant="body2" color="text.secondary">
                        © {new Date().getFullYear()} Magellon. All rights reserved. Revolutionizing structural biology.
                    </Typography>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {/* Social Links */}
                        <Box sx={{ display: 'flex', gap: 1, mr: 2 }}>
                            {socialLinks.map((social, index) => (
                                <IconButton
                                    key={index}
                                    href={social.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    size="small"
                                    sx={{
                                        color: 'text.secondary',
                                        border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                                        transition: 'all 0.2s ease-in-out',
                                        '&:hover': {
                                            color: 'primary.main',
                                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                            transform: 'translateY(-2px)',
                                        }
                                    }}
                                >
                                    {social.icon}
                                </IconButton>
                            ))}
                        </Box>

                        {/* Back to Top */}
                        <IconButton
                            onClick={scrollToTop}
                            size="small"
                            sx={{
                                color: 'text.secondary',
                                border: `1px solid ${alpha(theme.palette.primary.main, 0.3)}`,
                                background: alpha(theme.palette.primary.main, 0.05),
                                transition: 'all 0.2s ease-in-out',
                                '&:hover': {
                                    color: 'primary.main',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                    transform: 'translateY(-2px)',
                                }
                            }}
                        >
                            <ArrowUpward fontSize="small" />
                        </IconButton>
                    </Box>
                </Box>
            </Container>
        </Box>
    );
}