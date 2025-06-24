import * as React from 'react';
import { styled, useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import CssBaseline from '@mui/material/CssBaseline';
import { PanelDrawer } from "./PanelDrawer.tsx";
import { PanelHeader } from "./PanelHeader.tsx";
import { PanelRoutes } from "./PanelRoutes.tsx";
import PanelFooter from './PanelFooter.tsx';
import { useMediaQuery } from '@mui/material';
import { useLocation } from 'react-router-dom';

const DRAWER_WIDTH = 240;
const FOOTER_HEIGHT = 56;

// Routes that should have full-width layout (no padding)
const FULL_WIDTH_ROUTES = [
    'mrc-viewer',
    'images', // Add other routes that need full width
    // Add more routes as needed
];

// Improved Main component with conditional styling based on route
const Main = styled('main', { shouldForwardProp: (prop) => prop !== 'open' && prop !== 'isFullWidth' })<{
    open?: boolean;
    isFullWidth?: boolean;
}>(({ theme, open, isFullWidth }) => ({
    flexGrow: 1,
    width: '100%',
    // Conditional padding - none for full-width pages
    padding: isFullWidth ? 0 : theme.spacing(3),
    paddingLeft: isFullWidth ? 0 : theme.spacing(3),
    paddingRight: isFullWidth ? 0 : theme.spacing(3),
    transition: theme.transitions.create(['margin', 'width'], {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    marginLeft: `-${DRAWER_WIDTH}px`,
    marginTop: '64px', // AppBar height
    paddingBottom: isFullWidth ? 0 : `${FOOTER_HEIGHT + theme.spacing(3)}px`,
    overflowX: 'hidden',
    // Full height for full-width pages
    height: isFullWidth ? 'calc(100vh - 64px)' : 'auto',
    ...(open && {
        width: `calc(100% - ${DRAWER_WIDTH}px)`,
        transition: theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.easeOut,
            duration: theme.transitions.duration.enteringScreen,
        }),
        marginLeft: 0,
    }),
    border: 'none',
    boxShadow: 'none',
    borderRadius: 0,
    maxWidth: '100%',
}));

export const PanelTemplate = () => {
    const theme = useTheme();
    const location = useLocation();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Check if current route should have full-width layout
    const isFullWidthRoute = FULL_WIDTH_ROUTES.some(route => {
        // Remove leading slash and check if pathname includes the route
        const cleanPath = location.pathname.replace(/^\/+/, '');
        return cleanPath.includes(route);
    });

    console.log('Current path:', location.pathname);
    console.log('Is full width route:', isFullWidthRoute);

    // Store drawer state in localStorage to persist between page refreshes
    const [open, setOpen] = React.useState(() => {
        // For mobile devices, default to closed drawer unless explicitly opened
        if (isMobile) return false;

        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Save drawer state to localStorage when it changes
    React.useEffect(() => {
        localStorage.setItem('drawerOpen', JSON.stringify(open));
    }, [open]);

    // Auto-close drawer when screen becomes mobile, but allow manual opening
    React.useEffect(() => {
        // Only auto-close if the drawer was opened on desktop and screen becomes mobile
        // Don't prevent manual opening on mobile
        if (isMobile && open) {
            const wasOpenedOnDesktop = localStorage.getItem('drawerOpenedOnDesktop');
            if (wasOpenedOnDesktop === 'true') {
                setOpen(false);
                localStorage.setItem('drawerOpenedOnDesktop', 'false');
            }
        } else if (!isMobile && open) {
            // Mark that drawer was opened on desktop
            localStorage.setItem('drawerOpenedOnDesktop', 'true');
        }
    }, [isMobile, open]);

    const handleDrawerClose = () => {
        setOpen(false);
    };

    const handleDrawerOpen = () => {
        setOpen(true);
    };

    const toggleDrawer = () => {
        setOpen(prev => !prev);
    };

    return (
        <Box
            sx={{
                display: 'flex',
                minHeight: '100vh',
                position: 'relative',
                width: '100%',
                overflow: 'hidden'
            }}
        >
            <CssBaseline />
            <PanelHeader
                open={open}
                handleDrawerOpen={handleDrawerOpen}
                toggleDrawer={toggleDrawer}
            />
            <PanelDrawer
                open={open}
                handleDrawerClose={handleDrawerClose}
            />

            <Main open={open} isFullWidth={isFullWidthRoute}>
                <Box
                    sx={{
                        width: '100%',
                        height: isFullWidthRoute ? '100%' : 'auto',
                        border: 'none',
                        borderRadius: 0,
                        boxShadow: 'none',
                        maxWidth: '100%',
                        overflow: isFullWidthRoute ? 'hidden' : 'visible'
                    }}
                >
                    <PanelRoutes />
                </Box>
            </Main>

            {/* Hide footer for full-width routes */}
            {!isFullWidthRoute && (
                <PanelFooter drawerOpen={open} drawerWidth={DRAWER_WIDTH} />
            )}
        </Box>
    );
};