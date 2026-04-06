import React from 'react';
import {
    Box,
    Typography,
    Avatar,
    Chip,
    IconButton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination,
} from '@mui/material';
import {
    Edit,
    Lock,
    LockOpen,
    Security,
    Add,
    Delete,
    AssignmentInd,
    Block,
} from '@mui/icons-material';

interface UserTableProps {
    users: any[];
    page: number;
    rowsPerPage: number;
    onPageChange: (newPage: number) => void;
    onRowsPerPageChange: (newRowsPerPage: number) => void;
    onOpenRoleDialog: (user: any) => void;
    onOpenChangePasswordDialog: (user: any) => void;
    onActivateUser: (userId: string) => void;
    onDeactivateUser: (userId: string) => void;
    onDeleteUser: (userId: string) => void;
}

export default function UserTable({
    users,
    page,
    rowsPerPage,
    onPageChange,
    onRowsPerPageChange,
    onOpenRoleDialog,
    onOpenChangePasswordDialog,
    onActivateUser,
    onDeactivateUser,
    onDeleteUser,
}: UserTableProps) {
    return (
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
                        {users
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
                                                    onClick={() => onOpenRoleDialog(user)}
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
                                                            onClick={() => onOpenRoleDialog(user)}
                                                            sx={{ cursor: 'pointer' }}
                                                        />
                                                    ))}
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => onOpenRoleDialog(user)}
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
                                                    onClick={() => onOpenRoleDialog(user)}
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
                                                onClick={() => onDeactivateUser(user.id || user.oid)}
                                                title="Deactivate User"
                                                color="warning"
                                            >
                                                <Block />
                                            </IconButton>
                                        ) : (
                                            <IconButton
                                                size="small"
                                                onClick={() => onActivateUser(user.id || user.oid)}
                                                title="Activate User"
                                                color="success"
                                            >
                                                <LockOpen />
                                            </IconButton>
                                        )}
                                        <IconButton
                                            size="small"
                                            onClick={() => onOpenChangePasswordDialog(user)}
                                            title="Change Password"
                                        >
                                            <Lock />
                                        </IconButton>
                                        <IconButton
                                            size="small"
                                            onClick={() => onOpenRoleDialog(user)}
                                            title="Assign Roles"
                                        >
                                            <AssignmentInd />
                                        </IconButton>
                                        <IconButton
                                            size="small"
                                            onClick={() => onDeleteUser(user.id || user.oid)}
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
                count={users.length}
                page={page}
                onPageChange={(_, newPage) => onPageChange(newPage)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => {
                    onRowsPerPageChange(parseInt(e.target.value, 10));
                }}
                rowsPerPageOptions={[5, 10, 25]}
            />
        </>
    );
}
