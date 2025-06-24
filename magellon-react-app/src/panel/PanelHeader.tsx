import * as React from 'react';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import AppBar from "@mui/material/AppBar";
import { styled } from '@mui/material/styles';
import { Avatar, Box, Tooltip, useMediaQuery, useTheme } from '@mui/material';
import { HelpCircle, Settings } from 'lucide-react';
import ThemeSwitcher from './ThemeSwitcher.tsx'; // Import ThemeSwitcher

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
                        <Tooltip title="Help">
                            <IconButton color="inherit">
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
                        <Tooltip title="User Profile">
                            <IconButton sx={{ p: 0.5, ml: 1 }}>
                                <Avatar sx={{ width: 32, height: 32 }} />
                            </IconButton>
                        </Tooltip>
                    </Box>
                )}
            </Toolbar>
        </StyledAppBar>
    );
};