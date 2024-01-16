import * as React from 'react';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';

import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';

import AppBar from "@mui/material/AppBar";

interface PanelHeaderProps {
    open: boolean;
    handleDrawerOpen: () => void;
}

export const PanelHeader  : React.FC<PanelHeaderProps> = ({open,handleDrawerOpen}) => {
    return (
            <AppBar  position="fixed">
                <Toolbar>
                    <IconButton
                        color="inherit"
                        aria-label="open drawer"
                        onClick={handleDrawerOpen}
                        edge="start"
                        sx={{ mr: 2, ...(open && { display: 'none' }) }}
                    >
                        <MenuIcon />
                    </IconButton>
                    <Typography variant="h6" noWrap component="div" sx={{fontFamily: 'Exo 2' }}>
                        Magellon
                    </Typography>
                </Toolbar>
            </AppBar>
    );
};
