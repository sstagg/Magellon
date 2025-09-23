import * as React from 'react';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import AppBar from "@mui/material/AppBar";
import { styled } from '@mui/material/styles';
import {
    Avatar,
    Box,
    Tooltip,
    useMediaQuery,
    useTheme,
    Button,
    Menu,
    MenuItem
} from '@mui/material';
import { HelpCircle, Settings } from 'lucide-react';
import { AccountCircle, LogoutOutlined } from '@mui/icons-material';
import ThemeSwitcher from './ThemeSwitcher.tsx'; // Import ThemeSwitcher
import { useAuth } from '../account/UserManagement/AuthContext.tsx'; // Import useAuth

const DRAWER_WIDTH = 240;

interface AppBarProps {
    open?: boolean;
}

const StyledAppBar = styled(AppBar, {
    shouldForwardProp: (prop) => prop !== 'open',
})<AppBarProps>(({ theme, open }) => ({
    zIndex: theme.zIndex.drawer + 1,
    backgroundColor: '#0a1929', // Match drawer color - always dark
    transition: theme.transitions.create(['width', 'margin'], {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    ...(open && {
        marginLeft: DRAWER_WIDTH,
        width: `calc(100% - ${DRAWER_WIDTH}px)`,
        transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
        }),
    }),
}));

interface PanelHeaderProps {
    open: boolean;
    handleDrawerOpen: () => void;
    toggleDrawer: () => void;
}

export const PanelHeader: React.FC<PanelHeaderProps> = ({
                                                            open,
                                                            handleDrawerOpen,
                                                            toggleDrawer
                                                        }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const { user, logout } = useAuth();
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

    // Handler for opening help documentation
    const handleHelpClick = () => {
        window.open('https://magellon.org/docs', '_blank', 'noopener,noreferrer');
    };

    const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        logout();
        handleClose();
    };

    const handleProfile = () => {
        // Navigate to profile - you can implement navigation logic here
        // For example: navigate('/profile');
        handleClose();
    };

    return (
        <StyledAppBar position="fixed" open={open}>
            <Toolbar>
                <IconButton
                    color="inherit"
                    aria-label={open ? 'close drawer' : 'open drawer'}
                    onClick={toggleDrawer}
                    edge="start"
                    sx={{ mr: 2 }}
                >
                    {open ? <ChevronLeftIcon /> : <MenuIcon />}
                </IconButton>

                <Typography
                    variant="h6"
                    noWrap
                    component="div"
                    sx={{
                        flexGrow: 1,
                        fontFamily: 'Exo 2',
                        fontWeight: 'bold'
                    }}
                >
                    Magellon
                </Typography>

                {!isMobile && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Tooltip title="Help Documentation">
                            <IconButton
                                color="inherit"
                                onClick={handleHelpClick}
                                aria-label="Open help documentation"
                            >
                                <HelpCircle size={20} />
                            </IconButton>
                        </Tooltip>

                        {/* Add Theme Switcher */}
                        <ThemeSwitcher />

                        <Tooltip title="Settings">
                            <IconButton color="inherit">
                                <Settings size={20} />
                            </IconButton>
                        </Tooltip>

                        {/* User Authentication Section */}
                        {user && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, ml: 1 }}>
                                <Typography variant="body2" sx={{ color: 'inherit' }}>
                                    Welcome, {user.username}
                                </Typography>
                                <Button
                                    onClick={handleMenu}
                                    sx={{
                                        minWidth: 'auto',
                                        p: 1,
                                        '&:hover': {
                                            backgroundColor: 'rgba(255, 255, 255, 0.1)'
                                        }
                                    }}
                                >
                                    <Avatar sx={{ width: 32, height: 32 }}>
                                        {user.username.charAt(0).toUpperCase()}
                                    </Avatar>
                                </Button>
                                <Menu
                                    anchorEl={anchorEl}
                                    open={Boolean(anchorEl)}
                                    onClose={handleClose}
                                    anchorOrigin={{
                                        vertical: 'bottom',
                                        horizontal: 'right',
                                    }}
                                    transformOrigin={{
                                        vertical: 'top',
                                        horizontal: 'right',
                                    }}
                                >
                                    <MenuItem onClick={handleProfile}>
                                        <AccountCircle sx={{ mr: 1 }} />
                                        Profile
                                    </MenuItem>
                                    <MenuItem onClick={handleLogout}>
                                        <LogoutOutlined sx={{ mr: 1 }} />
                                        Logout
                                    </MenuItem>
                                </Menu>
                            </Box>
                        )}
                    </Box>
                )}
            </Toolbar>
        </StyledAppBar>
    );
};