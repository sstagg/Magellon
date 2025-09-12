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
    CardActions,
    Switch,
    FormControlLabel,
    Avatar,
    Menu,
    ListItemIcon,
    ListItemText,
    Divider,
    Badge,
    Stack,
    useTheme,
    alpha,
    TablePagination,
    InputAdornment,
    Snackbar
} from '@mui/material';
import {
    PersonAdd,
    Edit,
    Delete,
    MoreVert,
    Lock,
    LockOpen,
    Email,
    Person,
    AdminPanelSettings,
    SupervisorAccount,
    Visibility,
    VisibilityOff,
    Search,
    FilterList,
    Download,
    Upload,
    Refresh
} from '@mui/icons-material';
import { User, UserPlus, Shield, Mail, Calendar, CheckCircle, XCircle } from 'lucide-react';

interface UserData {
    id: string;
    username: string;
    email: string;
    firstName: string;
    lastName: string;
    role: 'ROLE_ADMIN' | 'ROLE_USER';
    isActive: boolean;
    lastLogin: Date | null;
    createdAt: Date;
    permissions: string[];
    department?: string;
    phoneNumber?: string;
}

interface UserFormData {
    username: string;
    email: string;
    firstName: string;
    lastName: string;
    password: string;
    confirmPassword: string;
    role: 'ROLE_ADMIN' | 'ROLE_USER';
    isActive: boolean;
    department: string;
    phoneNumber: string;
    permissions: string[];
}

const UserManagementPage: React.FC = () => {
    const theme = useTheme();
    const [users, setUsers] = useState<UserData[]>([]);
    const [filteredUsers, setFilteredUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [roleFilter, setRoleFilter] = useState<string>('all');
    const [statusFilter, setStatusFilter] = useState<string>('all');

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
        email: '',
        firstName: '',
        lastName: '',
        password: '',
        confirmPassword: '',
        role: 'ROLE_USER',
        isActive: true,
        department: '',
        phoneNumber: '',
        permissions: []
    });

    // UI state
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

    // Available permissions for Magellon
    const availablePermissions = [
        'view_images',
        'import_data',
        'export_data',
        'manage_sessions',
        'run_processing',
        'manage_settings',
        'view_logs',
        'manage_users'
    ];

    // Mock data - replace with actual API calls
    useEffect(() => {
        loadUsers();
    }, []);

    useEffect(() => {
        filterUsers();
    }, [users, searchTerm, roleFilter, statusFilter]);

    const loadUsers = async () => {
        setLoading(true);
        try {
            // Mock API call - replace with actual implementation
            const mockUsers: UserData[] = [
                {
                    id: '1',
                    username: 'admin',
                    email: 'admin@magellon.org',
                    firstName: 'System',
                    lastName: 'Administrator',
                    role: 'ROLE_ADMIN',
                    isActive: true,
                    lastLogin: new Date(),
                    createdAt: new Date('2024-01-01'),
                    permissions: availablePermissions,
                    department: 'IT'
                },
                {
                    id: '2',
                    username: 'jdoe',
                    email: 'john.doe@university.edu',
                    firstName: 'John',
                    lastName: 'Doe',
                    role: 'ROLE_USER',
                    isActive: true,
                    lastLogin: new Date(Date.now() - 86400000),
                    createdAt: new Date('2024-02-15'),
                    permissions: ['view_images', 'import_data', 'export_data'],
                    department: 'Biology',
                    phoneNumber: '+1-555-0123'
                },
                {
                    id: '3',
                    username: 'msmith',
                    email: 'mary.smith@university.edu',
                    firstName: 'Mary',
                    lastName: 'Smith',
                    role: 'ROLE_USER',
                    isActive: false,
                    lastLogin: null,
                    createdAt: new Date('2024-03-01'),
                    permissions: ['view_images'],
                    department: 'Chemistry'
                }
            ];
            setUsers(mockUsers);
        } catch (error) {
            setSnackbar({ open: true, message: 'Failed to load users', severity: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const filterUsers = () => {
        let filtered = users;

        // Search filter
        if (searchTerm) {
            filtered = filtered.filter(user =>
                user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                user.firstName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                user.lastName.toLowerCase().includes(searchTerm.toLowerCase())
            );
        }

        // Role filter
        if (roleFilter !== 'all') {
            filtered = filtered.filter(user => user.role === roleFilter);
        }

        // Status filter
        if (statusFilter !== 'all') {
            filtered = filtered.filter(user =>
                statusFilter === 'active' ? user.isActive : !user.isActive
            );
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

            // Mock API call - replace with actual implementation
            const newUser: UserData = {
                id: Date.now().toString(),
                ...formData,
                lastLogin: null,
                createdAt: new Date()
            };

            setUsers(prev => [...prev, newUser]);
            setIsCreateDialogOpen(false);
            resetForm();
            setSnackbar({ open: true, message: 'User created successfully', severity: 'success' });
        } catch (error) {
            setSnackbar({ open: true, message: 'Failed to create user', severity: 'error' });
        }
    };

    const handleUpdateUser = async () => {
        if (!selectedUser) return;

        try {
            // Mock API call - replace with actual implementation
            const updatedUser: UserData = {
                ...selectedUser,
                ...formData,
                id: selectedUser.id,
                createdAt: selectedUser.createdAt,
                lastLogin: selectedUser.lastLogin
            };

            setUsers(prev => prev.map(user => user.id === selectedUser.id ? updatedUser : user));
            setIsEditDialogOpen(false);
            setSelectedUser(null);
            resetForm();
            setSnackbar({ open: true, message: 'User updated successfully', severity: 'success' });
        } catch (error) {
            setSnackbar({ open: true, message: 'Failed to update user', severity: 'error' });
        }
    };

    const handleDeleteUser = async () => {
        if (!selectedUser) return;

        try {
            // Mock API call - replace with actual implementation
            setUsers(prev => prev.filter(user => user.id !== selectedUser.id));
            setIsDeleteDialogOpen(false);
            setSelectedUser(null);
            setSnackbar({ open: true, message: 'User deleted successfully', severity: 'success' });
        } catch (error) {
            setSnackbar({ open: true, message: 'Failed to delete user', severity: 'error' });
        }
    };

    const handleToggleUserStatus = async (userId: string) => {
        try {
            // Mock API call - replace with actual implementation
            setUsers(prev => prev.map(user =>
                user.id === userId ? { ...user, isActive: !user.isActive } : user
            ));
            setSnackbar({ open: true, message: 'User status updated', severity: 'success' });
        } catch (error) {
            setSnackbar({ open: true, message: 'Failed to update user status', severity: 'error' });
        }
    };

    const resetForm = () => {
        setFormData({
            username: '',
            email: '',
            firstName: '',
            lastName: '',
            password: '',
            confirmPassword: '',
            role: 'ROLE_USER',
            isActive: true,
            department: '',
            phoneNumber: '',
            permissions: []
        });
    };

    const openEditDialog = (user: UserData) => {
        setSelectedUser(user);
        setFormData({
            username: user.username,
            email: user.email,
            firstName: user.firstName,
            lastName: user.lastName,
            password: '',
            confirmPassword: '',
            role: user.role,
            isActive: user.isActive,
            department: user.department || '',
            phoneNumber: user.phoneNumber || '',
            permissions: user.permissions
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

    const getRoleColor = (role: string) => {
        return role === 'ROLE_ADMIN' ? 'primary' : 'default';
    };

    const getRoleIcon = (role: string) => {
        return role === 'ROLE_ADMIN' ? <AdminPanelSettings /> : <Person />;
    };

    const formatLastLogin = (lastLogin: Date | null) => {
        if (!lastLogin) return 'Never';
        return lastLogin.toLocaleDateString() + ' ' + lastLogin.toLocaleTimeString();
    };

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
                                Manage user accounts, roles, and permissions for Magellon
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
                                        <Typography variant="h4">{users.length}</Typography>
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
                                        <Typography variant="h4">{users.filter(u => u.isActive).length}</Typography>
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
                                    <Avatar sx={{ bgcolor: 'warning.main' }}>
                                        <AdminPanelSettings />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h4">{users.filter(u => u.role === 'ROLE_ADMIN').length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Administrators</Typography>
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
                                        <Typography variant="h4">{users.filter(u => !u.isActive).length}</Typography>
                                        <Typography variant="body2" color="text.secondary">Inactive Users</Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Filters and Search */}
                <Paper sx={{ p: 2, mb: 3 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} md={4}>
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
                        <Grid item xs={12} sm={6} md={2}>
                            <FormControl fullWidth>
                                <InputLabel>Role</InputLabel>
                                <Select
                                    value={roleFilter}
                                    onChange={(e) => setRoleFilter(e.target.value)}
                                    label="Role"
                                >
                                    <MenuItem value="all">All Roles</MenuItem>
                                    <MenuItem value="ROLE_ADMIN">Administrator</MenuItem>
                                    <MenuItem value="ROLE_USER">User</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12} sm={6} md={2}>
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
                        <Grid item xs={12} md={4}>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Button startIcon={<Refresh />} onClick={loadUsers}>
                                    Refresh
                                </Button>
                                <Button startIcon={<Download />}>
                                    Export
                                </Button>
                                <Button startIcon={<Upload />}>
                                    Import
                                </Button>
                            </Box>
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
                                    <TableCell>Role</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Department</TableCell>
                                    <TableCell>Last Login</TableCell>
                                    <TableCell>Permissions</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {filteredUsers
                                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                                    .map((user) => (
                                        <TableRow key={user.id} hover>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                    <Avatar sx={{ bgcolor: alpha(theme.palette.primary.main, 0.1) }}>
                                                        {user.firstName[0]}{user.lastName[0]}
                                                    </Avatar>
                                                    <Box>
                                                        <Typography variant="subtitle2">
                                                            {user.firstName} {user.lastName}
                                                        </Typography>
                                                        <Typography variant="body2" color="text.secondary">
                                                            @{user.username}
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {user.email}
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    icon={getRoleIcon(user.role)}
                                                    label={user.role === 'ROLE_ADMIN' ? 'Administrator' : 'User'}
                                                    color={getRoleColor(user.role)}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={user.isActive ? 'Active' : 'Inactive'}
                                                    color={user.isActive ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {user.department || '-'}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {formatLastLogin(user.lastLogin)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Badge badgeContent={user.permissions.length} color="primary">
                                                    <Shield size={20} />
                                                </Badge>
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
                                                    <Tooltip title={user.isActive ? 'Deactivate' : 'Activate'}>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleToggleUserStatus(user.id)}
                                                        >
                                                            {user.isActive ? <Lock /> : <LockOpen />}
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
                        onRowsPerPageChange={(e) => setRowsPerPage(parseInt(e.target.value, 10))}
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
                                    label="Email"
                                    type="email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    required
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="First Name"
                                    value={formData.firstName}
                                    onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                                    required
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Last Name"
                                    value={formData.lastName}
                                    onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                                    required
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <FormControl fullWidth>
                                    <InputLabel>Role</InputLabel>
                                    <Select
                                        value={formData.role}
                                        onChange={(e) => setFormData({ ...formData, role: e.target.value as 'ROLE_ADMIN' | 'ROLE_USER' })}
                                        label="Role"
                                    >
                                        <MenuItem value="ROLE_USER">User</MenuItem>
                                        <MenuItem value="ROLE_ADMIN">Administrator</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Department"
                                    value={formData.department}
                                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    label="Phone Number"
                                    value={formData.phoneNumber}
                                    onChange={(e) => setFormData({ ...formData, phoneNumber: e.target.value })}
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <FormControl fullWidth>
                                    <InputLabel>Permissions</InputLabel>
                                    <Select
                                        multiple
                                        value={formData.permissions}
                                        onChange={(e) => setFormData({ ...formData, permissions: e.target.value as string[] })}
                                        renderValue={(selected) => (
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                                {selected.map((value) => (
                                                    <Chip key={value} label={value.replace('_', ' ')} size="small" />
                                                ))}
                                            </Box>
                                        )}
                                    >
                                        {availablePermissions.map((permission) => (
                                            <MenuItem key={permission} value={permission}>
                                                {permission.replace('_', ' ')}
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={formData.isActive}
                                            onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                                        />
                                    }
                                    label="Active User"
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
                            This action cannot be undone. All data associated with this user will be permanently deleted.
                        </Alert>
                        <Typography>
                            Are you sure you want to delete user <strong>{selectedUser?.username}</strong>?
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            User: {selectedUser?.firstName} {selectedUser?.lastName} ({selectedUser?.email})
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