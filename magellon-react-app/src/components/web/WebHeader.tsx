import * as React from 'react';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import { useNavigate} from "react-router-dom";

export default function WebHeader() {
    const navigate = useNavigate();
    return (

            <AppBar >
                <Toolbar>
                    <IconButton
                        size="large"
                        edge="start"
                        color="inherit"
                        aria-label="menu"
                        sx={{ mr: 2 }}
                    >

                    </IconButton>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        Magellon
                    </Typography>
                    <Button color="inherit" onClick={()=> navigate("/en/panel")}>Panel</Button>
                </Toolbar>
            </AppBar>

    );
}