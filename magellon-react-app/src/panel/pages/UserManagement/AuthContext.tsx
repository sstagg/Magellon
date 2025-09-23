// contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { userApiService, AuthenticationResponse } from './userApi';

interface User {
    id: string;
    username: string;
    active: boolean;
    change_password_required: boolean;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    // Check if user is already logged in on app start
    useEffect(() => {
        const savedUser = localStorage.getItem('currentUser');
        const savedUserId = localStorage.getItem('currentUserId');

        if (savedUser && savedUserId) {
            try {
                const parsedUser = JSON.parse(savedUser);
                setUser(parsedUser);
            } catch (error) {
                console.error('Failed to parse saved user data:', error);
                localStorage.removeItem('currentUser');
                localStorage.removeItem('currentUserId');
            }
        }
        setLoading(false);
    }, []);

    const login = async (username: string, password: string): Promise<void> => {
        setLoading(true);
        try {
            const authResponse: AuthenticationResponse = await userApiService.authenticate({
                username,
                password
            });

            const userData: User = {
                id: authResponse.user_id,
                username: authResponse.username,
                active: true, // If authentication succeeds, user is active
                change_password_required: authResponse.change_password_required
            };

            setUser(userData);

            // Save to localStorage for persistence
            localStorage.setItem('currentUser', JSON.stringify(userData));
            localStorage.setItem('currentUserId', authResponse.user_id);

        } catch (error) {
            throw error; // Re-throw so the login component can handle it
        } finally {
            setLoading(false);
        }
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem('currentUser');
        localStorage.removeItem('currentUserId');
    };

    const value: AuthContextType = {
        user,
        loading,
        login,
        logout,
        isAuthenticated: !!user
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

// Simple Login Component
import {
    Box,
    Card,
    CardContent,
    TextField,
    Button,
    Typography,
    Alert,
    Container,
    Paper,
    Stack
} from '@mui/material';
import { Lock } from '@mui/icons-material';

interface LoginPageProps {
    onLoginSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
    const { login, loading } = useAuth();
    const [credentials, setCredentials] = useState({ username: '', password: '' });
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            await login(credentials.username, credentials.password);
            onLoginSuccess?.();
        } catch (error) {
            setError((error as Error).message);
        }
    };

    return (
        <Container maxWidth="sm">
            <Box sx={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                <Paper elevation={3} sx={{ p: 4, width: '100%', maxWidth: 400 }}>
                    <Box sx={{ textAlign: 'center', mb: 3 }}>
                        <Lock sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
                        <Typography variant="h4" component="h1" gutterBottom>
                            Magellon Login
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            Sign in to your account
                        </Typography>
                    </Box>

                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {error}
                        </Alert>
                    )}

                    <form onSubmit={handleSubmit}>
                        <Stack spacing={2}>
                            <TextField
                                fullWidth
                                label="Username"
                                value={credentials.username}
                                onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
                                required
                            />
                            <TextField
                                fullWidth
                                label="Password"
                                type="password"
                                value={credentials.password}
                                onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                                required
                            />
                            <Button
                                type="submit"
                                variant="contained"
                                size="large"
                                disabled={loading}
                                fullWidth
                            >
                                {loading ? 'Signing In...' : 'Sign In'}
                            </Button>
                        </Stack>
                    </form>
                </Paper>
            </Box>
        </Container>
    );
};