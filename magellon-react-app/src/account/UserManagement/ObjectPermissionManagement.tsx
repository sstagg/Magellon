'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Chip,
    Alert,
    AlertTitle,
    CircularProgress,
    Radio,
    RadioGroup,
    FormControlLabel,
    FormLabel,
    Grid,
    FormControl,
} from '@mui/material';
import {
    Add,
    Edit,
    Delete,
    CheckCircle,
    Cancel,
    Code,
} from '@mui/icons-material';

interface ObjectPermission {
    oid: string;
    criteria: string;
    read_state: number;
    write_state: number;
    delete_state: number;
    navigate_state: number;
    type_permission_object: string;
}

interface ObjectPermissionManagementProps {
    typePermissionId: string;
    targetType: string;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}

export default function ObjectPermissionManagement({
    typePermissionId,
    targetType,
    showSnackbar,
}: ObjectPermissionManagementProps) {
    const [permissions, setPermissions] = useState<ObjectPermission[]>([]);
    const [loading, setLoading] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingPermission, setEditingPermission] = useState<ObjectPermission | null>(null);

    const [formData, setFormData] = useState({
        criteria: '',
        read_state: 1,
        write_state: 1,
        delete_state: 0,
        navigate_state: 1,
    });

    const criteriaExamples = [
        'owner_id = CurrentUserId()',
        'department = CurrentUser().Department',
        'created_by = CurrentUserId() OR assigned_to = CurrentUserId()',
        'status IN ("draft", "pending")',
        'team_members CONTAINS CurrentUserId()',
    ];

    useEffect(() => {
        loadPermissions();
    }, [typePermissionId]);

    const loadPermissions = async () => {
        setLoading(true);
        try {
            const response = await fetch(
                `http://localhost:8000/db/security/permissions/objects/type/${typePermissionId}`
            );
            if (!response.ok) throw new Error('Failed to load object permissions');
            const data = await response.json();
            setPermissions(data);
        } catch (error: any) {
            showSnackbar('Failed to load object permissions: ' + error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setEditingPermission(null);
        setFormData({
            criteria: '',
            read_state: 1,
            write_state: 1,
            delete_state: 0,
            navigate_state: 1,
        });
        setDialogOpen(true);
    };

    const openEditDialog = (permission: ObjectPermission) => {
        setEditingPermission(permission);
        setFormData({
            criteria: permission.criteria,
            read_state: permission.read_state,
            write_state: permission.write_state,
            delete_state: permission.delete_state,
            navigate_state: permission.navigate_state,
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (!formData.criteria.trim()) {
            showSnackbar('Criteria expression is required', 'error');
            return;
        }

        try {
            const payload = {
                type_permission_object: typePermissionId,
                criteria: formData.criteria,
                read_state: formData.read_state,
                write_state: formData.write_state,
                delete_state: formData.delete_state,
                navigate_state: formData.navigate_state,
            };

            if (editingPermission) {
                const response = await fetch(
                    `http://localhost:8000/db/security/permissions/objects/${editingPermission.oid}`,
                    {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ...payload, oid: editingPermission.oid }),
                    }
                );
                if (!response.ok) throw new Error('Failed to update object permission');
                showSnackbar('Object permission updated successfully', 'success');
            } else {
                const response = await fetch(
                    'http://localhost:8000/db/security/permissions/objects',
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    }
                );
                if (!response.ok) throw new Error('Failed to create object permission');
                showSnackbar('Object permission created successfully', 'success');
            }

            setDialogOpen(false);
            loadPermissions();
        } catch (error: any) {
            showSnackbar('Failed to save object permission: ' + error.message, 'error');
        }
    };

    const handleDelete = async (permissionId: string) => {
        if (!confirm('Are you sure you want to delete this object permission?')) return;

        try {
            const response = await fetch(
                `http://localhost:8000/db/security/permissions/objects/${permissionId}`,
                { method: 'DELETE' }
            );
            if (!response.ok) throw new Error('Failed to delete object permission');
            showSnackbar('Object permission deleted successfully', 'success');
            loadPermissions();
        } catch (error: any) {
            showSnackbar('Failed to delete object permission: ' + error.message, 'error');
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
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                    Object Permissions - {targetType}
                </Typography>
                <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={openCreateDialog}
                >
                    Add Object Permission
                </Button>
            </Box>

            <Alert severity="info" sx={{ mb: 2 }}>
                Object permissions control instance-level access. Use criteria to define which specific objects users can access. Example: "Users can only edit their own records"
            </Alert>

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                    <CircularProgress />
                </Box>
            ) : (
                <TableContainer>
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableCell>Criteria</TableCell>
                                <TableCell>Read</TableCell>
                                <TableCell>Write</TableCell>
                                <TableCell>Delete</TableCell>
                                <TableCell>Navigate</TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {permissions.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={6} align="center">
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                            No object permissions defined
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                permissions.map((permission) => (
                                    <TableRow key={permission.oid} hover>
                                        <TableCell>
                                            <Box
                                                sx={{
                                                    p: 1,
                                                    bgcolor: 'background.default',
                                                    borderRadius: 1,
                                                    fontFamily: 'monospace',
                                                    fontSize: '0.75rem',
                                                }}
                                            >
                                                {permission.criteria}
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.read_state} />
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.write_state} />
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.delete_state} />
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.navigate_state} />
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton
                                                size="small"
                                                onClick={() => openEditDialog(permission)}
                                            >
                                                <Edit />
                                            </IconButton>
                                            <IconButton
                                                size="small"
                                                onClick={() => handleDelete(permission.oid)}
                                                color="error"
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
            )}

            {/* Create/Edit Dialog */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>
                    {editingPermission ? 'Edit Object Permission' : 'Create Object Permission'}
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 2 }}>
                        <Alert severity="info" icon={<Code />}>
                            <AlertTitle>Criteria Expression Examples</AlertTitle>
                            {criteriaExamples.map((example, idx) => (
                                <Box
                                    key={idx}
                                    sx={{
                                        fontFamily: 'monospace',
                                        fontSize: '0.75rem',
                                        p: 0.5,
                                        cursor: 'pointer',
                                        '&:hover': { bgcolor: 'action.hover' },
                                    }}
                                    onClick={() => setFormData({ ...formData, criteria: example })}
                                >
                                    • {example}
                                </Box>
                            ))}
                        </Alert>

                        <TextField
                            label="Filter Criteria (SQL-like)"
                            multiline
                            rows={4}
                            value={formData.criteria}
                            onChange={(e) => setFormData({ ...formData, criteria: e.target.value })}
                            placeholder="owner_id = CurrentUserId()"
                            required
                            helperText="Click examples above to use them, or write your own expression"
                            InputProps={{
                                sx: { fontFamily: 'monospace' },
                            }}
                        />

                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <FormControl fullWidth>
                                    <FormLabel>Read Permission</FormLabel>
                                    <RadioGroup
                                        row
                                        value={formData.read_state}
                                        onChange={(e) => setFormData({ ...formData, read_state: Number(e.target.value) })}
                                    >
                                        <FormControlLabel value={1} control={<Radio />} label="Allow" />
                                        <FormControlLabel value={0} control={<Radio />} label="Deny" />
                                    </RadioGroup>
                                </FormControl>
                            </Grid>
                            <Grid item xs={6}>
                                <FormControl fullWidth>
                                    <FormLabel>Write Permission</FormLabel>
                                    <RadioGroup
                                        row
                                        value={formData.write_state}
                                        onChange={(e) => setFormData({ ...formData, write_state: Number(e.target.value) })}
                                    >
                                        <FormControlLabel value={1} control={<Radio />} label="Allow" />
                                        <FormControlLabel value={0} control={<Radio />} label="Deny" />
                                    </RadioGroup>
                                </FormControl>
                            </Grid>
                            <Grid item xs={6}>
                                <FormControl fullWidth>
                                    <FormLabel>Delete Permission</FormLabel>
                                    <RadioGroup
                                        row
                                        value={formData.delete_state}
                                        onChange={(e) => setFormData({ ...formData, delete_state: Number(e.target.value) })}
                                    >
                                        <FormControlLabel value={1} control={<Radio />} label="Allow" />
                                        <FormControlLabel value={0} control={<Radio />} label="Deny" />
                                    </RadioGroup>
                                </FormControl>
                            </Grid>
                            <Grid item xs={6}>
                                <FormControl fullWidth>
                                    <FormLabel>Navigate Permission</FormLabel>
                                    <RadioGroup
                                        row
                                        value={formData.navigate_state}
                                        onChange={(e) => setFormData({ ...formData, navigate_state: Number(e.target.value) })}
                                    >
                                        <FormControlLabel value={1} control={<Radio />} label="Allow" />
                                        <FormControlLabel value={0} control={<Radio />} label="Deny" />
                                    </RadioGroup>
                                </FormControl>
                            </Grid>
                        </Grid>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={handleSave}
                        variant="contained"
                        disabled={!formData.criteria.trim()}
                    >
                        {editingPermission ? 'Update' : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
