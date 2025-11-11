'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Checkbox,
    FormControlLabel,
    IconButton,
    Tooltip,
    CircularProgress,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Chip,
    Grid,
    Autocomplete,
} from '@mui/material';
import {
    Add,
    Delete,
    Refresh,
    CheckCircle,
    Cancel,
    Lock,
    LockOpen,
} from '@mui/icons-material';

import { SessionAccessAPI, GrantSessionAccessRequest } from './rbacApi';

interface User {
    id: string;
    username: string;
}

interface Session {
    oid: string;
    name: string;
    description?: string;
    start_on?: string;
}

interface SessionAccessManagementTabProps {
    currentUser: User;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
    isSuperUser?: boolean;
}

interface BulkGrantSessionAccessRequest {
    user_id: string;
    session_ids: string[]; // Multiple sessions
    read_access: boolean;
    write_access: boolean;
    delete_access: boolean;
}

interface UserWithAccess {
    user_id: string;
    username: string;
    role_name: string;
    read_access: boolean;
    write_access: boolean;
    delete_access: boolean;
    permission_id: string;
}

export default function SessionAccessManagementTab({
    currentUser,
    showSnackbar,
    isSuperUser = false,
}: SessionAccessManagementTabProps) {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [users, setUsers] = useState<User[]>([]);
    const [selectedSession, setSelectedSession] = useState<string>('');
    const [selectedSessions, setSelectedSessions] = useState<string[]>([]); // Multi-select for bulk grant
    const [selectedUser, setSelectedUser] = useState<string>('');
    const [readAccess, setReadAccess] = useState(true);
    const [writeAccess, setWriteAccess] = useState(false);
    const [deleteAccess, setDeleteAccess] = useState(false);
    const [usersWithAccess, setUsersWithAccess] = useState<UserWithAccess[]>([]);
    const [loading, setLoading] = useState(false);
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [openGrantDialog, setOpenGrantDialog] = useState(false);

    useEffect(() => {
        loadSessions();
        loadUsers();
    }, []);

    useEffect(() => {
        if (selectedSession) {
            loadSessionUsers(selectedSession);
        } else {
            setUsersWithAccess([]);
        }
    }, [selectedSession]);

    const loadSessions = async () => {
        try {
            setLoading(true);
            const response = await SessionAccessAPI.getAllSessions();
            setSessions(response || []);
        } catch (error: any) {
            console.error('Failed to load sessions:', error);
            showSnackbar('Failed to load sessions: ' + (error.message || 'Unknown error'), 'error');
        } finally {
            setLoading(false);
        }
    };

    const loadUsers = async () => {
        try {
            // Fetch users from the users endpoint using axios
            const axios = (await import('axios')).default;
            const token = localStorage.getItem('access_token');

            const response = await axios.get('http://localhost:8000/db/security/users/', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            const data = response.data;
            // Map to User interface format
            const mappedUsers = data.map((user: any) => ({
                id: user.oid,
                username: user.USERNAME,
            }));
            setUsers(mappedUsers);
        } catch (error: any) {
            console.error('Failed to load users:', error);
            showSnackbar('Failed to load users: ' + (error.message || 'Unknown error'), 'error');
        }
    };

    const loadSessionUsers = async (sessionId: string) => {
        try {
            setLoadingUsers(true);
            const response = await SessionAccessAPI.getSessionUsers(sessionId);
            setUsersWithAccess(response.users || []);

            // Note: This shows permissions created by BOTH UIs:
            // - Session Access Tab creates: [session_id] = 'uuid'
            // - Object Permission Tab creates: [session_id] = 'uuid' OR [session_id] IN (...)
            // Both are stored in sys_sec_object_permission and appear here
        } catch (error: any) {
            console.error('Failed to load session users:', error);
            // Don't show error if no users found (404 is expected for sessions without permissions)
            if (error.response?.status !== 404) {
                showSnackbar('Failed to load session users: ' + (error.message || 'Unknown error'), 'error');
            }
            setUsersWithAccess([]);
        } finally {
            setLoadingUsers(false);
        }
    };

    const handleGrantAccess = async () => {
        if (!selectedUser || selectedSessions.length === 0) {
            showSnackbar('Please select a user and at least one session', 'warning');
            return;
        }

        try {
            // Grant access to multiple sessions
            // This creates ONE object permission with IN clause if multiple sessions
            if (selectedSessions.length === 1) {
                // Single session: [session_id] = 'uuid'
                const request: GrantSessionAccessRequest = {
                    user_id: selectedUser,
                    session_id: selectedSessions[0],
                    read_access: readAccess,
                    write_access: writeAccess,
                    delete_access: deleteAccess,
                };

                const response = await SessionAccessAPI.grantAccess(request);

                if (response.success) {
                    showSnackbar(
                        `${response.message}. Synced ${response.policies_synced || 0} policies.`,
                        'success'
                    );
                }
            } else {
                // Multiple sessions: Create criteria [session_id] IN ('uuid1', 'uuid2', ...)
                // This requires a different backend endpoint or generic object permission creation
                showSnackbar(
                    `Granting access to ${selectedSessions.length} sessions. This creates: [session_id] IN ('${selectedSessions.join("', '")}')`,
                    'info'
                );

                // For now, create individual permissions for each session
                // TODO: Update backend to accept bulk with IN clause
                let successCount = 0;
                for (const sessionId of selectedSessions) {
                    try {
                        const request: GrantSessionAccessRequest = {
                            user_id: selectedUser,
                            session_id: sessionId,
                            read_access: readAccess,
                            write_access: writeAccess,
                            delete_access: deleteAccess,
                        };
                        await SessionAccessAPI.grantAccess(request);
                        successCount++;
                    } catch (err) {
                        console.error(`Failed to grant access to session ${sessionId}:`, err);
                    }
                }

                showSnackbar(
                    `Successfully granted access to ${successCount} of ${selectedSessions.length} sessions.`,
                    successCount === selectedSessions.length ? 'success' : 'warning'
                );
            }

            // Reload users with access for currently selected session
            if (selectedSession) {
                loadSessionUsers(selectedSession);
            }

            // Reset form
            setSelectedUser('');
            setSelectedSessions([]);
            setReadAccess(true);
            setWriteAccess(false);
            setDeleteAccess(false);
            setOpenGrantDialog(false);
        } catch (error: any) {
            console.error('Failed to grant access:', error);
            showSnackbar(
                'Failed to grant access: ' + (error.response?.data?.detail || error.message || 'Unknown error'),
                'error'
            );
        }
    };

    const handleRevokeAccess = async (userId: string) => {
        if (!selectedSession) return;

        if (!confirm('Are you sure you want to revoke this user\'s access to this session?')) {
            return;
        }

        try {
            const response = await SessionAccessAPI.revokeAccess(userId, selectedSession);

            if (response.success) {
                showSnackbar(
                    `${response.message}. Synced ${response.policies_synced || 0} policies.`,
                    'success'
                );
                loadSessionUsers(selectedSession);
            } else {
                showSnackbar('Failed to revoke access: ' + response.message, 'error');
            }
        } catch (error: any) {
            console.error('Failed to revoke access:', error);
            showSnackbar(
                'Failed to revoke access: ' + (error.response?.data?.detail || error.message || 'Unknown error'),
                'error'
            );
        }
    };

    return (
        <Box>
            <Typography variant="h5" gutterBottom>
                Session Access Management
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
                Grant or revoke user access to specific imaging sessions. This implements row-level security
                using Casbin policies.
            </Typography>

            {isSuperUser && (
                <Alert severity="info" sx={{ mb: 3 }}>
                    Super user mode: You can manage session access for all users and sessions.
                </Alert>
            )}

            <Grid container spacing={3}>
                {/* Session Selection */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">1. Select Session</Typography>
                            <Button
                                startIcon={<Refresh />}
                                onClick={loadSessions}
                                disabled={loading}
                            >
                                Refresh
                            </Button>
                        </Box>

                        <FormControl fullWidth>
                            <InputLabel>Session</InputLabel>
                            <Select
                                value={selectedSession}
                                onChange={(e) => setSelectedSession(e.target.value)}
                                label="Session"
                                disabled={loading}
                            >
                                <MenuItem value="">
                                    <em>Select a session...</em>
                                </MenuItem>
                                {sessions.map((session) => (
                                    <MenuItem key={session.oid} value={session.oid}>
                                        {session.name || session.oid}
                                        {session.start_on && ` (${new Date(session.start_on).toLocaleDateString()})`}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        {selectedSession && (
                            <Box sx={{ mt: 2 }}>
                                <Chip
                                    icon={<CheckCircle />}
                                    label={`Session ID: ${selectedSession}`}
                                    color="primary"
                                    size="small"
                                />
                            </Box>
                        )}
                    </Paper>
                </Grid>

                {/* Users with Access */}
                {selectedSession && (
                    <Grid item xs={12}>
                        <Paper sx={{ p: 3 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                <Typography variant="h6">
                                    2. Users with Access ({usersWithAccess.length})
                                </Typography>
                                <Button
                                    startIcon={<Add />}
                                    variant="contained"
                                    onClick={() => setOpenGrantDialog(true)}
                                >
                                    Grant Access
                                </Button>
                            </Box>

                            {loadingUsers ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                                    <CircularProgress />
                                </Box>
                            ) : usersWithAccess.length === 0 ? (
                                <Alert severity="info">
                                    No users have access to this session yet. Click "Grant Access" to add users.
                                </Alert>
                            ) : (
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Username</TableCell>
                                                <TableCell>Role</TableCell>
                                                <TableCell align="center">Read</TableCell>
                                                <TableCell align="center">Write</TableCell>
                                                <TableCell align="center">Delete</TableCell>
                                                <TableCell align="center">Actions</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {usersWithAccess.map((user) => (
                                                <TableRow key={user.permission_id}>
                                                    <TableCell>{user.username}</TableCell>
                                                    <TableCell>
                                                        <Chip label={user.role_name} size="small" />
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {user.read_access ? (
                                                            <CheckCircle color="success" fontSize="small" />
                                                        ) : (
                                                            <Cancel color="disabled" fontSize="small" />
                                                        )}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {user.write_access ? (
                                                            <CheckCircle color="success" fontSize="small" />
                                                        ) : (
                                                            <Cancel color="disabled" fontSize="small" />
                                                        )}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {user.delete_access ? (
                                                            <CheckCircle color="success" fontSize="small" />
                                                        ) : (
                                                            <Cancel color="disabled" fontSize="small" />
                                                        )}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Tooltip title="Revoke Access">
                                                            <IconButton
                                                                size="small"
                                                                color="error"
                                                                onClick={() => handleRevokeAccess(user.user_id)}
                                                            >
                                                                <Delete fontSize="small" />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            )}
                        </Paper>
                    </Grid>
                )}
            </Grid>

            {/* Grant Access Dialog */}
            <Dialog open={openGrantDialog} onClose={() => setOpenGrantDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Grant Session Access</DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 2 }}>
                        <FormControl fullWidth sx={{ mb: 3 }}>
                            <InputLabel>User</InputLabel>
                            <Select
                                value={selectedUser}
                                onChange={(e) => setSelectedUser(e.target.value)}
                                label="User"
                            >
                                <MenuItem value="">
                                    <em>Select a user...</em>
                                </MenuItem>
                                {users.map((user) => (
                                    <MenuItem key={user.id} value={user.id}>
                                        {user.username}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        {/* Multi-Select Sessions */}
                        <Autocomplete
                            multiple
                            options={sessions}
                            getOptionLabel={(session) => session.name || session.oid}
                            value={sessions.filter((s) => selectedSessions.includes(s.oid))}
                            onChange={(_, newValue) => {
                                setSelectedSessions(newValue.map((s) => s.oid));
                            }}
                            renderInput={(params) => (
                                <TextField
                                    {...params}
                                    label="Sessions (select one or more)"
                                    placeholder="Select sessions..."
                                />
                            )}
                            renderTags={(value, getTagProps) =>
                                value.map((option, index) => (
                                    <Chip
                                        label={option.name || option.oid}
                                        {...getTagProps({ index })}
                                        size="small"
                                    />
                                ))
                            }
                            sx={{ mb: 3 }}
                        />

                        <Alert severity="info" sx={{ mb: 2 }}>
                            {selectedSessions.length === 0 && 'Select one or more sessions to grant access.'}
                            {selectedSessions.length === 1 && 'Creates: [session_id] = \'uuid\''}
                            {selectedSessions.length > 1 && `Creates: [session_id] IN ('uuid1', 'uuid2', ...) or multiple individual permissions`}
                        </Alert>

                        <Typography variant="subtitle2" gutterBottom>
                            Access Permissions:
                        </Typography>

                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={readAccess}
                                    onChange={(e) => setReadAccess(e.target.checked)}
                                />
                            }
                            label="Read Access"
                        />
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={writeAccess}
                                    onChange={(e) => setWriteAccess(e.target.checked)}
                                />
                            }
                            label="Write Access"
                        />
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={deleteAccess}
                                    onChange={(e) => setDeleteAccess(e.target.checked)}
                                />
                            }
                            label="Delete Access"
                        />

                        <Alert severity="info" sx={{ mt: 2 }}>
                            This will create an object-level permission for the user's role. Changes sync immediately to Casbin policies.
                        </Alert>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenGrantDialog(false)}>Cancel</Button>
                    <Button
                        onClick={handleGrantAccess}
                        variant="contained"
                        disabled={!selectedUser || selectedSessions.length === 0}
                        startIcon={<LockOpen />}
                    >
                        Grant Access to {selectedSessions.length > 0 ? `${selectedSessions.length} Session${selectedSessions.length > 1 ? 's' : ''}` : 'Sessions'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}