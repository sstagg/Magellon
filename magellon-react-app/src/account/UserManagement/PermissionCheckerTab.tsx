'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Button,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Alert,
    AlertTitle,
    CircularProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Grid,
    Chip,
    Divider,
} from '@mui/material';
import {
    Search,
    ExpandMore,
    CheckCircle,
    Cancel,
    Security,
} from '@mui/icons-material';

import { userApiService } from './userApi';
import getAxiosClient from '../../core/AxiosClient.ts';
import { settings } from '../../core/settings.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

interface PermissionCheckResult {
    has_permission: boolean;
    reason?: string;
    user_info?: {
        username: string;
        roles: string[];
        is_admin: boolean;
    };
}

interface PermissionCheckerTabProps {
    currentUser: any;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}

export default function PermissionCheckerTab({
    currentUser,
    showSnackbar,
}: PermissionCheckerTabProps) {
    const [users, setUsers] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [checking, setChecking] = useState(false);
    const [result, setResult] = useState<PermissionCheckResult | null>(null);

    const [formData, setFormData] = useState({
        user_id: '',
        permission_type: 'action',
        resource: '',
        operation: 'read',
    });

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            const usersData = await userApiService.getUsers({ include_inactive: false });
            setUsers(usersData);
        } catch (error: any) {
            showSnackbar('Failed to load users: ' + error.message, 'error');
        }
    };

    const handleCheck = async () => {
        if (!formData.user_id || !formData.resource) {
            showSnackbar('Please fill in all required fields', 'warning');
            return;
        }

        setChecking(true);
        setResult(null);

        try {
            const response = await apiClient.post('/db/security/check-permission', {
                user_id: formData.user_id,
                permission_type: formData.permission_type,
                resource: formData.resource,
                operation: formData.permission_type === 'type' ? formData.operation : undefined,
            });

            setResult(response.data);
        } catch (error: any) {
            showSnackbar('Failed to check permission: ' + (error.response?.data?.detail || error.message), 'error');
        } finally {
            setChecking(false);
        }
    };

    const getPlaceholder = () => {
        switch (formData.permission_type) {
            case 'action':
                return 'e.g., Export, Import, DeleteAll';
            case 'navigation':
                return 'e.g., /admin/users, /dashboard';
            case 'type':
                return 'e.g., Image, Session, User';
            case 'role':
                return 'e.g., Administrator, Editor';
            default:
                return '';
        }
    };

    const selectedUser = users.find(u => (u.id || u.oid) === formData.user_id);

    return (
        <Box>
            <Card>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
                        <Security color="primary" />
                        <Typography variant="h6">Permission Checker</Typography>
                    </Box>

                    <Alert severity="info" sx={{ mb: 3 }}>
                        <AlertTitle>Developer/Admin Utility</AlertTitle>
                        Test if a user has specific permissions. Useful for debugging and verifying permission configurations.
                    </Alert>

                    <Grid container spacing={3}>
                        <Grid item xs={12} md={6}>
                            <FormControl fullWidth>
                                <InputLabel>Select User</InputLabel>
                                <Select
                                    value={formData.user_id}
                                    label="Select User"
                                    onChange={(e) => setFormData({ ...formData, user_id: e.target.value })}
                                >
                                    {users.map((user) => (
                                        <MenuItem key={user.id || user.oid} value={user.id || user.oid}>
                                            {user.username}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <FormControl fullWidth>
                                <InputLabel>Permission Type</InputLabel>
                                <Select
                                    value={formData.permission_type}
                                    label="Permission Type"
                                    onChange={(e) =>
                                        setFormData({ ...formData, permission_type: e.target.value, resource: '' })
                                    }
                                >
                                    <MenuItem value="action">Action Permission</MenuItem>
                                    <MenuItem value="navigation">Navigation Permission</MenuItem>
                                    <MenuItem value="type">Type Permission</MenuItem>
                                    <MenuItem value="role">Role Check</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} md={formData.permission_type === 'type' ? 6 : 12}>
                            <TextField
                                fullWidth
                                label="Resource"
                                value={formData.resource}
                                onChange={(e) => setFormData({ ...formData, resource: e.target.value })}
                                placeholder={getPlaceholder()}
                                required
                            />
                        </Grid>

                        {formData.permission_type === 'type' && (
                            <Grid item xs={12} md={6}>
                                <FormControl fullWidth>
                                    <InputLabel>Operation</InputLabel>
                                    <Select
                                        value={formData.operation}
                                        label="Operation"
                                        onChange={(e) => setFormData({ ...formData, operation: e.target.value })}
                                    >
                                        <MenuItem value="read">Read</MenuItem>
                                        <MenuItem value="write">Write</MenuItem>
                                        <MenuItem value="create">Create</MenuItem>
                                        <MenuItem value="delete">Delete</MenuItem>
                                        <MenuItem value="navigate">Navigate</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                        )}

                        <Grid item xs={12}>
                            <Button
                                variant="contained"
                                startIcon={checking ? <CircularProgress size={20} /> : <Search />}
                                onClick={handleCheck}
                                disabled={checking || !formData.user_id || !formData.resource}
                                fullWidth
                                size="large"
                            >
                                {checking ? 'Checking...' : 'Check Permission'}
                            </Button>
                        </Grid>
                    </Grid>

                    {result && (
                        <Box sx={{ mt: 3 }}>
                            <Divider sx={{ mb: 3 }} />

                            <Alert
                                severity={result.has_permission ? 'success' : 'error'}
                                icon={result.has_permission ? <CheckCircle /> : <Cancel />}
                                sx={{ mb: 2 }}
                            >
                                <AlertTitle>
                                    {result.has_permission ? '✓ Permission Granted' : '✗ Permission Denied'}
                                </AlertTitle>
                                {result.reason || 'User has access to this resource'}
                            </Alert>

                            {result.user_info && (
                                <Accordion>
                                    <AccordionSummary expandIcon={<ExpandMore />}>
                                        <Typography variant="subtitle2">Permission Resolution Details</Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                            <Box>
                                                <Typography variant="caption" color="text.secondary">
                                                    User
                                                </Typography>
                                                <Typography variant="body2">
                                                    {result.user_info.username}
                                                </Typography>
                                            </Box>

                                            <Box>
                                                <Typography variant="caption" color="text.secondary">
                                                    Roles
                                                </Typography>
                                                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                                                    {result.user_info.roles.map((role, idx) => (
                                                        <Chip key={idx} label={role} size="small" />
                                                    ))}
                                                    {result.user_info.roles.length === 0 && (
                                                        <Typography variant="body2" color="text.secondary">
                                                            No roles assigned
                                                        </Typography>
                                                    )}
                                                </Box>
                                            </Box>

                                            <Box>
                                                <Typography variant="caption" color="text.secondary">
                                                    Is Administrator
                                                </Typography>
                                                <Typography variant="body2">
                                                    {result.user_info.is_admin ? (
                                                        <Chip
                                                            label="Yes"
                                                            color="error"
                                                            size="small"
                                                            icon={<CheckCircle />}
                                                        />
                                                    ) : (
                                                        <Chip label="No" size="small" variant="outlined" />
                                                    )}
                                                </Typography>
                                            </Box>

                                            <Box>
                                                <Typography variant="caption" color="text.secondary">
                                                    Checked Permission
                                                </Typography>
                                                <Box
                                                    sx={{
                                                        mt: 0.5,
                                                        p: 1.5,
                                                        bgcolor: 'background.default',
                                                        borderRadius: 1,
                                                        fontFamily: 'monospace',
                                                        fontSize: '0.875rem',
                                                    }}
                                                >
                                                    <div>Type: {formData.permission_type}</div>
                                                    <div>Resource: {formData.resource}</div>
                                                    {formData.permission_type === 'type' && (
                                                        <div>Operation: {formData.operation}</div>
                                                    )}
                                                </Box>
                                            </Box>
                                        </Box>
                                    </AccordionDetails>
                                </Accordion>
                            )}
                        </Box>
                    )}
                </CardContent>
            </Card>

            {selectedUser && (
                <Card sx={{ mt: 3 }}>
                    <CardContent>
                        <Typography variant="subtitle2" gutterBottom>
                            Quick Tests for {selectedUser.username}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 2 }}>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={() =>
                                    setFormData({
                                        ...formData,
                                        permission_type: 'action',
                                        resource: 'Export',
                                    })
                                }
                            >
                                Test Export Action
                            </Button>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={() =>
                                    setFormData({
                                        ...formData,
                                        permission_type: 'navigation',
                                        resource: '/admin/users',
                                    })
                                }
                            >
                                Test Admin Navigation
                            </Button>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={() =>
                                    setFormData({
                                        ...formData,
                                        permission_type: 'type',
                                        resource: 'User',
                                        operation: 'delete',
                                    })
                                }
                            >
                                Test User Delete
                            </Button>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={() =>
                                    setFormData({
                                        ...formData,
                                        permission_type: 'role',
                                        resource: 'Administrator',
                                    })
                                }
                            >
                                Test Administrator Role
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            )}
        </Box>
    );
}
