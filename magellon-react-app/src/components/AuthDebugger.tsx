/**
 * Authentication Debugger Component
 *
 * Add this component to your app temporarily to debug authentication issues.
 *
 * Usage:
 * import { AuthDebugger } from './components/AuthDebugger';
 *
 * // Add to your App.tsx or any page:
 * <AuthDebugger />
 */

import React, { useState } from 'react';
import { useAuth } from '../account/UserManagement/AuthContext';
import { Box, Paper, Typography, Button, TextField, Alert, Chip } from '@mui/material';

export const AuthDebugger: React.FC = () => {
    const { user, isAuthenticated, login, logout } = useAuth();
    const [username, setUsername] = useState('super');
    const [password, setPassword] = useState('super');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const token = localStorage.getItem('access_token');
    const currentUser = localStorage.getItem('currentUser');

    const handleLogin = async () => {
        setLoading(true);
        setError('');
        try {
            await login(username, password);
            console.log('✅ Login successful!');
            console.log('Token:', localStorage.getItem('access_token'));
        } catch (err: any) {
            console.error('❌ Login failed:', err);
            setError(err.message || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    const handleTestApi = async () => {
        const token = localStorage.getItem('access_token');

        console.log('Testing API with token:', token);

        try {
            const response = await fetch('http://localhost:8000/db/security/users', {
                headers: {
                    'Authorization': token ? `Bearer ${token}` : ''
                }
            });

            const data = await response.json();
            console.log('API Response:', response.status, data);

            if (!response.ok) {
                setError(`API Error ${response.status}: ${JSON.stringify(data)}`);
            } else {
                setError('');
                alert('API call successful! Check console for data.');
            }
        } catch (err: any) {
            console.error('API Error:', err);
            setError(err.message);
        }
    };

    return (
        <Paper
            sx={{
                position: 'fixed',
                bottom: 20,
                right: 20,
                p: 2,
                width: 400,
                maxHeight: '80vh',
                overflowY: 'auto',
                zIndex: 9999,
                backgroundColor: 'background.paper',
                border: '2px solid',
                borderColor: 'primary.main'
            }}
        >
            <Typography variant="h6" gutterBottom>
                🔍 Auth Debugger
            </Typography>

            {/* Authentication Status */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Status:</Typography>
                <Chip
                    label={isAuthenticated ? 'Authenticated ✅' : 'Not Authenticated ❌'}
                    color={isAuthenticated ? 'success' : 'error'}
                    size="small"
                    sx={{ mr: 1 }}
                />
                {user && (
                    <Chip
                        label={`User: ${user.username}`}
                        color="primary"
                        size="small"
                    />
                )}
            </Box>

            {/* LocalStorage Status */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>LocalStorage:</Typography>
                <Typography variant="caption" component="div">
                    access_token: {token ? '✅ Exists' : '❌ Missing'}
                </Typography>
                {token && (
                    <Typography variant="caption" component="div" sx={{ fontFamily: 'monospace', fontSize: '0.7rem', wordBreak: 'break-all' }}>
                        {token.substring(0, 50)}...
                    </Typography>
                )}
                <Typography variant="caption" component="div">
                    currentUser: {currentUser ? '✅ Exists' : '❌ Missing'}
                </Typography>
            </Box>

            {/* Login Form */}
            {!isAuthenticated && (
                <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>Quick Login:</Typography>
                    <TextField
                        fullWidth
                        size="small"
                        label="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        sx={{ mb: 1 }}
                    />
                    <TextField
                        fullWidth
                        size="small"
                        type="password"
                        label="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        sx={{ mb: 1 }}
                    />
                    <Button
                        fullWidth
                        variant="contained"
                        onClick={handleLogin}
                        disabled={loading}
                    >
                        {loading ? 'Logging in...' : 'Login'}
                    </Button>
                </Box>
            )}

            {/* Error Display */}
            {error && (
                <Alert severity="error" sx={{ mb: 2, fontSize: '0.75rem' }}>
                    {error}
                </Alert>
            )}

            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
                {isAuthenticated && (
                    <>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={handleTestApi}
                        >
                            Test API Call
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={logout}
                        >
                            Logout
                        </Button>
                    </>
                )}
                <Button
                    size="small"
                    variant="outlined"
                    onClick={() => {
                        console.log('=== FULL DIAGNOSTIC ===');
                        console.log('isAuthenticated:', isAuthenticated);
                        console.log('user:', user);
                        console.log('access_token:', localStorage.getItem('access_token'));
                        console.log('currentUser:', localStorage.getItem('currentUser'));
                        console.log('currentUserId:', localStorage.getItem('currentUserId'));
                        console.log('=== END ===');
                    }}
                >
                    Log Diagnostic to Console
                </Button>
            </Box>

            <Typography variant="caption" display="block" sx={{ mt: 2, opacity: 0.7 }}>
                Remove this component in production
            </Typography>
        </Paper>
    );
};
