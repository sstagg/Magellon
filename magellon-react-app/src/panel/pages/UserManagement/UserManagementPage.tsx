import React, { useState, useEffect } from 'react';
import {
    Box,
    Container,
    Paper,
    Typography,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Chip,
    IconButton,
    Tooltip,
    Alert,
    Grid,
    Card,
    CardContent,
    Switch,
    FormControlLabel,
    Avatar,
    Menu,
    ListItemIcon,
    ListItemText,
    TablePagination,
    InputAdornment,
    Snackbar,
    CircularProgress,
    useTheme,
    alpha,
    Stack
} from '@mui/material';
import {
    PersonAdd,
    Edit,
    Delete,
    MoreVert,
    Lock,
    LockOpen,
    Person,
    AdminPanelSettings,
    Visibility,
    VisibilityOff,
    Search,
    Refresh
} from '@mui/icons-material';
import { CheckCircle, XCircle } from 'lucide-react';
import { userApiService, ApiUser, CreateUserRequest, UpdateUserRequest } from './userApi';

// Updated interface to match API response
interface UserData {
    id: string;
    username: string;
    active: boolean;
    created_date: Date | null;
    last_modified_date: Date | null;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    change_password_on_first_logon?: boolean;
    object_type?: number;
    access_failed_count?: number;
    lockout_end?: Date | null;
}

interface UserFormData {
    username: string;
    password: string;
    confirmPassword: string;
    active: boolean;
    change_password_on_first_logon: boolean;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    object_type?: number;
}

const UserManagementPage: React.FC = () => {
    const theme = useTheme();
    const [users, setUsers] = useState<UserData[]>([]);
    const [filteredUsers, setFilteredUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [totalUsers, setTotalUsers] = useState(0);

    // Dialog states
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState<UserData | null>(null);

    // Menu state
    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
    const [menuUserId, setMenuUserId] = useState<string | null>(null);

    // Form state
    const [formData, setFormData] = useState<UserFormData>({
        username: '',
        password: '',
        confirmPassword: '',
        active: true,
        change_password_on_first_logon: false,
        omid: undefined,
        ouid: '',
        sync_status: undefined,
        version: '',
        object_type: undefined
    });

    // UI state
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error' | 'info' | 'warning'
    });

    // Load users on component mount and when filters change
    useEffect(() => {
        loadUsers();
    }, [page, rowsPerPage, statusFilter]);

    useEffect(() => {
        filterUsers();
    }, [users, searchTerm]);

    // Convert API user to component user format
    const convertApiUserToUserData = (apiUser: ApiUser): UserData => ({
        id: apiUser.oid,
        username: apiUser.username || '',
        active: apiUser.active || false,
        created_date: apiUser.created_date ? new Date(apiUser.created_date) : null,
        last_modified_date: apiUser.last_modified_date ? new Date(apiUser.last_modified_date) : null,
        omid: apiUser.omid,
        ouid: apiUser.ouid,
        sync_status: apiUser.sync_status,
        version: apiUser.version,
        change_password_on_first_logon: apiUser.change_password_on_first_logon,
        object_type: apiUser.object_type,
        access_failed_count: apiUser.access_failed_count,
        lockout_end: apiUser.lockout_end ? new Date(apiUser.lockout_end) : null
    });

    const loadUsers = async () => {
        setLoading(true);
        try {
            const includeInactive = statusFilter === 'all' || statusFilter === 'inactive';
            const apiUsers = await userApiService.getUsers({
                skip: page * rowsPerPage,
                limit: rowsPerPage,
                include_inactive: includeInactive,
                username: searchTerm || undefined
            });

            const userData = apiUsers.map(convertApiUserToUserData);
            setUsers(userData);

            // Get total count
            const stats = await userApiService.getUserStats(includeInactive);
            setTotalUsers(stats.total_users);

        } catch (error) {
            console.error('Failed to load users:', error);
            setSnackbar({
                open: true,
                message: 'Failed to load users: ' + (error as Error).message,
                severity: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    const filterUsers = () => {
        let filtered = users;

        // Search filter (client-side for loaded data)
        if (searchTerm) {
            filtered = filtered.filter(user =>
                user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (user.ouid && user.ouid.toLowerCase().includes(searchTerm.toLowerCase()))
            );
        }

        // Status filter
        if (statusFilter === 'active') {
            filtered = filtered.filter(user => user.active);
        } else if (statusFilter === 'inactive') {
            filtered = filtered.filter(user => !user.active);
        }

        setFilteredUsers(filtered);
    };

    const handleCreateUser = async () => {
        try {
            // Validation
            if (formData.password !== formData.confirmPassword) {
                setSnackbar({ open: true, message: 'Passwords do not match', severity: 'error' });
                return;
            }

            if (formData.password.length < 6) {
                setSnackbar({ open: true, message: 'Password must be at least 6 characters long', severity: 'error' });
                return;
            }

            const createRequest: CreateUserRequest = {
                username: formData.username,
                password: formData.password,
                active: formData.active,
                change_password_on_first_logon: formData.change_password_on_first_logon,
                omid: formData.omid,
                ouid: formData.ouid,
                sync_status: formData.sync_status,
                version: formData.version,
                object_type: formData.object_type
            };

            await userApiService.createUser(createRequest);
            setIsCreateDialogOpen(false);
            resetForm();
            setSnackbar({ open: true, message: 'User created successfully', severity: 'success' });
            loadUsers(); // Reload users list

        } catch (error) {
            console.error('Failed to create user:', error);
            setSnackbar({
                open: true,
                message: 'Failed to create user: ' + (error as Error).message,
                severity: 'error'
            });
        }
    };

    const handleUpdateUser = async () => {
        if (!selectedUser) return;

        try {
            const updateRequest: UpdateUserRequest = {
                oid: selectedUser.id,
                username: formData.username,
                active: formData.active,
                change_password_on_first_logon: formData.change_password_on_first_logon,
                omid: formData.omid,
                ouid: formData.ouid,
                sync_status: formData.sync_status,
                version: formData.version,
                object_type: formData.object_type
            };

            // Only include password if provided
            if (formData.password) {
                if (formData.password !== formData.confirmPassword) {
                    setSnackbar({ open: true, message: 'Passwords do not match', severity: 'error' });
                    return;
                }
                if (formData.password.length < 6) {
                    setSnackbar({ open: true, message: 'Password must be at least 6 characters long', severity: 'error' });
                    return;
                }
                updateRequest.password = formData.password;
            }

            await userApiService.updateUser(updateRequest);
            setIsEditDialogOpen(false);
            setSelectedUser(null);
            resetForm();
            setSnackbar({ open: true, message: 'User updated successfully', severity: 'success' });
            loadUsers(); // Reload users list

        } catch (error) {
            console.error('Failed to update user:', error);
            setSnackbar({
                open: true,
                message: 'Failed to update user: ' + (error as Error).message,
                severity: 'error'
            });
        }
    };

    const handleDeleteUser = async () => {
        if (!selectedUser) return;

        try {
            await userApiService.deleteUser(selectedUser.id);
            setIsDeleteDialogOpen(false);
            setSelectedUser(null);
            setSnackbar({ open: true, message: 'User deleted successfully', severity: 'success' });
            loadUsers(); // Reload users list

        } catch (error) {
            console.error('Failed to delete user:', error);
            setSnackbar({
                open: true,
                message: 'Failed to delete user: ' + (error as Error).message,
                severity: 'error'
            });
        }
    };

    const handleToggleUserStatus = async (userId: string) => {
        try {
            const user = users.find(u => u.id === userId);
            if (!user) return;

            if (user.active) {
                await userApiService.deactivateUser(userId);
            } else {
                await userApiService.activateUser(userId);
            }

            setSnackbar({ open: true, message: 'User status updated', severity: 'success' });
            loadUsers(); // Reload users list

        } catch (error) {
            console.error('Failed to update user status:', error);
            setSnackbar({
                open: true,
                message: 'Failed to update user status: ' + (error as Error).message,
                severity: 'error'
            });
        }
    };

    const resetForm = () => {
        setFormData({
            username: '',
            password: '',
            confirmPassword: '',
            active: true,
            change_password_on_first_logon: false,
            omid: undefined,
            ouid: '',
            sync_status: undefined,
            version: '',
            object_type: undefined
        });
    };

    const openEditDialog = (user: UserData) => {
        setSelectedUser(user);
        setFormData({
            username: user.username,
            password: '',
            confirmPassword: '',
            active: user.active,
            change_password_on_first_logon: user.change_password_on_first_logon || false,
            omid: user.omid,
            ouid: user.ouid || '',
            sync_status: user.sync_status,
            version: user.version || '',
            object_type: user.object_type
        });
        setIsEditDialogOpen(true);
    };

    const openDeleteDialog = (user: UserData) => {
        setSelectedUser(user);
        setIsDeleteDialogOpen(true);
    };

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, userId: string) => {
        setMenuAnchor(event.currentTarget);
        setMenuUserId(userId);
    };

    const handleMenuClose = () => {
        setMenuAnchor(null);
        setMenuUserId(null);
    };

    const formatDate = (date: Date | null) => {
        if (!date) return 'Never';
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    };

    const activeUsers = users.filter(u => u.active);
    const inactiveUsers = users.filter(u => !u.active);

    return (
        <Container maxWidth="xl">
            <Box sx={{ mt: 4, mb: 4 }}>
                {/* Header */}
                <Paper sx={{ p: 3, mb: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                        <Box>
                            <Typography variant="h4" component="h1" gutterBottom>
                                User Management
                            </Typography>
                            <Typography variant="body1" color="text.secondary">
                                Manage user accounts and permissions for Magellon
                            </Typography>
                        </Box>
                        <Button
                            variant="contained"
                            startIcon={<PersonAdd />}
                            onClick={() => setIsCreateDialogOpen(true)}
                            size="large"
                        >
                            Add User
                        </Button>
                    </Box>
                </Paper>

                {/* Statistics Cards */}
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid item xs={12} sm={6} md={3}>
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
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'success.main' }}>
                                        <CheckCircle />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{activeUsers.length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Active Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'error.main' }}>
                                        <XCircle />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{inactiveUsers.length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Inactive Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ bgcolor: 'warning.main' }}>
                                        <AdminPanelSettings />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{users.filter(u => u.access_failed_count && u.access_failed_count > 0).length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Users with Failed Logins</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Filters and Search */}
                <Paper sx={{ p: 2, mb: 3 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} md={6}>
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
                                    )
                                }}
                            />
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                            <FormControl fullWidth>
                                <InputLabel>Status</InputLabel>
                                <Select
                                    value={statusFilter}
                                    onChange={(e) => setStatusFilter(e.target.value)}
                                    label="Status"
                                >
                                    <MenuItem value="all">All Status</MenuItem>
                                    <MenuItem value="active">Active</MenuItem>
                                    <MenuItem value="inactive">Inactive</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12} md={3}>
                            <Button
                                startIcon={<Refresh />}
                                onClick={loadUsers}
                                disabled={loading}
                                fullWidth
                            >
                                {loading ? 'Loading...' : 'Refresh'}
                            </Button>
                        </Grid>
                    </Grid>
                </Paper>

                {/* Users Table */}
                <Paper>
                    <TableContainer>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>User</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Created</TableCell>
                                    <TableCell>Last Modified</TableCell>
                                    <TableCell>Failed Logins</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {loading ? (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center">
                                            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                                                <CircularProgress />
                                            </Box>
                                        </TableCell>
                                    </TableRow>
                                ) : filteredUsers.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center">
                                            <Typography variant="body1" color="text.secondary" sx={{ p: 3 }}>
                                                No users found
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    filteredUsers.map((user) => (
                                        <TableRow key={user.id} hover>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                    <Avatar sx={{ bgcolor: alpha(theme.palette.primary.main, 0.1) }}>
                                                        {user.username.charAt(0).toUpperCase()}
                                                    </Avatar>
                                                    <Box>
                                                        <Typography variant="subtitle2">
                                                            {user.username}
                                                        </Typography>
                                                        {user.ouid && (
                                                            <Typography variant="body2" color="text.secondary">
                                                                ID: {user.ouid}
                                                            </Typography>
                                                        )}
                                                        {user.version && (
                                                            <Typography variant="caption" color="text.secondary">
                                                                v{user.version}
                                                            </Typography>
                                                        )}
                                                    </Box>
                                                </Box>
                                            </TableCell>
                                            <TableCell>
                                                <Stack spacing={1}>
                                                    <Chip
                                                        label={user.active ? 'Active' : 'Inactive'}
                                                        color={user.active ? 'success' : 'default'}
                                                        size="small"
                                                    />
                                                    {user.change_password_on_first_logon && (
                                                        <Chip
                                                            label="Password Change Required"
                                                            color="warning"
                                                            size="small"
                                                        />
                                                    )}
                                                    {user.lockout_end && new Date(user.lockout_end) > new Date() && (
                                                        <Chip
                                                            label="Locked Out"
                                                            color="error"
                                                            size="small"
                                                        />
                                                    )}
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {formatDate(user.created_date)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {formatDate(user.last_modified_date)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={user.access_failed_count || 0}
                                                    color={user.access_failed_count && user.access_failed_count > 0 ? 'error' : 'default'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell align="right">
                                                <Box sx={{ display: 'flex', gap: 1 }}>
                                                    <Tooltip title="Edit User">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => openEditDialog(user)}
                                                        >
                                                            <Edit />
                                                        </IconButton>
                                                    </Tooltip>
                                                    <Tooltip title={user.active ? 'Deactivate' : 'Activate'}>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleToggleUserStatus(user.id)}
                                                        >
                                                            {user.active ? <Lock /> : <LockOpen />}
                                                        </IconButton>
                                                    </Tooltip>
                                                    <IconButton
                                                        size="small"
                                                        onClick={(e) => handleMenuOpen(e, user.id)}
                                                    >
                                                        <MoreVert />
                                                    </IconButton>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    <TablePagination
                        component="div"
                        count={totalUsers}
                        page={page}
                        onPageChange={(_, newPage) => setPage(newPage)}
                        rowsPerPage={rowsPerPage}
                        onRowsPerPageChange={(e) => {
                            setRowsPerPage(parseInt(e.target.value, 10));
                            setPage(0);
                        }}
                        rowsPerPageOptions={[5, 10, 25, 50]}
                    />
                </Paper>

                {/* Action Menu */}
                <Menu
                    anchorEl={menuAnchor}
                    open={Boolean(menuAnchor)}
                    onClose={handleMenuClose}
                >
                    <MenuItem onClick={() => {
                        const user = users.find(u => u.id === menuUserId);
                        if (user) openEditDialog(user);
                        handleMenuClose();
                    }}>
                        <ListItemIcon><Edit /></ListItemIcon>
                        <ListItemText>Edit User</ListItemText>
                    </MenuItem>
                    <MenuItem onClick={() => {
                        const user = users.find(u => u.id === menuUserId);
                        if (user) openDeleteDialog(user);
                        handleMenuClose();
                    }}>
                        <ListItemIcon><Delete /></ListItemIcon>
                        <ListItemText>Delete User</ListItemText>
                    </MenuItem>
                </Menu>

                {/* Create User Dialog */}
                <Dialog open={isCreateDialogOpen} onClose={() => setIsCreateDialogOpen(false)} maxWidth="md" fullWidth>
                    <DialogTitle>Create New User</DialogTitle>
                    <DialogContent>
                        <Grid container spacing={2} sx={{ mt: 1 }}>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Username"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    required
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="User ID (OUID)"
                                    value={formData.ouid}
                                    onChange={(e) => setFormData({ ...formData, ouid: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Password"
                                    type={showPassword ? 'text' : 'password'}
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    required
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                                                    {showPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        )
                                    }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Confirm Password"
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    value={formData.confirmPassword}
                                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                    required
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end">
                                                    {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        )
                                    }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Version"
                                    value={formData.version}
                                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Object Type"
                                    type="number"
                                    value={formData.object_type || ''}
                                    onChange={(e) => setFormData({ ...formData, object_type: e.target.value ? parseInt(e.target.value) : undefined })}
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={formData.active}
                                            onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                                        />
                                    }
                                    label="Active User"
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={formData.change_password_on_first_logon}
                                            onChange={(e) => setFormData({ ...formData, change_password_on_first_logon: e.target.checked })}
                                        />
                                    }
                                    label="Change Password on First Login"
                                />
                            </Grid>
                        </Grid>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setIsCreateDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreateUser} variant="contained">Create User</Button>
                    </DialogActions>
                </Dialog>

                {/* Edit User Dialog */}
                <Dialog open={isEditDialogOpen} onClose={() => setIsEditDialogOpen(false)} maxWidth="md" fullWidth>
                    <DialogTitle>Edit User</DialogTitle>
                    <DialogContent>
                        <Grid container spacing={2} sx={{ mt: 1 }}>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Username"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    required
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="User ID (OUID)"
                                    value={formData.ouid}
                                    onChange={(e) => setFormData({ ...formData, ouid: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="New Password (leave empty to keep current)"
                                    type={showPassword ? 'text' : 'password'}
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                                                    {showPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        )
                                    }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Confirm New Password"
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    value={formData.confirmPassword}
                                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end">
                                                    {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        )
                                    }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Version"
                                    value={formData.version}
                                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Object Type"
                                    type="number"
                                    value={formData.object_type || ''}
                                    onChange={(e) => setFormData({ ...formData, object_type: e.target.value ? parseInt(e.target.value) : undefined })}
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={formData.active}
                                            onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                                        />
                                    }
                                    label="Active User"
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={formData.change_password_on_first_logon}
                                            onChange={(e) => setFormData({ ...formData, change_password_on_first_logon: e.target.checked })}
                                        />
                                    }
                                    label="Change Password on First Login"
                                />
                            </Grid>
                        </Grid>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setIsEditDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleUpdateUser} variant="contained">Update User</Button>
                    </DialogActions>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={isDeleteDialogOpen} onClose={() => setIsDeleteDialogOpen(false)}>
                    <DialogTitle>Delete User</DialogTitle>
                    <DialogContent>
                        <Alert severity="warning" sx={{ mb: 2 }}>
                            This action cannot be undone. The user will be permanently deleted.
                        </Alert>
                        <Typography>
                            Are you sure you want to delete user <strong>{selectedUser?.username}</strong>?
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            User ID: {selectedUser?.id}
                        </Typography>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setIsDeleteDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleDeleteUser} variant="contained" color="error">
                            Delete User
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Snackbar for notifications */}
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                >
                    <Alert
                        severity={snackbar.severity}
                        onClose={() => setSnackbar({ ...snackbar, open: false })}
                    >
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>
        </Container>
    );
};

export default UserManagementPage;