// For routes that should redirect authenticated users away (like login page)
import {useAuth} from "./UserManagement/AuthContext.tsx";
import {Navigate, useLocation} from "react-router-dom";
import {Box, CircularProgress, Container, Typography} from "@mui/material";

interface PublicRouteProps {
    children: React.ReactNode;
    redirectTo?: string;
}

export const PublicRoute: React.FC<PublicRouteProps> = ({
                                                            children,
                                                            redirectTo = '/en/panel/images'
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
                        Loading...
                    </Typography>
                </Box>
            </Container>
        );
    }

    // Redirect to intended destination or default panel if already authenticated
    if (isAuthenticated) {
        const from = location.state?.from?.pathname || redirectTo;
        return <Navigate to={from} replace />;
    }

    return <>{children}</>;
};