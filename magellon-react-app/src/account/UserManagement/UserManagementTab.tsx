'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Grid,
    Card,
    CardContent,
    Typography,
    TextField,
    Button,
    Avatar,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    InputAdornment,
    IconButton,
    Divider,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination,
    CircularProgress,
} from '@mui/material';
import {
    Edit,
    Save,
    Cancel,
    Lock,
    Email,
    Person,
    Visibility,
    VisibilityOff,
    CheckCircle,
    Security,
    VpnKey,
    Shield,
    Search,
    Add,
    Delete,
    AssignmentInd,
} from '@mui/icons-material';

// FIXED: Use relative paths that match your project structure
import { userApiService } from './userApi';
import { RoleAPI, UserRoleAPI, PermissionAPI } from './rbacApi';
import RoleAssignmentDialog from './RoleAssignmentDialog';

interface UserManagementTabProps {
    currentUser: any;
    isAdmin: boolean;
    onUpdate: () => void;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
    adminMode?: boolean;
    isSuperUser?: boolean;  // ADDED: Super user flag
}

export default function UserManagementTab({
                                              currentUser,
                                              isAdmin,
                                              onUpdate,
                                              showSnackbar,
                                              adminMode = false,
                                              isSuperUser = false,  // ADDED: Default to false
                                          }: UserManagementTabProps) {
    const [editMode, setEditMode] = useState(false);
    const [loading, setLoading] = useState(false);
    const [users, setUsers] = useState<any[]>([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);

    // Form data
    const [formData, setFormData] = useState({
        username: currentUser?.username || '',
        email: currentUser?.email || '',
    });

    // Password dialog
    const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
    const [passwordData, setPasswordData] = useState({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
    });
    const [showPasswords, setShowPasswords] = useState({
        current: false,
        new: false,
        confirm: false,
    });

    // Permissions
    const [userPermissions, setUserPermissions] = useState<any>(null);

    // Role assignment
    const [roleDialogOpen, setRoleDialogOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState<any>(null);

    // Create user dialog
    const [createUserDialogOpen, setCreateUserDialogOpen] = useState(false);
    const [newUserData, setNewUserData] = useState({
        username: '',
        password: '',
        email: '',
        active: true,
    });

    useEffect(() => {
        if (currentUser) {  // FIXED: Only load if currentUser exists
            loadData();
        }
    }, [adminMode, currentUser]);

    const loadData = async () => {
        if (adminMode) {
            loadUsers();
        } else {
            loadUserPermissions();
        }
    };

    const loadUsers = async () => {
        setLoading(true);
        try {
            const usersData = await userApiService.getUsers();
            setUsers(usersData);
        } catch (error) {
            console.error('Failed to load users:', error);
            showSnackbar('Failed to load users', 'error');
        } finally {
            setLoading(false);
        }
    };

    const loadUserPermissions = async () => {
        if (!currentUser?.id) {
            console.error('Cannot load permissions: currentUser.id is missing');
            return;
        }

        setLoading(true);
        try {
            const permissions = await PermissionAPI.getUserPermissionsSummary(currentUser.id);
            setUserPermissions(permissions);
        } catch (error) {
            console.error('Failed to load permissions:', error);
            // Don't show error for super user as they don't need database permissions
            if (!isSuperUser) {
                showSnackbar('Failed to load permissions', 'error');
            }
        } finally {
            setLoading(false);
        }
    };

    const handleSaveProfile = async () => {
        setLoading(true);
        try {
            await userApiService.updateUser({
                oid: currentUser.id,
                username: formData.username,
            });
            showSnackbar('Profile updated successfully', 'success');
            setEditMode(false);
            onUpdate();
        } catch (error: any) {
            showSnackbar('Failed to update profile: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleChangePassword = async () => {
        if (passwordData.newPassword !== passwordData.confirmPassword) {
            showSnackbar('Passwords do not match', 'error');
            return;
        }

        if (passwordData.newPassword.length < 6) {
            showSnackbar('Password must be at least 6 characters', 'error');
            return;
        }

        setLoading(true);
        try {
            await userApiService.changePassword(
                currentUser.id,
                passwordData.currentPassword,
                passwordData.newPassword
            );
            showSnackbar('Password changed successfully', 'success');
            setPasswordDialogOpen(false);
            setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
        } catch (error: any) {
            showSnackbar('Failed to change password: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateUser = async () => {
        setLoading(true);
        try {
            await userApiService.createUser(newUserData);
            showSnackbar('User created successfully', 'success');
            setCreateUserDialogOpen(false);
            setNewUserData({ username: '', password: '', email: '', active: true });
            loadUsers();
        } catch (error: any) {
            showSnackbar('Failed to create user: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteUser = async (userId: string) => {
        if (!confirm('Are you sure you want to delete this user?')) return;

        setLoading(true);
        try {
            await userApiService.deleteUser(userId);
            showSnackbar('User deleted successfully', 'success');
            loadUsers();
        } catch (error: any) {
            showSnackbar('Failed to delete user: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const openRoleDialog = (user: any) => {
        setSelectedUser(user);
        setRoleDialogOpen(true);
    };

    const filteredUsers = users.filter(
        (user) =>
            user.username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            user.email?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Admin Mode: User Management View
    if (adminMode) {
        return (
            <Box>
                {/* Header with Search and Add */}
                <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
                    <TextField
                        fullWidth
                        placeholder="Search users..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <Search />
                                </InputAdornment>
                            ),
                        }}
                    />
                    <Button
                        variant="contained"
                        startIcon={<Add />}
                        onClick={() => setCreateUserDialogOpen(true)}
                    >
                        Add User
                    </Button>
                </Box>

                {/* Users Table */}
                {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>User</TableCell>
                                        <TableCell>Email</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Created</TableCell>
                                        <TableCell align="right">Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {filteredUsers
                                        .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                                        .map((user) => (
                                            <TableRow key={user.id || user.oid} hover>
                                                <TableCell>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                        <Avatar>{user.username?.charAt(0).toUpperCase()}</Avatar>
                                                        <Typography>{user.username}</Typography>
                                                    </Box>
                                                </TableCell>
                                                <TableCell>{user.email || 'N/A'}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={user.active ? 'Active' : 'Inactive'}
                                                        color={user.active ? 'success' : 'default'}
                                                        size="small"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    {user.created_date ? new Date(user.created_date).toLocaleDateString() : 'N/A'}
                                                </TableCell>
                                                <TableCell align="right">
                                                    <IconButton size="small" onClick={() => openRoleDialog(user)}>
                                                        <AssignmentInd />
                                                    </IconButton>
                                                    <IconButton size="small" onClick={() => handleDeleteUser(user.id || user.oid)}>
                                                        <Delete />
                                                    </IconButton>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        <TablePagination
                            component="div"
                            count={filteredUsers.length}
                            page={page}
                            onPageChange={(_, newPage) => setPage(newPage)}
                            rowsPerPage={rowsPerPage}
                            onRowsPerPageChange={(e) => {
                                setRowsPerPage(parseInt(e.target.value, 10));
                                setPage(0);
                            }}
                            rowsPerPageOptions={[5, 10, 25]}
                        />
                    </>
                )}

                {/* Create User Dialog */}
                <Dialog open={createUserDialogOpen} onClose={() => setCreateUserDialogOpen(false)} maxWidth="sm" fullWidth>
                    <DialogTitle>Create New User</DialogTitle>
                    <DialogContent>
                        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <TextField
                                fullWidth
                                label="Username"
                                value={newUserData.username}
                                onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                            />
                            <TextField
                                fullWidth
                                label="Password"
                                type="password"
                                value={newUserData.password}
                                onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                            />
                            <TextField
                                fullWidth
                                label="Email"
                                type="email"
                                value={newUserData.email}
                                onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                            />
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setCreateUserDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreateUser} variant="contained">
                            Create
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Role Assignment Dialog */}
                {selectedUser && (
                    <RoleAssignmentDialog
                        open={roleDialogOpen}
                        user={selectedUser}
                        onClose={() => {
                            setRoleDialogOpen(false);
                            setSelectedUser(null);
                        }}
                        onSuccess={() => {
                            showSnackbar('Roles updated successfully', 'success');
                            loadUsers();
                        }}
                    />
                )}
            </Box>
        );
    }

    // Regular Mode: My Profile View
    return (
        <Box>
            <Grid container spacing={3}>
                {/* Profile Card */}
                <Grid item xs={12}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                                <Typography variant="h6">Profile Information</Typography>
                                {!editMode ? (
                                    <Button startIcon={<Edit />} onClick={() => setEditMode(true)} variant="outlined">
                                        Edit
                                    </Button>
                                ) : (
                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                        <Button
                                            startIcon={<Cancel />}
                                            onClick={() => {
                                                setEditMode(false);
                                                setFormData({
                                                    username: currentUser?.username || '',
                                                    email: currentUser?.email || '',
                                                });
                                            }}
                                        >
                                            Cancel
                                        </Button>
                                        <Button
                                            startIcon={<Save />}
                                            onClick={handleSaveProfile}
                                            variant="contained"
                                            disabled={loading}
                                        >
                                            Save
                                        </Button>
                                    </Box>
                                )}
                            </Box>

                            <Grid container spacing={2}>
                                <Grid item xs={12} md={6}>
                                    <TextField
                                        fullWidth
                                        label="Username"
                                        value={formData.username}
                                        onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                        disabled={!editMode}
                                        InputProps={{
                                            startAdornment: (
                                                <InputAdornment position="start">
                                                    <Person />
                                                </InputAdornment>
                                            ),
                                        }}
                                    />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <TextField
                                        fullWidth
                                        label="Email"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                        disabled={!editMode}
                                        InputProps={{
                                            startAdornment: (
                                                <InputAdornment position="start">
                                                    <Email />
                                                </InputAdornment>
                                            ),
                                        }}
                                    />
                                </Grid>
                            </Grid>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Security Card */}
                <Grid item xs={12}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Security
                            </Typography>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    <Typography variant="subtitle2">Password</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Last changed: Never
                                    </Typography>
                                </Box>
                                <Button
                                    variant="outlined"
                                    startIcon={<Lock />}
                                    onClick={() => setPasswordDialogOpen(true)}
                                >
                                    Change Password
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Permissions Card */}
                <Grid item xs={12}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                My Permissions
                            </Typography>
                            <Divider sx={{ my: 2 }} />

                            {loading ? (
                                <CircularProgress />
                            ) : (
                                <>
                                    {/* Roles */}
                                    <Box sx={{ mb: 3 }}>
                                        <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Security /> Roles
                                        </Typography>
                                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                                            {userPermissions?.roles?.map((role: any) => (
                                                <Chip
                                                    key={role.oid}
                                                    label={role.name}
                                                    color={role.is_administrative ? 'error' : 'primary'}
                                                />
                                            ))}
                                            {(!userPermissions?.roles || userPermissions.roles.length === 0) && (
                                                <Typography variant="body2" color="text.secondary">
                                                    No roles assigned
                                                </Typography>
                                            )}
                                        </Box>
                                    </Box>

                                    {/* Action Permissions */}
                                    <Box sx={{ mb: 3 }}>
                                        <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <VpnKey /> Action Permissions
                                        </Typography>
                                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                                            {userPermissions?.action_permissions?.map((perm: any, index: number) => (
                                                <Chip key={index} label={perm.action_id || perm} size="small" variant="outlined" />
                                            ))}
                                            {(!userPermissions?.action_permissions || userPermissions.action_permissions.length === 0) && (
                                                <Typography variant="body2" color="text.secondary">
                                                    No action permissions
                                                </Typography>
                                            )}
                                        </Box>
                                    </Box>

                                    {/* Navigation Permissions */}
                                    <Box>
                                        <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Shield /> Navigation Access
                                        </Typography>
                                        <List dense>
                                            {userPermissions?.navigation_permissions?.map((perm: any, index: number) => (
                                                <ListItem key={index}>
                                                    <ListItemIcon>
                                                        <CheckCircle color="success" fontSize="small" />
                                                    </ListItemIcon>
                                                    <ListItemText primary={perm.path || perm.item_path || perm} />
                                                </ListItem>
                                            ))}
                                            {(!userPermissions?.navigation_permissions || userPermissions.navigation_permissions.length === 0) && (
                                                <Typography variant="body2" color="text.secondary">
                                                    No navigation permissions
                                                </Typography>
                                            )}
                                        </List>
                                    </Box>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Change Password Dialog */}
            <Dialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Change Password</DialogTitle>
                <DialogContent>
                    <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            fullWidth
                            label="Current Password"
                            type={showPasswords.current ? 'text' : 'password'}
                            value={passwordData.currentPassword}
                            onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton
                                            onClick={() => setShowPasswords({ ...showPasswords, current: !showPasswords.current })}
                                        >
                                            {showPasswords.current ? <VisibilityOff /> : <Visibility />}
                                        </IconButton>
                                    </InputAdornment>
                                ),
                            }}
                        />
                        <TextField
                            fullWidth
                            label="New Password"
                            type={showPasswords.new ? 'text' : 'password'}
                            value={passwordData.newPassword}
                            onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton
                                            onClick={() => setShowPasswords({ ...showPasswords, new: !showPasswords.new })}
                                        >
                                            {showPasswords.new ? <VisibilityOff /> : <Visibility />}
                                        </IconButton>
                                    </InputAdornment>
                                ),
                            }}
                        />
                        <TextField
                            fullWidth
                            label="Confirm Password"
                            type={showPasswords.confirm ? 'text' : 'password'}
                            value={passwordData.confirmPassword}
                            onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton
                                            onClick={() => setShowPasswords({ ...showPasswords, confirm: !showPasswords.confirm })}
                                        >
                                            {showPasswords.confirm ? <VisibilityOff /> : <Visibility />}
                                        </IconButton>
                                    </InputAdornment>
                                ),
                            }}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPasswordDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleChangePassword} variant="contained" disabled={loading}>
                        Change Password
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
