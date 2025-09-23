// For routes that behave differently based on auth status
import {useAuth} from "./UserManagement/AuthContext.tsx";
import {Box, CircularProgress, Container} from "@mui/material";

interface ConditionalRouteProps {
    authenticatedComponent: React.ReactNode;
    unauthenticatedComponent: React.ReactNode;
}

export const ConditionalRoute: React.FC<ConditionalRouteProps> = ({
                                                                      authenticatedComponent,
                                                                      unauthenticatedComponent
                                                                  }) => {
    const { isAuthenticated, loading } = useAuth();

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
                </Box>
            </Container>
        );
    }

    return isAuthenticated ? <>{authenticatedComponent}</> : <>{unauthenticatedComponent}</>;
};