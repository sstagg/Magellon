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
    FormControlLabel,
    Checkbox,
    Autocomplete,
} from '@mui/material';
import {
    Add,
    Delete,
    Refresh,
    Info,
    Code,
} from '@mui/icons-material';

interface User {
    id: string;
    username: string;
}

interface Role {
    oid: string;
    name: string;
}

interface ObjectPermission {
    oid: string;
    type_permission_id: string;
    target_type: string;
    role_name: string;
    criteria: string;
    read_state: boolean;
    write_state: boolean;
    delete_state: boolean;
    navigate_state: boolean;
}

interface ObjectPermissionManagementTabProps {
    currentUser: User;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
    isSuperUser?: boolean;
}

export default function ObjectPermissionManagementTab({
    currentUser,
    showSnackbar,
    isSuperUser = false,
}: ObjectPermissionManagementTabProps) {
    const [roles, setRoles] = useState<Role[]>([]);
    const [permissions, setPermissions] = useState<ObjectPermission[]>([]);
    const [selectedRole, setSelectedRole] = useState<string>('');
    const [targetType, setTargetType] = useState<string>('Image');
    const [criteria, setCriteria] = useState<string>('');
    const [readState, setReadState] = useState(true);
    const [writeState, setWriteState] = useState(false);
    const [deleteState, setDeleteState] = useState(false);
    const [navigateState, setNavigateState] = useState(true);
    const [loading, setLoading] = useState(false);
    const [openCreateDialog, setOpenCreateDialog] = useState(false);

    const targetTypes = ['Image', 'Msession', 'Movie', 'Particle', 'Atlas', 'Square', 'Hole'];

    // Common criteria templates
    const criteriaTemplates = [
        {
            label: 'Session by ID',
            value: "[session_id] = '<uuid>'",
            description: 'Grant access to specific session by UUID'
        },
        {
            label: 'Session by Name',
            value: "[name] = '<session_name>'",
            description: 'Grant access to session by name'
        },
        {
            label: 'Multiple Sessions',
            value: "[session_id] IN ('<uuid1>', '<uuid2>')",
            description: 'Grant access to multiple sessions'
        },
        {
            label: 'Current User\'s Data',
            value: "[user_id] = CurrentUserId()",
            description: 'Dynamic: User\'s own data'
        },
        {
            label: 'Date Range',
            value: "[start_on] >= '2024-01-01' AND [start_on] <= '2024-12-31'",
            description: 'Grant access to data within date range'
        },
    ];

    useEffect(() => {
        loadRoles();
        loadPermissions();
    }, []);

    const loadRoles = async () => {
        try {
            const axios = (await import('axios')).default;
            const token = localStorage.getItem('access_token');

            const response = await axios.get('http://localhost:8000/db/security/roles/', {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            setRoles(response.data || []);
        } catch (error: any) {
            console.error('Failed to load roles:', error);
            showSnackbar('Failed to load roles: ' + (error.message || 'Unknown error'), 'error');
        }
    };

    const loadPermissions = async () => {
        try {
            setLoading(true);
            // TODO: Implement backend endpoint to list all object permissions
            // For now, show empty state
            setPermissions([]);
        } catch (error: any) {
            console.error('Failed to load permissions:', error);
            showSnackbar('Failed to load permissions: ' + (error.message || 'Unknown error'), 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleCreatePermission = async () => {
        if (!selectedRole || !criteria.trim()) {
            showSnackbar('Please select a role and enter criteria', 'warning');
            return;
        }

        try {
            const axios = (await import('axios')).default;
            const token = localStorage.getItem('access_token');

            // First, get or create type permission for the role
            const typePermResponse = await axios.post(
                'http://localhost:8000/db/security/types',
                {
                    target_type: targetType,
                    Role: selectedRole,
                    read_state: readState ? 1 : 0,
                    write_state: writeState ? 1 : 0,
                    create_state: 0,
                    delete_state: deleteState ? 1 : 0,
                    navigate_state: navigateState ? 1 : 0,
                },
                {
                    headers: { 'Authorization': `Bearer ${token}` },
                }
            );

            const typePermId = typePermResponse.data.Oid;

            // Then create object permission with criteria
            await axios.post(
                `http://localhost:8000/db/security/object-permissions`,
                {
                    type_permission_id: typePermId,
                    criteria: criteria,
                    read_state: readState ? 1 : 0,
                    write_state: writeState ? 1 : 0,
                    delete_state: deleteState ? 1 : 0,
                    navigate_state: navigateState ? 1 : 0,
                },
                {
                    headers: { 'Authorization': `Bearer ${token}` },
                }
            );

            showSnackbar('Object permission created successfully!', 'success');
            setOpenCreateDialog(false);
            setCriteria('');
            setReadState(true);
            setWriteState(false);
            setDeleteState(false);
            setNavigateState(true);
            loadPermissions();
        } catch (error: any) {
            console.error('Failed to create permission:', error);
            showSnackbar(
                'Failed to create permission: ' + (error.response?.data?.detail || error.message || 'Unknown error'),
                'error'
            );
        }
    };

    const useCriteriaTemplate = (template: string) => {
        setCriteria(template);
    };

    return (
        <Box>
            <Typography variant="h5" gutterBottom>
                Object Permission Management
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
                Create row-level permissions using XAF criteria expressions. This is the generic interface
                for all object permissions - more flexible than the Session Access shortcut.
            </Typography>

            {isSuperUser && (
                <Alert severity="info" sx={{ mb: 3 }}>
                    Super user mode: You can create object permissions for any role and any criteria pattern.
                </Alert>
            )}

            <Alert severity="info" sx={{ mb: 3 }} icon={<Info />}>
                <Typography variant="subtitle2" gutterBottom>
                    <strong>What are Object Permissions?</strong>
                </Typography>
                <Typography variant="body2">
                    Object permissions use <strong>XAF criteria expressions</strong> to define row-level access.
                    Examples:
                </Typography>
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                    <li><code>[session_id] = 'uuid'</code> - Access to one specific session</li>
                    <li><code>[name] = '24DEC03A'</code> - Access by name field</li>
                    <li><code>[session_id] IN ('uuid1', 'uuid2')</code> - Access to multiple records</li>
                    <li><code>[user_id] = CurrentUserId()</code> - Dynamic: user's own data</li>
                </ul>
            </Alert>

            <Grid container spacing={3}>
                {/* Create Permission Section */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Existing Object Permissions</Typography>
                            <Button
                                startIcon={<Add />}
                                variant="contained"
                                onClick={() => setOpenCreateDialog(true)}
                            >
                                Create Object Permission
                            </Button>
                        </Box>

                        {loading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                                <CircularProgress />
                            </Box>
                        ) : permissions.length === 0 ? (
                            <Alert severity="info">
                                No object permissions yet. Click "Create Object Permission" to add criteria-based access rules.
                            </Alert>
                        ) : (
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Role</TableCell>
                                            <TableCell>Type</TableCell>
                                            <TableCell>Criteria</TableCell>
                                            <TableCell align="center">Read</TableCell>
                                            <TableCell align="center">Write</TableCell>
                                            <TableCell align="center">Delete</TableCell>
                                            <TableCell align="center">Actions</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {permissions.map((perm) => (
                                            <TableRow key={perm.oid}>
                                                <TableCell>
                                                    <Chip label={perm.role_name} size="small" />
                                                </TableCell>
                                                <TableCell>{perm.target_type}</TableCell>
                                                <TableCell>
                                                    <code style={{ fontSize: '0.875rem' }}>{perm.criteria}</code>
                                                </TableCell>
                                                <TableCell align="center">
                                                    {perm.read_state ? '✓' : '-'}
                                                </TableCell>
                                                <TableCell align="center">
                                                    {perm.write_state ? '✓' : '-'}
                                                </TableCell>
                                                <TableCell align="center">
                                                    {perm.delete_state ? '✓' : '-'}
                                                </TableCell>
                                                <TableCell align="center">
                                                    <Tooltip title="Delete Permission">
                                                        <IconButton size="small" color="error">
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
            </Grid>

            {/* Create Dialog */}
            <Dialog open={openCreateDialog} onClose={() => setOpenCreateDialog(false)} maxWidth="md" fullWidth>
                <DialogTitle>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Code />
                        Create Object Permission
                    </Box>
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 2 }}>
                        {/* Role Selection */}
                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel>Role</InputLabel>
                            <Select
                                value={selectedRole}
                                onChange={(e) => setSelectedRole(e.target.value)}
                                label="Role"
                            >
                                <MenuItem value="">
                                    <em>Select a role...</em>
                                </MenuItem>
                                {roles.map((role) => (
                                    <MenuItem key={role.oid} value={role.oid}>
                                        {role.name}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        {/* Target Type Selection */}
                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel>Target Type</InputLabel>
                            <Select
                                value={targetType}
                                onChange={(e) => setTargetType(e.target.value)}
                                label="Target Type"
                            >
                                {targetTypes.map((type) => (
                                    <MenuItem key={type} value={type}>
                                        {type}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        {/* Criteria Templates */}
                        <Typography variant="subtitle2" gutterBottom sx={{ mt: 3 }}>
                            Common Criteria Templates:
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                            {criteriaTemplates.map((template) => (
                                <Tooltip key={template.label} title={template.description}>
                                    <Chip
                                        label={template.label}
                                        onClick={() => useCriteriaTemplate(template.value)}
                                        size="small"
                                        variant="outlined"
                                        sx={{ cursor: 'pointer' }}
                                    />
                                </Tooltip>
                            ))}
                        </Box>

                        {/* Criteria Expression */}
                        <TextField
                            fullWidth
                            label="Criteria Expression (XAF Syntax)"
                            value={criteria}
                            onChange={(e) => setCriteria(e.target.value)}
                            multiline
                            rows={3}
                            placeholder="[session_id] = 'abc-123-def-456'"
                            helperText="Enter XAF criteria expression. Use templates above or write custom criteria."
                            sx={{ mb: 2, fontFamily: 'monospace' }}
                        />

                        {/* Permissions */}
                        <Typography variant="subtitle2" gutterBottom>
                            Access Permissions:
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={readState}
                                        onChange={(e) => setReadState(e.target.checked)}
                                    />
                                }
                                label="Read"
                            />
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={writeState}
                                        onChange={(e) => setWriteState(e.target.checked)}
                                    />
                                }
                                label="Write"
                            />
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={deleteState}
                                        onChange={(e) => setDeleteState(e.target.checked)}
                                    />
                                }
                                label="Delete"
                            />
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={navigateState}
                                        onChange={(e) => setNavigateState(e.target.checked)}
                                    />
                                }
                                label="Navigate"
                            />
                        </Box>

                        <Alert severity="warning" sx={{ mt: 2 }}>
                            <Typography variant="body2">
                                <strong>Note:</strong> Complex criteria like <code>[user_id] = CurrentUserId()</code>
                                cannot be synced to Casbin and will use hybrid enforcement.
                            </Typography>
                        </Alert>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenCreateDialog(false)}>Cancel</Button>
                    <Button
                        onClick={handleCreatePermission}
                        variant="contained"
                        disabled={!selectedRole || !criteria.trim()}
                        startIcon={<Add />}
                    >
                        Create Permission
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
