'use client';

import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Box,
    Typography,
    Switch,
    FormControlLabel,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Tabs,
    Tab,
    Alert,
    CircularProgress,
    Divider,
    Chip,
    Grid,
    IconButton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
} from '@mui/material';
import {
    Save,
    Close,
    AdminPanelSettings,
    Security,
    VpnKey,
    Navigation,
    DataObject,
    Add,
    Delete,
    Edit,
    CheckCircle,
    Cancel,
} from '@mui/icons-material';

import { RoleAPI } from './rbacApi';

interface RoleEditDialogProps {
    open: boolean;
    role: any;
    onClose: () => void;
    onSuccess: () => void;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`role-edit-tabpanel-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
        </div>
    );
}

export default function RoleEditDialog({
    open,
    role,
    onClose,
    onSuccess,
    showSnackbar,
}: RoleEditDialogProps) {
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [tabValue, setTabValue] = useState(0);

    // Basic role info
    const [formData, setFormData] = useState({
        name: '',
        is_administrative: false,
        can_edit_model: false,
        permission_policy: 0,
    });

    // Action Permissions - Initialize with empty arrays to prevent map errors
    const [actionPermissions, setActionPermissions] = useState<any[]>([]);
    const [newActionId, setNewActionId] = useState('');

    // Navigation Permissions - Initialize with empty arrays to prevent map errors
    const [navigationPermissions, setNavigationPermissions] = useState<any[]>([]);
    const [newNavPath, setNewNavPath] = useState('');
    const [newNavState, setNewNavState] = useState(1);

    // Type Permissions - Initialize with empty arrays to prevent map errors
    const [typePermissions, setTypePermissions] = useState<any[]>([]);
    const [newTargetType, setNewTargetType] = useState('');
    const [typeOperations, setTypeOperations] = useState({
        read_state: 1,
        write_state: 1,
        create_state: 1,
        delete_state: 0,
        navigate_state: 1,
    });

    const actionSuggestions = [
        'Export',
        'Import',
        'DeleteAll',
        'BulkEdit',
        'ViewReports',
        'ManageSettings',
        'ExecuteJobs',
        'ViewLogs',
    ];

    const navigationSuggestions = [
        '/admin',
        '/admin/users',
        '/admin/roles',
        '/dashboard',
        '/reports',
        '/settings',
        '/microscopy',
        '/images',
    ];

    const typeSuggestions = [
        'User',
        'Role',
        'Session',
        'Image',
        'Project',
        'Microscope',
        'Job',
        'Report',
    ];

    useEffect(() => {
        if (open && role) {
            // Reset to empty arrays when opening
            setActionPermissions([]);
            setNavigationPermissions([]);
            setTypePermissions([]);
            loadRoleData();
        } else if (!open) {
            // Clear data when closing
            setActionPermissions([]);
            setNavigationPermissions([]);
            setTypePermissions([]);
        }
    }, [open, role]);

    const loadRoleData = async () => {
        setLoading(true);
        try {
            // Get the correct role ID
            const roleId = role.oid || role.Oid;
            console.log('Loading role data for role ID:', roleId);

            if (!roleId) {
                throw new Error('Role ID is missing');
            }

            // Load basic role info
            setFormData({
                name: role.name || role.Name || '',
                is_administrative: role.is_administrative || role.IsAdministrative || false,
                can_edit_model: role.can_edit_model || role.CanEditModel || false,
                permission_policy: role.permission_policy || role.PermissionPolicy || 0,
            });

            // Load action permissions
            const actionUrl = `http://localhost:8000/db/security/permissions/actions/role/${encodeURIComponent(roleId)}`;
            console.log('Fetching action permissions from:', actionUrl);
            const actionResponse = await fetch(actionUrl);
            console.log('Action permissions response status:', actionResponse.status);
            if (actionResponse.ok) {
                const actionPerms = await actionResponse.json();
                console.log('Action permissions loaded:', actionPerms);
                setActionPermissions(Array.isArray(actionPerms) ? actionPerms : []);
            } else {
                const errorText = await actionResponse.text();
                console.warn('Failed to load action permissions:', actionResponse.status, errorText);
                setActionPermissions([]);
            }

            // Load navigation permissions
            const navResponse = await fetch(
                `http://localhost:8000/db/security/permissions/navigation/role/${encodeURIComponent(roleId)}`
            );
            if (navResponse.ok) {
                const navPerms = await navResponse.json();
                setNavigationPermissions(Array.isArray(navPerms) ? navPerms : []);
            } else {
                console.warn('Failed to load navigation permissions:', navResponse.status);
                setNavigationPermissions([]);
            }

            // Load type permissions
            const typeResponse = await fetch(
                `http://localhost:8000/db/security/permissions/types/role/${encodeURIComponent(roleId)}`
            );
            if (typeResponse.ok) {
                const typePerms = await typeResponse.json();
                setTypePermissions(Array.isArray(typePerms) ? typePerms : []);
            } else {
                console.warn('Failed to load type permissions:', typeResponse.status);
                setTypePermissions([]);
            }
        } catch (error: any) {
            console.error('Failed to load role data:', error);
            showSnackbar('Failed to load role data: ' + error.message, 'error');
            // Set empty arrays to prevent map errors
            setActionPermissions([]);
            setNavigationPermissions([]);
            setTypePermissions([]);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveBasicInfo = async () => {
        setSaving(true);
        try {
            const roleId = role.oid || role.Oid;
            await RoleAPI.updateRole({
                oid: roleId,
                ...formData,
            });
            showSnackbar('Role updated successfully', 'success');
            onSuccess();
        } catch (error: any) {
            showSnackbar('Failed to update role: ' + error.message, 'error');
        } finally {
            setSaving(false);
        }
    };

    // Action Permission Handlers
    const handleAddActionPermission = async () => {
        if (!newActionId.trim()) {
            showSnackbar('Please enter an action ID', 'warning');
            return;
        }

        try {
            const roleId = role.oid || role.Oid;
            const response = await fetch('http://localhost:8000/db/security/permissions/actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    role_id: roleId,
                    action_id: newActionId.trim(),
                }),
            });

            if (!response.ok) throw new Error('Failed to add action permission');

            showSnackbar('Action permission added successfully', 'success');
            setNewActionId('');
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to add action permission: ' + error.message, 'error');
        }
    };

    const handleDeleteActionPermission = async (permissionId: string) => {
        try {
            const response = await fetch(
                `http://localhost:8000/db/security/permissions/actions/${permissionId}`,
                { method: 'DELETE' }
            );

            if (!response.ok) throw new Error('Failed to delete action permission');

            showSnackbar('Action permission deleted successfully', 'success');
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to delete action permission: ' + error.message, 'error');
        }
    };

    // Navigation Permission Handlers
    const handleAddNavigationPermission = async () => {
        if (!newNavPath.trim()) {
            showSnackbar('Please enter a navigation path', 'warning');
            return;
        }

        try {
            const roleId = role.oid || role.Oid;
            const response = await fetch('http://localhost:8000/db/security/permissions/navigation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    role_id: roleId,
                    item_path: newNavPath.trim(),
                    navigate_state: newNavState,
                }),
            });

            if (!response.ok) throw new Error('Failed to add navigation permission');

            showSnackbar('Navigation permission added successfully', 'success');
            setNewNavPath('');
            setNewNavState(1);
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to add navigation permission: ' + error.message, 'error');
        }
    };

    const handleDeleteNavigationPermission = async (permissionId: string) => {
        try {
            const response = await fetch(
                `http://localhost:8000/db/security/permissions/navigation/${permissionId}`,
                { method: 'DELETE' }
            );

            if (!response.ok) throw new Error('Failed to delete navigation permission');

            showSnackbar('Navigation permission deleted successfully', 'success');
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to delete navigation permission: ' + error.message, 'error');
        }
    };

    // Type Permission Handlers
    const handleAddTypePermission = async () => {
        if (!newTargetType.trim()) {
            showSnackbar('Please enter a target type', 'warning');
            return;
        }

        try {
            const roleId = role.oid || role.Oid;
            const response = await fetch('http://localhost:8000/db/security/permissions/types', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    role_id: roleId,
                    target_type: newTargetType.trim(),
                    ...typeOperations,
                }),
            });

            if (!response.ok) throw new Error('Failed to add type permission');

            showSnackbar('Type permission added successfully', 'success');
            setNewTargetType('');
            setTypeOperations({
                read_state: 1,
                write_state: 1,
                create_state: 1,
                delete_state: 0,
                navigate_state: 1,
            });
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to add type permission: ' + error.message, 'error');
        }
    };

    const handleDeleteTypePermission = async (permissionId: string) => {
        try {
            const response = await fetch(
                `http://localhost:8000/db/security/permissions/types/${permissionId}`,
                { method: 'DELETE' }
            );

            if (!response.ok) throw new Error('Failed to delete type permission');

            showSnackbar('Type permission deleted successfully', 'success');
            loadRoleData();
        } catch (error: any) {
            showSnackbar('Failed to delete type permission: ' + error.message, 'error');
        }
    };

    const StateChip = ({ value }: { value: number }) => (
        <Chip
            size="small"
            label={value === 1 ? 'Allow' : 'Deny'}
            color={value === 1 ? 'success' : 'error'}
            icon={value === 1 ? <CheckCircle /> : <Cancel />}
        />
    );

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Security color="primary" />
                        <Typography variant="h6">Edit Role - {role?.name}</Typography>
                    </Box>
                    <IconButton onClick={onClose} size="small">
                        <Close />
                    </IconButton>
                </Box>
            </DialogTitle>

            <Divider />

            <DialogContent>
                {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <Box>
                        <Tabs
                            value={tabValue}
                            onChange={(_, newValue) => setTabValue(newValue)}
                            sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
                        >
                            <Tab icon={<Security />} label="Basic Info" iconPosition="start" />
                            <Tab icon={<VpnKey />} label="Actions" iconPosition="start" />
                            <Tab icon={<Navigation />} label="Navigation" iconPosition="start" />
                            <Tab icon={<DataObject />} label="Types" iconPosition="start" />
                        </Tabs>

                        {/* Tab 0: Basic Info */}
                        <TabPanel value={tabValue} index={0}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                <TextField
                                    fullWidth
                                    label="Role Name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    required
                                />

                                <FormControl fullWidth>
                                    <InputLabel>Permission Policy</InputLabel>
                                    <Select
                                        value={formData.permission_policy}
                                        label="Permission Policy"
                                        onChange={(e) =>
                                            setFormData({ ...formData, permission_policy: Number(e.target.value) })
                                        }
                                    >
                                        <MenuItem value={0}>Deny All by Default</MenuItem>
                                        <MenuItem value={1}>Allow All by Default</MenuItem>
                                        <MenuItem value={2}>Read Only by Default</MenuItem>
                                    </Select>
                                </FormControl>

                                <Box>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={formData.is_administrative}
                                                onChange={(e) =>
                                                    setFormData({ ...formData, is_administrative: e.target.checked })
                                                }
                                            />
                                        }
                                        label="Administrative Role"
                                    />
                                    {formData.is_administrative && (
                                        <Alert severity="warning" sx={{ mt: 1 }}>
                                            Administrative roles bypass all permission checks
                                        </Alert>
                                    )}
                                </Box>

                                <Box>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={formData.can_edit_model}
                                                onChange={(e) =>
                                                    setFormData({ ...formData, can_edit_model: e.target.checked })
                                                }
                                            />
                                        }
                                        label="Can Edit Model"
                                    />
                                    {formData.can_edit_model && (
                                        <Alert severity="info" sx={{ mt: 1 }}>
                                            Allows editing system data models
                                        </Alert>
                                    )}
                                </Box>

                                <Button
                                    variant="contained"
                                    startIcon={<Save />}
                                    onClick={handleSaveBasicInfo}
                                    disabled={saving}
                                >
                                    {saving ? 'Saving...' : 'Save Basic Info'}
                                </Button>
                            </Box>
                        </TabPanel>

                        {/* Tab 1: Action Permissions */}
                        <TabPanel value={tabValue} index={1}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                {role.is_administrative && (
                                    <Alert severity="warning">
                                        <strong>Administrative Role:</strong> This role bypasses all permission checks. Permission settings are informational only.
                                    </Alert>
                                )}
                                <Alert severity="info">
                                    Action permissions grant specific operation access like Export, Import, DeleteAll, etc.
                                </Alert>

                                <Box sx={{ display: 'flex', gap: 2 }}>
                                    <TextField
                                        fullWidth
                                        label="Action ID"
                                        value={newActionId}
                                        onChange={(e) => setNewActionId(e.target.value)}
                                        placeholder="e.g., Export, Import, DeleteAll"
                                    />
                                    <Button
                                        variant="contained"
                                        startIcon={<Add />}
                                        onClick={handleAddActionPermission}
                                        sx={{ minWidth: 120 }}
                                    >
                                        Add
                                    </Button>
                                </Box>

                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    {actionSuggestions.map((action) => (
                                        <Chip
                                            key={action}
                                            label={action}
                                            size="small"
                                            onClick={() => setNewActionId(action)}
                                            sx={{ cursor: 'pointer' }}
                                        />
                                    ))}
                                </Box>

                                <Divider />

                                <TableContainer component={Paper} variant="outlined">
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Action ID</TableCell>
                                                <TableCell align="right">Actions</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {!Array.isArray(actionPermissions) || actionPermissions.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={2} align="center">
                                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                                            No action permissions defined
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            ) : (
                                                actionPermissions.map((perm) => (
                                                    <TableRow key={perm.oid}>
                                                        <TableCell>
                                                            <Chip label={perm.action_id} color="primary" size="small" />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <IconButton
                                                                size="small"
                                                                color="error"
                                                                onClick={() => handleDeleteActionPermission(perm.oid)}
                                                            >
                                                                <Delete />
                                                            </IconButton>
                                                        </TableCell>
                                                    </TableRow>
                                                ))
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        </TabPanel>

                        {/* Tab 2: Navigation Permissions */}
                        <TabPanel value={tabValue} index={2}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <Alert severity="info">
                                    Navigation permissions control UI navigation access (menu items, pages, routes).
                                </Alert>

                                <Grid container spacing={2}>
                                    <Grid item xs={12} md={7}>
                                        <TextField
                                            fullWidth
                                            label="Navigation Path"
                                            value={newNavPath}
                                            onChange={(e) => setNewNavPath(e.target.value)}
                                            placeholder="/admin/users"
                                        />
                                    </Grid>
                                    <Grid item xs={12} md={3}>
                                        <FormControl fullWidth>
                                            <InputLabel>Access</InputLabel>
                                            <Select
                                                value={newNavState}
                                                label="Access"
                                                onChange={(e) => setNewNavState(Number(e.target.value))}
                                            >
                                                <MenuItem value={1}>Allow</MenuItem>
                                                <MenuItem value={0}>Deny</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Grid>
                                    <Grid item xs={12} md={2}>
                                        <Button
                                            fullWidth
                                            variant="contained"
                                            startIcon={<Add />}
                                            onClick={handleAddNavigationPermission}
                                            sx={{ height: '56px' }}
                                        >
                                            Add
                                        </Button>
                                    </Grid>
                                </Grid>

                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    {navigationSuggestions.map((path) => (
                                        <Chip
                                            key={path}
                                            label={path}
                                            size="small"
                                            onClick={() => setNewNavPath(path)}
                                            sx={{ cursor: 'pointer' }}
                                        />
                                    ))}
                                </Box>

                                <Divider />

                                <TableContainer component={Paper} variant="outlined">
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Path</TableCell>
                                                <TableCell>Access</TableCell>
                                                <TableCell align="right">Actions</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {!Array.isArray(navigationPermissions) || navigationPermissions.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={3} align="center">
                                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                                            No navigation permissions defined
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            ) : (
                                                navigationPermissions.map((perm) => (
                                                    <TableRow key={perm.oid}>
                                                        <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                                                            {perm.item_path}
                                                        </TableCell>
                                                        <TableCell>
                                                            <StateChip value={perm.navigate_state} />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <IconButton
                                                                size="small"
                                                                color="error"
                                                                onClick={() => handleDeleteNavigationPermission(perm.oid)}
                                                            >
                                                                <Delete />
                                                            </IconButton>
                                                        </TableCell>
                                                    </TableRow>
                                                ))
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        </TabPanel>

                        {/* Tab 3: Type Permissions */}
                        <TabPanel value={tabValue} index={3}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <Alert severity="info">
                                    Type permissions define CRUD operations on classes/types (User, Session, Image, etc.).
                                </Alert>

                                <TextField
                                    fullWidth
                                    label="Target Type"
                                    value={newTargetType}
                                    onChange={(e) => setNewTargetType(e.target.value)}
                                    placeholder="User, Session, Image, etc."
                                />

                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    {typeSuggestions.map((type) => (
                                        <Chip
                                            key={type}
                                            label={type}
                                            size="small"
                                            onClick={() => setNewTargetType(type)}
                                            sx={{ cursor: 'pointer' }}
                                        />
                                    ))}
                                </Box>

                                <Grid container spacing={2}>
                                    <Grid item xs={6} md={2.4}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={typeOperations.read_state === 1}
                                                    onChange={(e) =>
                                                        setTypeOperations({
                                                            ...typeOperations,
                                                            read_state: e.target.checked ? 1 : 0,
                                                        })
                                                    }
                                                />
                                            }
                                            label="Read"
                                        />
                                    </Grid>
                                    <Grid item xs={6} md={2.4}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={typeOperations.write_state === 1}
                                                    onChange={(e) =>
                                                        setTypeOperations({
                                                            ...typeOperations,
                                                            write_state: e.target.checked ? 1 : 0,
                                                        })
                                                    }
                                                />
                                            }
                                            label="Write"
                                        />
                                    </Grid>
                                    <Grid item xs={6} md={2.4}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={typeOperations.create_state === 1}
                                                    onChange={(e) =>
                                                        setTypeOperations({
                                                            ...typeOperations,
                                                            create_state: e.target.checked ? 1 : 0,
                                                        })
                                                    }
                                                />
                                            }
                                            label="Create"
                                        />
                                    </Grid>
                                    <Grid item xs={6} md={2.4}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={typeOperations.delete_state === 1}
                                                    onChange={(e) =>
                                                        setTypeOperations({
                                                            ...typeOperations,
                                                            delete_state: e.target.checked ? 1 : 0,
                                                        })
                                                    }
                                                />
                                            }
                                            label="Delete"
                                        />
                                    </Grid>
                                    <Grid item xs={6} md={2.4}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={typeOperations.navigate_state === 1}
                                                    onChange={(e) =>
                                                        setTypeOperations({
                                                            ...typeOperations,
                                                            navigate_state: e.target.checked ? 1 : 0,
                                                        })
                                                    }
                                                />
                                            }
                                            label="Navigate"
                                        />
                                    </Grid>
                                </Grid>

                                <Button
                                    variant="contained"
                                    startIcon={<Add />}
                                    onClick={handleAddTypePermission}
                                >
                                    Add Type Permission
                                </Button>

                                <Divider />

                                <TableContainer component={Paper} variant="outlined">
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Type</TableCell>
                                                <TableCell align="center">Read</TableCell>
                                                <TableCell align="center">Write</TableCell>
                                                <TableCell align="center">Create</TableCell>
                                                <TableCell align="center">Delete</TableCell>
                                                <TableCell align="center">Navigate</TableCell>
                                                <TableCell align="right">Actions</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {!Array.isArray(typePermissions) || typePermissions.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={7} align="center">
                                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                                            No type permissions defined
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            ) : (
                                                typePermissions.map((perm) => (
                                                    <TableRow key={perm.oid}>
                                                        <TableCell>
                                                            <Chip label={perm.target_type} color="info" size="small" />
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <StateChip value={perm.read_state} />
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <StateChip value={perm.write_state} />
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <StateChip value={perm.create_state} />
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <StateChip value={perm.delete_state} />
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <StateChip value={perm.navigate_state} />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <IconButton
                                                                size="small"
                                                                color="error"
                                                                onClick={() => handleDeleteTypePermission(perm.oid)}
                                                            >
                                                                <Delete />
                                                            </IconButton>
                                                        </TableCell>
                                                    </TableRow>
                                                ))
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        </TabPanel>
                    </Box>
                )}
            </DialogContent>

            <Divider />

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
}
