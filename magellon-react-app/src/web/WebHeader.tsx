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
    useScrollTrigger,
    Slide,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Menu as MenuIcon,
    DarkMode,
    LightMode,
    Science,
    Dashboard,
    Info,
    ContactMail,
    Home as HomeIcon
} from '@mui/icons-material';
import { useNavigate } from "react-router-dom";
import { useThemeContext } from '../themes';

interface Props {
    children: React.ReactElement;
}

function HideOnScroll(props: Props) {
    const { children } = props;
    const trigger = useScrollTrigger();

    return (
        <Slide appear={false} direction="down" in={!trigger}>
            {children}
        </Slide>
    );
}

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
        <HideOnScroll>
            <AppBar
                position="fixed"
                elevation={0}
                sx={{
                    background: theme.palette.mode === 'dark'
                        ? `linear-gradient(135deg, ${alpha('#0a1929', 0.98)} 0%, ${alpha('#1e293b', 0.98)} 100%)`
                        : `linear-gradient(135deg, ${alpha('#ffffff', 0.98)} 0%, ${alpha('#f8fafc', 0.98)} 100%)`,
                    backdropFilter: 'blur(24px)',
                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.12)}`,
                    boxShadow: theme.palette.mode === 'dark'
                        ? '0 4px 20px rgba(0, 0, 0, 0.25)'
                        : '0 4px 20px rgba(0, 0, 0, 0.08)',
                }}
            >
                <Toolbar sx={{ px: { xs: 2, sm: 4 }, minHeight: '70px !important' }}>
                    {/* Logo */}
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            cursor: 'pointer',
                            transition: 'all 0.3s ease-in-out',
                            '&:hover': {
                                transform: 'scale(1.05)',
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
                            component="div"
                            sx={{
                                fontWeight: 800,
                                fontSize: '1.8rem',
                                background: theme.palette.mode === 'dark'
                                    ? 'linear-gradient(45deg, #67e8f9, #818cf8)'
                                    : 'linear-gradient(45deg, #0891b2, #6366f1)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                textShadow: '0 0 20px rgba(103, 232, 249, 0.3)',
                                letterSpacing: '-0.5px'
                            }}
                        >
                            Magellon
                        </Typography>
                    </Box>

                    <Box sx={{ flexGrow: 1 }} />

                    {/* Desktop Navigation */}
                    <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1 }}>
                        {navItems.map((item) => (
                            <Button
                                key={item.label}
                                startIcon={item.icon}
                                onClick={() => navigate(item.path)}
                                sx={{
                                    borderRadius: 3,
                                    px: 3,
                                    py: 1.2,
                                    textTransform: 'none',
                                    fontWeight: 600,
                                    fontSize: '1rem',
                                    color: theme.palette.mode === 'dark'
                                        ? 'rgba(255, 255, 255, 0.9)'
                                        : 'rgba(15, 23, 42, 0.9)',
                                    border: theme.palette.mode === 'dark'
                                        ? `1px solid ${alpha('#67e8f9', 0.2)}`
                                        : `1px solid ${alpha('#0891b2', 0.2)}`,
                                    background: theme.palette.mode === 'dark'
                                        ? alpha('#67e8f9', 0.05)
                                        : alpha('#0891b2', 0.05),
                                    transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                    '&:hover': {
                                        background: theme.palette.mode === 'dark'
                                            ? 'linear-gradient(135deg, rgba(103, 232, 249, 0.15), rgba(129, 140, 248, 0.15))'
                                            : 'linear-gradient(135deg, rgba(8, 145, 178, 0.15), rgba(99, 102, 241, 0.15))',
                                        borderColor: theme.palette.mode === 'dark'
                                            ? alpha('#67e8f9', 0.4)
                                            : alpha('#0891b2', 0.4),
                                        color: theme.palette.mode === 'dark'
                                            ? '#67e8f9'
                                            : '#0891b2',
                                        transform: 'translateY(-2px)',
                                        boxShadow: theme.palette.mode === 'dark'
                                            ? '0 8px 25px rgba(103, 232, 249, 0.2)'
                                            : '0 8px 25px rgba(8, 145, 178, 0.2)',
                                    }
                                }}
                            >
                                {item.label}
                            </Button>
                        ))}

                        {/* Theme Toggle */}
                        <IconButton
                            onClick={toggleTheme}
                            sx={{
                                ml: 2,
                                width: 48,
                                height: 48,
                                border: `2px solid ${alpha(theme.palette.primary.main, 0.3)}`,
                                background: alpha(theme.palette.primary.main, 0.1),
                                color: 'primary.main',
                                transition: 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                '&:hover': {
                                    background: alpha(theme.palette.primary.main, 0.2),
                                    transform: 'rotate(180deg) scale(1.1)',
                                    borderColor: alpha(theme.palette.primary.main, 0.6),
                                    boxShadow: `0 8px 25px ${alpha(theme.palette.primary.main, 0.3)}`,
                                }
                            }}
                        >
                            {themeName === 'dark' ? <LightMode /> : <DarkMode />}
                        </IconButton>

                        {/* Panel Access - Modern Design */}
                        <Button
                            variant="contained"
                            startIcon={<Dashboard />}
                            onClick={() => navigate("/en/panel")}
                            sx={{
                                ml: 2,
                                borderRadius: 3,
                                px: 4,
                                py: 1.5,
                                textTransform: 'none',
                                fontWeight: 700,
                                fontSize: '1rem',
                                position: 'relative',
                                overflow: 'hidden',
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                color: '#ffffff',
                                border: 'none',
                                boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
                                transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                                '&::before': {
                                    content: '""',
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                                    opacity: 0,
                                    transition: 'opacity 0.3s ease',
                                },
                                '&:hover': {
                                    transform: 'translateY(-3px) scale(1.02)',
                                    boxShadow: '0 12px 40px rgba(102, 126, 234, 0.4)',
                                    '&::before': {
                                        opacity: 1,
                                    }
                                },
                                '& .MuiButton-startIcon': {
                                    position: 'relative',
                                    zIndex: 1,
                                },
                                '& span': {
                                    position: 'relative',
                                    zIndex: 1,
                                }
                            }}
                        >
                            Launch Panel
                        </Button>
                    </Box>

                    {/* Mobile Menu Button */}
                    <Box sx={{ display: { xs: 'flex', md: 'none' } }}>
                        <IconButton
                            onClick={handleMobileMenuOpen}
                            sx={{
                                width: 48,
                                height: 48,
                                border: `2px solid ${alpha(theme.palette.primary.main, 0.3)}`,
                                background: alpha(theme.palette.primary.main, 0.1),
                                color: 'primary.main',
                                transition: 'all 0.3s ease',
                                '&:hover': {
                                    background: alpha(theme.palette.primary.main, 0.2),
                                    transform: 'scale(1.1)',
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
                                background: alpha(theme.palette.primary.main, 0.1),
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    background: alpha(theme.palette.primary.main, 0.2),
                                }
                            }}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Dashboard />
                                <Typography fontWeight={600} color="primary.main">Launch Panel</Typography>
                            </Box>
                        </MenuItem>
                        <MenuItem
                            onClick={() => {
                                toggleTheme();
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
                                }
                            }}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                {themeName === 'dark' ? <LightMode /> : <DarkMode />}
                                <Typography fontWeight={500}>
                                    {themeName === 'dark' ? 'Light Mode' : 'Dark Mode'}
                                </Typography>
                            </Box>
                        </MenuItem>
                    </Menu>
                </Toolbar>
            </AppBar>
        </HideOnScroll>
    );
}