import * as React from 'react';
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import CssBaseline from '@mui/material/CssBaseline';
import { PanelDrawer } from "./PanelDrawer.tsx";
import { PanelHeader } from "./PanelHeader.tsx";
import { PanelRoutes } from "./PanelRoutes.tsx";
import PanelFooter from './PanelFooter.tsx';

const DRAWER_WIDTH = 240;
const FOOTER_HEIGHT = 56; // Height of the footer in pixels

const Main = styled('main', { shouldForwardProp: (prop) => prop !== 'open' })<{
    open?: boolean;
}>(({ theme, open }) => ({
    flexGrow: 1,
    padding: theme.spacing(3),
    transition: theme.transitions.create('margin', {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    marginLeft: `-${DRAWER_WIDTH}px`,
    marginTop: '64px', // AppBar height
    paddingBottom: `${FOOTER_HEIGHT + theme.spacing(3)}px`, // Add padding for footer
    ...(open && {
        transition: theme.transitions.create('margin', {
            easing: theme.transitions.easing.easeOut,
            duration: theme.transitions.duration.enteringScreen,
        }),
        marginLeft: 0,
    }),
}));

export const PanelTemplate = () => {
    // Store drawer state in localStorage to persist between page refreshes
    const [open, setOpen] = React.useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Save drawer state to localStorage when it changes
    React.useEffect(() => {
        localStorage.setItem('drawerOpen', JSON.stringify(open));
    }, [open]);

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
        <Box sx={{ display: 'flex', minHeight: '100vh', position: 'relative' }}>
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
                <PanelRoutes />
            </Main>

            <PanelFooter drawerOpen={open} drawerWidth={DRAWER_WIDTH} />
        </Box>
    );
};