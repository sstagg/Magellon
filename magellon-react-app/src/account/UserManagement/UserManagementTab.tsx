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
    FormControl,
    InputLabel,
    Select,
    MenuItem,
} from '@mui/material';
import {
    Edit,
    Save,
    Cancel,
    Lock,
    LockOpen,
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
    Refresh,
    Block,
    AdminPanelSettings,
} from '@mui/icons-material';

// FIXED: Use relative paths that match your project structure
import { userApiService } from './userApi';
import { RoleAPI, UserRoleAPI, PermissionAPI } from './rbacApi';
import RoleAssignmentDialog from './RoleAssignmentDialog';
import ChangePasswordDialog from './ChangePasswordDialog';

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
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [totalUsers, setTotalUsers] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);

    // Form data
    const [formData, setFormData] = useState({
        username: currentUser?.username || '',
        email: currentUser?.email || '',
    });

    // Password dialog
    const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);

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

    // Change password dialog (for admin changing other users' passwords)
    const [changePasswordDialogOpen, setChangePasswordDialogOpen] = useState(false);
    const [userToChangePassword, setUserToChangePassword] = useState<any>(null);

    useEffect(() => {
        if (currentUser) {  // FIXED: Only load if currentUser exists
            loadData();
        }
    }, [adminMode, currentUser, statusFilter]);

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
            const includeInactive = statusFilter === 'all' || statusFilter === 'inactive';
            const usersData = await userApiService.getUsers({ include_inactive: includeInactive });

            // Load roles for each user
            const usersWithRoles = await Promise.all(
                usersData.map(async (user) => {
                    try {
                        const roles = await UserRoleAPI.getUserRoles(user.id || user.oid);
                        return { ...user, roles, rolesLoadError: false };
                    } catch (error) {
                        // Silently handle - roles will show as empty with error indicator
                        return { ...user, roles: [], rolesLoadError: true };
                    }
                })
            );

            setUsers(usersWithRoles);

            // Get total user count
            try {
                const stats = await userApiService.getUserStats(includeInactive);
                setTotalUsers(stats.total_users);
            } catch (error) {
                console.error('Failed to load user stats:', error);
            }
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

    const openChangePasswordDialog = (user: any) => {
        setUserToChangePassword(user);
        setChangePasswordDialogOpen(true);
    };

    const handleActivateUser = async (userId: string) => {
        setLoading(true);
        try {
            await userApiService.activateUser(userId);
            showSnackbar('User activated successfully', 'success');
            loadUsers();
        } catch (error: any) {
            showSnackbar('Failed to activate user: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleDeactivateUser = async (userId: string) => {
        setLoading(true);
        try {
            await userApiService.deactivateUser(userId);
            showSnackbar('User deactivated successfully', 'success');
            loadUsers();
        } catch (error: any) {
            showSnackbar('Failed to deactivate user: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
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
                {/* Statistics Cards */}
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'primary.main' }}>
                                        <Person />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{totalUsers}</Typography>
                                        <Typography variant="body2" color="text.secondary">Total Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'success.main' }}>
                                        <CheckCircle />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{users.filter(u => u.active).length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Active Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'error.main' }}>
                                        <Block />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{users.filter(u => !u.active).length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Inactive Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'warning.main' }}>
                                        <AdminPanelSettings />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{users.filter(u => u.roles && u.roles.some((r: any) => r.is_administrative)).length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Admin Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Filters, Search and Add */}
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
                    <FormControl sx={{ minWidth: 150 }}>
                        <InputLabel>Status</InputLabel>
                        <Select
                            value={statusFilter}
                            label="Status"
                            onChange={(e) => setStatusFilter(e.target.value)}
                        >
                            <MenuItem value="all">All Users</MenuItem>
                            <MenuItem value="active">Active</MenuItem>
                            <MenuItem value="inactive">Inactive</MenuItem>
                        </Select>
                    </FormControl>
                    <Button
                        variant="outlined"
                        startIcon={<Refresh />}
                        onClick={() => loadUsers()}
                    >
                        Refresh
                    </Button>
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
                                        <TableCell>Roles</TableCell>
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
                                                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                                                        {user.rolesLoadError ? (
                                                            <Chip
                                                                label="Error loading roles"
                                                                size="small"
                                                                color="warning"
                                                                variant="outlined"
                                                                onClick={() => openRoleDialog(user)}
                                                                sx={{ cursor: 'pointer' }}
                                                            />
                                                        ) : user.roles && user.roles.length > 0 ? (
                                                            <>
                                                                {user.roles.map((role: any) => (
                                                                    <Chip
                                                                        key={role.role_id}
                                                                        label={role.role_name}
                                                                        size="small"
                                                                        color={role.is_administrative ? 'error' : 'primary'}
                                                                        variant={role.is_administrative ? 'filled' : 'outlined'}
                                                                        icon={role.is_administrative ? <Security fontSize="small" /> : undefined}
                                                                        onClick={() => openRoleDialog(user)}
                                                                        sx={{ cursor: 'pointer' }}
                                                                    />
                                                                ))}
                                                                <IconButton
                                                                    size="small"
                                                                    onClick={() => openRoleDialog(user)}
                                                                    title="Manage Roles"
                                                                    sx={{ ml: 0.5 }}
                                                                >
                                                                    <Edit fontSize="small" />
                                                                </IconButton>
                                                            </>
                                                        ) : (
                                                            <Chip
                                                                label="No roles - Click to assign"
                                                                size="small"
                                                                variant="outlined"
                                                                onClick={() => openRoleDialog(user)}
                                                                sx={{ cursor: 'pointer' }}
                                                                icon={<Add fontSize="small" />}
                                                            />
                                                        )}
                                                    </Box>
                                                </TableCell>
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
                                                    {user.active ? (
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleDeactivateUser(user.id || user.oid)}
                                                            title="Deactivate User"
                                                            color="warning"
                                                        >
                                                            <Block />
                                                        </IconButton>
                                                    ) : (
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleActivateUser(user.id || user.oid)}
                                                            title="Activate User"
                                                            color="success"
                                                        >
                                                            <LockOpen />
                                                        </IconButton>
                                                    )}
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => openChangePasswordDialog(user)}
                                                        title="Change Password"
                                                    >
                                                        <Lock />
                                                    </IconButton>
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => openRoleDialog(user)}
                                                        title="Assign Roles"
                                                    >
                                                        <AssignmentInd />
                                                    </IconButton>
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => handleDeleteUser(user.id || user.oid)}
                                                        title="Delete User"
                                                        color="error"
                                                    >
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

                {/* Change Password Dialog (Admin changing other users' passwords) */}
                {userToChangePassword && (
                    <ChangePasswordDialog
                        open={changePasswordDialogOpen}
                        userId={userToChangePassword.id || userToChangePassword.oid}
                        username={userToChangePassword.username}
                        isOwnPassword={false}
                        onClose={() => {
                            setChangePasswordDialogOpen(false);
                            setUserToChangePassword(null);
                        }}
                        onSuccess={() => {
                            showSnackbar('Password changed successfully', 'success');
                            setChangePasswordDialogOpen(false);
                            setUserToChangePassword(null);
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

            {/* Change Password Dialog (User changing own password) */}
            <ChangePasswordDialog
                open={passwordDialogOpen}
                userId={currentUser?.id}
                username={currentUser?.username}
                isOwnPassword={true}
                onClose={() => setPasswordDialogOpen(false)}
                onSuccess={() => {
                    showSnackbar('Password changed successfully', 'success');
                    setPasswordDialogOpen(false);
                }}
            />
        </Box>
    );
}
