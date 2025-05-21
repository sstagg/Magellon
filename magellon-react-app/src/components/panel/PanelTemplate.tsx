import * as React from 'react';
import { styled, useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import CssBaseline from '@mui/material/CssBaseline';
import { PanelDrawer } from "./PanelDrawer.tsx";
import { PanelHeader } from "./PanelHeader.tsx";
import { PanelRoutes } from "./PanelRoutes.tsx";
import PanelFooter from './PanelFooter.tsx';
import { useMediaQuery } from '@mui/material';

const DRAWER_WIDTH = 240;
const FOOTER_HEIGHT = 56; // Height of the footer in pixels

// Improved Main component with adjusted styling to prevent the boxed appearance
const Main = styled('main', { shouldForwardProp: (prop) => prop !== 'open' })<{
    open?: boolean;
}>(({ theme, open }) => ({
    flexGrow: 1,
    width: '100%', // Ensure main content takes full width available
    padding: theme.spacing(3),
    paddingLeft: theme.spacing(3),
    paddingRight: theme.spacing(3),
    transition: theme.transitions.create(['margin', 'width'], {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    marginLeft: `-${DRAWER_WIDTH}px`,
    marginTop: '64px', // AppBar height
    paddingBottom: `${FOOTER_HEIGHT + theme.spacing(3)}px`, // Add padding for footer
    overflowX: 'hidden', // Prevent horizontal scroll
    ...(open && {
        width: `calc(100% - ${DRAWER_WIDTH}px)`, // Adjust width when drawer is open
        transition: theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.easeOut,
            duration: theme.transitions.duration.enteringScreen,
        }),
        marginLeft: 0,
    }),
    // Remove any border or box styling
    border: 'none',
    boxShadow: 'none',
    borderRadius: 0,
    // Allow content to expand as needed
    maxWidth: '100%',
}));

export const PanelTemplate = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Store drawer state in localStorage to persist between page refreshes
    const [open, setOpen] = React.useState(() => {
        // For mobile devices, default to closed drawer
        if (isMobile) return false;

        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Save drawer state to localStorage when it changes
    React.useEffect(() => {
        localStorage.setItem('drawerOpen', JSON.stringify(open));
    }, [open]);

    // Close drawer when screen size becomes mobile
    React.useEffect(() => {
        if (isMobile && open) {
            setOpen(false);
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
                overflow: 'hidden' // Prevent any overflow at the container level
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

            <Main open={open}>
                <Box
                    sx={{
                        width: '100%',
                        height: '100%',
                        // Remove any styling that could make it appear boxed
                        border: 'none',
                        borderRadius: 0,
                        boxShadow: 'none',
                        // Allow content to take all available space
                        maxWidth: '100%'
                    }}
                >
                    <PanelRoutes />
                </Box>
            </Main>

            <PanelFooter drawerOpen={open} drawerWidth={DRAWER_WIDTH} />
        </Box>
    );
};