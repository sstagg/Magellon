import React from 'react';
import { MainWebRoutes } from "./MainWebRoutes.tsx";
import { useTheme } from '@mui/material/styles';
import { Box } from '@mui/material';
import WebHeader from "./WebHeader.tsx";
import WebFooter from "./WebFooter.tsx";

export const MainWebTemplate = () => {
    const theme = useTheme();

    return (
        <Box
            sx={{
                minHeight: '100vh',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)'
                    : 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
            }}
        >
            <WebHeader />

            {/* Main content area that grows to fill space */}
            <Box
                component="main"
                sx={{
                    flex: '1 0 auto', // This will grow to fill space but footer will always show
                    width: '100%',
                    pt: { xs: 8, sm: 9 }, // Account for AppBar height
                }}
            >
                <MainWebRoutes />
            </Box>

            {/* Footer will always appear at bottom */}
            <WebFooter />
        </Box>
    );
};