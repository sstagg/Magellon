import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../UserManagement/AuthContext';
import { Box, CircularProgress, Container, Typography } from '@mui/material';

interface ProtectedRouteProps {
    children: React.ReactNode;
    fallback?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
                                                                  children,
                                                                  fallback = '/en/account/'
                                                              }) => {
    const { isAuthenticated, loading } = useAuth();
    const location = useLocation();

    // Show loading spinner while checking authentication
    if (loading) {
        return (
            <Container maxWidth="sm">
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center',
                        alignItems: 'center',
                        minHeight: '60vh',
                        gap: 2
                    }}
                >
                    <CircularProgress size={40} />
                    <Typography variant="body1" color="text.secondary">
                        Verifying authentication...
                    </Typography>
                </Box>
            </Container>
        );
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to={fallback} state={{ from: location }} replace />;
    }

    return <>{children}</>;
};