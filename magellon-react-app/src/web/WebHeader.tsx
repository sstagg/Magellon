import React, { useState } from 'react';
import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    IconButton,
    Box,
    Menu,
    MenuItem,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Menu as MenuIcon,
    DarkMode,
    LightMode,
    Dashboard,
    Info,
    ContactMail,
    Home as HomeIcon
} from '@mui/icons-material';
import { useNavigate } from "react-router-dom";
import { useThemeContext } from '../themes';
import magellanLogo from '../assets/images/magellon-logo.svg';

export default function WebHeader() {
    const navigate = useNavigate();
    const theme = useTheme();
    const { themeName, toggleTheme } = useThemeContext();
    const [mobileMenuAnchor, setMobileMenuAnchor] = useState<null | HTMLElement>(null);

    const handleMobileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setMobileMenuAnchor(event.currentTarget);
    };

    const handleMobileMenuClose = () => {
        setMobileMenuAnchor(null);
    };

    const navItems = [
        { label: 'Home', path: '/en/web/home', icon: <HomeIcon /> },
        { label: 'About', path: '/en/web/about', icon: <Info /> },
        { label: 'Contact', path: '/en/web/contact', icon: <ContactMail /> },
    ];

    return (
        <AppBar
            position="fixed"
            elevation={0}
            sx={{
                backgroundColor: theme.palette.mode === 'dark'
                    ? alpha('#0f172a', 0.95)
                    : alpha('#ffffff', 0.95),
                backdropFilter: 'blur(20px)',
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                boxShadow: theme.palette.mode === 'dark'
                    ? '0 2px 8px rgba(0, 0, 0, 0.2)'
                    : '0 2px 8px rgba(0, 0, 0, 0.05)',
            }}
        >
                <Toolbar sx={{ px: { xs: 2, sm: 4 }, minHeight: '72px !important' }}>
                    {/* Logo with Tagline */}
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            '&:hover': {
                                opacity: 0.85,
                            }
                        }}
                        onClick={() => navigate('/en/web/home')}
                    >
                        <Box
                            component="img"
                            src={magellanLogo}
                            alt="Magellon Logo"
                            sx={{
                                height: 42,
                                width: 42,
                                mr: 1.5,
                            }}
                        />
                        <Box>
                            <Typography
                                variant="h6"
                                component="div"
                                sx={{
                                    fontWeight: 700,
                                    fontSize: '1.4rem',
                                    color: 'text.primary',
                                    fontFamily: 'Exo 2, sans-serif',
                                    letterSpacing: '-0.3px',
                                    lineHeight: 1.2,
                                }}
                            >
                                Magellon
                            </Typography>
                            <Typography
                                variant="caption"
                                sx={{
                                    color: 'text.secondary',
                                    fontSize: '0.7rem',
                                    fontWeight: 500,
                                    letterSpacing: '0.8px',
                                    textTransform: 'uppercase',
                                    display: { xs: 'none', sm: 'block' }
                                }}
                            >
                                CryoEM Data Platform
                            </Typography>
                        </Box>
                    </Box>

                    <Box sx={{ flexGrow: 1 }} />

                    {/* Desktop Navigation */}
                    <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5 }}>
                        {navItems.map((item) => (
                            <Button
                                key={item.label}
                                onClick={() => navigate(item.path)}
                                sx={{
                                    px: 2.5,
                                    py: 1,
                                    textTransform: 'none',
                                    fontWeight: 500,
                                    fontSize: '0.95rem',
                                    color: 'text.secondary',
                                    transition: 'all 0.2s ease',
                                    '&:hover': {
                                        color: 'primary.main',
                                        backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                    }
                                }}
                            >
                                {item.label}
                            </Button>
                        ))}

                        {/* Divider */}
                        <Box sx={{
                            width: '1px',
                            height: '24px',
                            backgroundColor: alpha(theme.palette.divider, 0.2),
                            mx: 2
                        }} />

                        {/* Theme Toggle */}
                        <IconButton
                            onClick={toggleTheme}
                            size="small"
                            sx={{
                                color: 'text.secondary',
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    color: 'primary.main',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                }
                            }}
                        >
                            {themeName === 'dark' ? <LightMode fontSize="small" /> : <DarkMode fontSize="small" />}
                        </IconButton>

                        {/* Panel Access */}
                        <Button
                            variant="contained"
                            startIcon={<Dashboard />}
                            onClick={() => navigate("/en/panel")}
                            sx={{
                                ml: 2,
                                px: 3,
                                py: 1,
                                textTransform: 'none',
                                fontWeight: 600,
                                fontSize: '0.95rem',
                                backgroundColor: 'primary.main',
                                color: '#ffffff',
                                boxShadow: 'none',
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    backgroundColor: 'primary.dark',
                                    boxShadow: 'none',
                                }
                            }}
                        >
                            Access Platform
                        </Button>
                    </Box>

                    {/* Mobile Menu Button */}
                    <Box sx={{ display: { xs: 'flex', md: 'none' }, gap: 1 }}>
                        <IconButton
                            onClick={toggleTheme}
                            size="small"
                            sx={{
                                color: 'text.secondary',
                                '&:hover': {
                                    color: 'primary.main',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                }
                            }}
                        >
                            {themeName === 'dark' ? <LightMode fontSize="small" /> : <DarkMode fontSize="small" />}
                        </IconButton>
                        <IconButton
                            onClick={handleMobileMenuOpen}
                            sx={{
                                color: 'text.secondary',
                                '&:hover': {
                                    color: 'primary.main',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                }
                            }}
                        >
                            <MenuIcon />
                        </IconButton>
                    </Box>

                    {/* Mobile Menu */}
                    <Menu
                        anchorEl={mobileMenuAnchor}
                        open={Boolean(mobileMenuAnchor)}
                        onClose={handleMobileMenuClose}
                        PaperProps={{
                            sx: {
                                mt: 1,
                                minWidth: 200,
                                borderRadius: 3,
                                backdropFilter: 'blur(20px)',
                                background: alpha(theme.palette.background.paper, 0.95),
                                border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
                            }
                        }}
                    >
                        {navItems.map((item) => (
                            <MenuItem
                                key={item.label}
                                onClick={() => {
                                    navigate(item.path);
                                    handleMobileMenuClose();
                                }}
                                sx={{
                                    py: 1.5,
                                    borderRadius: 2,
                                    mx: 1,
                                    my: 0.5,
                                    transition: 'all 0.2s ease',
                                    '&:hover': {
                                        background: alpha(theme.palette.primary.main, 0.1),
                                        color: 'primary.main',
                                    }
                                }}
                            >
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    {item.icon}
                                    <Typography fontWeight={500}>{item.label}</Typography>
                                </Box>
                            </MenuItem>
                        ))}
                        <MenuItem
                            onClick={() => {
                                navigate("/en/panel");
                                handleMobileMenuClose();
                            }}
                            sx={{
                                py: 1.5,
                                borderRadius: 2,
                                mx: 1,
                                my: 0.5,
                                mt: 1,
                                background: alpha(theme.palette.primary.main, 0.1),
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    background: alpha(theme.palette.primary.main, 0.2),
                                }
                            }}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Dashboard />
                                <Typography fontWeight={600} color="primary.main">Access Platform</Typography>
                            </Box>
                        </MenuItem>
                    </Menu>
                </Toolbar>
        </AppBar>
    );
}