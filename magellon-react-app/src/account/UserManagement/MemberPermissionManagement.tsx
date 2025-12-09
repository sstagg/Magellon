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
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Chip,
    Alert,
    CircularProgress,
    Autocomplete,
    Radio,
    RadioGroup,
    FormControlLabel,
    FormLabel,
} from '@mui/material';
import {
    Add,
    Edit,
    Delete,
    CheckCircle,
    Cancel,
} from '@mui/icons-material';
import getAxiosClient from '../../core/AxiosClient.ts';
import { settings } from '../../core/settings.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

interface MemberPermission {
    oid: string;
    members: string;
    read_state: number;
    write_state: number;
    criteria?: string;
    type_permission_object: string;
}

interface MemberPermissionManagementProps {
    typePermissionId: string;
    targetType: string;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}

export default function MemberPermissionManagement({
    typePermissionId,
    targetType,
    showSnackbar,
}: MemberPermissionManagementProps) {
    const [permissions, setPermissions] = useState<MemberPermission[]>([]);
    const [loading, setLoading] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingPermission, setEditingPermission] = useState<MemberPermission | null>(null);

    const [formData, setFormData] = useState({
        members: [] as string[],
        read_state: 1,
        write_state: 0,
        criteria: '',
    });

    useEffect(() => {
        loadPermissions();
    }, [typePermissionId]);

    const loadPermissions = async () => {
        setLoading(true);
        try {
            const response = await apiClient.get(
                `/db/security/permissions/members/type/${typePermissionId}`
            );
            setPermissions(response.data);
        } catch (error: any) {
            showSnackbar('Failed to load member permissions: ' + (error.response?.data?.detail || error.message), 'error');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setEditingPermission(null);
        setFormData({
            members: [],
            read_state: 1,
            write_state: 0,
            criteria: '',
        });
        setDialogOpen(true);
    };

    const openEditDialog = (permission: MemberPermission) => {
        setEditingPermission(permission);
        setFormData({
            members: permission.members.split(',').map(m => m.trim()),
            read_state: permission.read_state,
            write_state: permission.write_state,
            criteria: permission.criteria || '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        try {
            const payload = {
                type_permission_object: typePermissionId,
                members: formData.members.join(', '),
                read_state: formData.read_state,
                write_state: formData.write_state,
                criteria: formData.criteria || undefined,
            };

            if (editingPermission) {
                await apiClient.put(
                    `/db/security/permissions/members/${editingPermission.oid}`,
                    { ...payload, oid: editingPermission.oid }
                );
                showSnackbar('Member permission updated successfully', 'success');
            } else {
                await apiClient.post(
                    '/db/security/permissions/members',
                    payload
                );
                showSnackbar('Member permission created successfully', 'success');
            }

            setDialogOpen(false);
            loadPermissions();
        } catch (error: any) {
            showSnackbar('Failed to save member permission: ' + (error.response?.data?.detail || error.message), 'error');
        }
    };

    const handleDelete = async (permissionId: string) => {
        if (!confirm('Are you sure you want to delete this member permission?')) return;

        try {
            await apiClient.delete(
                `/db/security/permissions/members/${permissionId}`
            );
            showSnackbar('Member permission deleted successfully', 'success');
            loadPermissions();
        } catch (error: any) {
            showSnackbar('Failed to delete member permission: ' + (error.response?.data?.detail || error.message), 'error');
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
                    Member Permissions - {targetType}
                </Typography>
                <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={openCreateDialog}
                >
                    Add Member Permission
                </Button>
            </Box>

            <Alert severity="info" sx={{ mb: 2 }}>
                Member permissions control field-level access. Use them to hide sensitive fields like salary or SSN from certain roles.
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
                                <TableCell>Fields/Members</TableCell>
                                <TableCell>Read</TableCell>
                                <TableCell>Write</TableCell>
                                <TableCell>Criteria</TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {permissions.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} align="center">
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                            No member permissions defined
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                permissions.map((permission) => (
                                    <TableRow key={permission.oid} hover>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                                {permission.members.split(',').map((member, idx) => (
                                                    <Chip
                                                        key={idx}
                                                        label={member.trim()}
                                                        size="small"
                                                        variant="outlined"
                                                    />
                                                ))}
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.read_state} />
                                        </TableCell>
                                        <TableCell>
                                            <StateChip value={permission.write_state} />
                                        </TableCell>
                                        <TableCell>
                                            {permission.criteria ? (
                                                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                                                    {permission.criteria}
                                                </Typography>
                                            ) : (
                                                <Typography variant="caption" color="text.secondary">
                                                    None
                                                </Typography>
                                            )}
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
                    {editingPermission ? 'Edit Member Permission' : 'Create Member Permission'}
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 2 }}>
                        <Autocomplete
                            multiple
                            freeSolo
                            options={[]}
                            value={formData.members}
                            onChange={(_, newValue) => setFormData({ ...formData, members: newValue })}
                            renderInput={(params) => (
                                <TextField
                                    {...params}
                                    label="Field/Property Names"
                                    helperText="Type field names and press Enter. Example: salary, ssn, email"
                                />
                            )}
                        />

                        <FormControl>
                            <FormLabel>Read Permission</FormLabel>
                            <RadioGroup
                                row
                                value={formData.read_state}
                                onChange={(e) => setFormData({ ...formData, read_state: Number(e.target.value) })}
                            >
                                <FormControlLabel value={1} control={<Radio />} label="Allow Read" />
                                <FormControlLabel value={0} control={<Radio />} label="Deny Read" />
                            </RadioGroup>
                        </FormControl>

                        <FormControl>
                            <FormLabel>Write Permission</FormLabel>
                            <RadioGroup
                                row
                                value={formData.write_state}
                                onChange={(e) => setFormData({ ...formData, write_state: Number(e.target.value) })}
                            >
                                <FormControlLabel value={1} control={<Radio />} label="Allow Write" />
                                <FormControlLabel value={0} control={<Radio />} label="Deny Write" />
                            </RadioGroup>
                        </FormControl>

                        <TextField
                            label="Additional Criteria (Optional)"
                            multiline
                            rows={3}
                            value={formData.criteria}
                            onChange={(e) => setFormData({ ...formData, criteria: e.target.value })}
                            placeholder="SQL-like expression: status='active'"
                            helperText="Additional filter criteria for when this permission applies"
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={handleSave}
                        variant="contained"
                        disabled={formData.members.length === 0}
                    >
                        {editingPermission ? 'Update' : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
