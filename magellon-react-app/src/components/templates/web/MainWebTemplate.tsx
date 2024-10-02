import {MainWebRoutes} from "./MainWebRoutes.tsx";
import {Outlet, useParams} from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';

// material-ui
import { useTheme } from '@mui/material/styles';
import {Box, Grid, Paper, Toolbar, useMediaQuery} from '@mui/material';

import WebHeader from "./WebHeader.tsx";
import WebFooter from "./WebFooter.tsx";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";

export const MainWebTemplate = () => {
    const theme = useTheme();
    return (
         <Container>
                <WebHeader/>
                {/*<Drawer open={open} handleDrawerToggle={handleDrawerToggle} />*/}
                {/*    /!*<Outlet />*!/*/}
             <h1 className="mb3 text-amber-500">Magellon</h1>
                <Container>
                    <Paper style={{ padding: '20px', marginTop: '20px' }}>
                        {/* Add your main content here */}
                        <Typography variant="h4">Welcome to Magellon</Typography>
                        <p>CryoEm application.</p>
                    </Paper>
                    <MainWebRoutes/>
                </Container>

                <WebFooter/>
            </Container>
    );
};
