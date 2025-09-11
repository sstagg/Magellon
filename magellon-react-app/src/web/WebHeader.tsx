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
    Chip,
} from '@mui/material';
import {
    Menu as MenuIcon,
    DarkMode,
    LightMode,
    Science,
    Dashboard,
    Info,
    ContactMail
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
    const { themeName, toggleTheme } = useThemeContext();
    const [mobileMenuAnchor, setMobileMenuAnchor] = useState<null | HTMLElement>(null);

    const handleMobileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setMobileMenuAnchor(event.currentTarget);
    };

    const handleMobileMenuClose = () => {
        setMobileMenuAnchor(null);
    };

    const navItems = [
        { label: 'Home', path: '/en/web/home', icon: <Science /> },
        { label: 'About', path: '/en/web/about', icon: <Info /> },
        { label: 'Contact', path: '/en/web/contact', icon: <ContactMail /> },
    ];

    return (
        <HideOnScroll>
            <AppBar
                position="fixed"
                elevation={0}
                sx={{
                    background: (theme) => theme.palette.mode === 'dark'
                        ? `linear-gradient(90deg, ${alpha('#0a1929', 0.95)} 0%, ${alpha('#1e293b', 0.95)} 100%)`
                        : `linear-gradient(90deg, ${alpha('#ffffff', 0.95)} 0%, ${alpha('#f8fafc', 0.95)} 100%)`,
                    backdropFilter: 'blur(20px)',
                    borderBottom: (theme) => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
            >
                <Toolbar sx={{ px: { xs: 2, sm: 4 } }}>
                    {/* Logo */}
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            cursor: 'pointer',
                            '&:hover': {
                                transform: 'scale(1.05)',
                                transition: 'transform 0.2s ease-in-out'
                            }
                        }}
                        onClick={() => navigate('/en/web/home')}
                    >
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
                            component="div"
                            sx={{
                                fontWeight: 700,
                                background: (theme) => theme.palette.mode === 'dark'
                                    ? 'linear-gradient(45deg, #67e8f9, #818cf8)'
                                    : 'linear-gradient(45deg, #0891b2, #6366f1)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                textShadow: '0 0 20px rgba(103, 232, 249, 0.3)'
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
                                color="inherit"
                                startIcon={item.icon}
                                onClick={() => navigate(item.path)}
                                sx={{
                                    borderRadius: 2,
                                    px: 2,
                                    py: 1,
                                    textTransform: 'none',
                                    fontWeight: 500,
                                    transition: 'all 0.2s ease-in-out',
                                    '&:hover': {
                                        backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.1),
                                        transform: 'translateY(-2px)',
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
                                ml: 1,
                                border: (theme) => `1px solid ${alpha(theme.palette.primary.main, 0.3)}`,
                                transition: 'all 0.2s ease-in-out',
                                '&:hover': {
                                    backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.1),
                                    transform: 'rotate(180deg)',
                                }
                            }}
                        >
                            {themeName === 'dark' ? <LightMode /> : <DarkMode />}
                        </IconButton>

                        {/* Panel Access */}
                        <Button
                            variant="contained"
                            startIcon={<Dashboard />}
                            onClick={() => navigate("/en/panel")}
                            sx={{
                                ml: 2,
                                borderRadius: 2,
                                px: 3,
                                py: 1,
                                textTransform: 'none',
                                fontWeight: 600,
                                background: 'linear-gradient(45deg, #67e8f9, #818cf8)',
                                '&:hover': {
                                    background: 'linear-gradient(45deg, #22d3ee, #a5b4fc)',
                                    transform: 'translateY(-2px)',
                                    boxShadow: '0 8px 25px rgba(103, 232, 249, 0.3)',
                                }
                            }}
                        >
                            Panel
                        </Button>
                    </Box>

                    {/* Mobile Menu Button */}
                    <Box sx={{ display: { xs: 'flex', md: 'none' } }}>
                        <IconButton
                            color="inherit"
                            onClick={handleMobileMenuOpen}
                            sx={{
                                border: (theme) => `1px solid ${alpha(theme.palette.primary.main, 0.3)}`,
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
                                borderRadius: 2,
                                backdropFilter: 'blur(20px)',
                                background: (theme) => alpha(theme.palette.background.paper, 0.9),
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
                                sx={{ py: 1.5 }}
                            >
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    {item.icon}
                                    {item.label}
                                </Box>
                            </MenuItem>
                        ))}
                        <MenuItem
                            onClick={() => {
                                navigate("/en/panel");
                                handleMobileMenuClose();
                            }}
                            sx={{ py: 1.5 }}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Dashboard />
                                Panel
                            </Box>
                        </MenuItem>
                        <MenuItem
                            onClick={() => {
                                toggleTheme();
                                handleMobileMenuClose();
                            }}
                            sx={{ py: 1.5 }}
                        >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                {themeName === 'dark' ? <LightMode /> : <DarkMode />}
                                {themeName === 'dark' ? 'Light Mode' : 'Dark Mode'}
                            </Box>
                        </MenuItem>
                    </Menu>
                </Toolbar>
            </AppBar>
        </HideOnScroll>
    );
}