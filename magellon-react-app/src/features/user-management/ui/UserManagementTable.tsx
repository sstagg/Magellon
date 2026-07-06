import React from 'react';
import {
    alpha,
    Avatar,
    Box,
    Chip,
    CircularProgress,
    IconButton,
    Paper,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TablePagination,
    TableRow,
    Tooltip,
    Typography,
    useTheme
} from '@mui/material';
import { Edit, Lock, LockOpen, MoreVert } from '@mui/icons-material';
import type { UserData } from '../model/types.ts';

interface UserManagementTableProps {
    users: UserData[];
    loading: boolean;
    totalUsers: number;
    page: number;
    rowsPerPage: number;
    onPageChange: (newPage: number) => void;
    onRowsPerPageChange: (newRowsPerPage: number) => void;
    onEditUser: (user: UserData) => void;
    onToggleUserStatus: (userId: string) => void;
    onMenuOpen: (event: React.MouseEvent<HTMLElement>, userId: string) => void;
}

const formatDate = (date: Date | null) => {
    if (!date) return 'Never';
    return `${date.toLocaleDateString()  } ${  date.toLocaleTimeString()}`;
};

export default function UserManagementTable({
    users,
    loading,
    totalUsers,
    page,
    rowsPerPage,
    onPageChange,
    onRowsPerPageChange,
    onEditUser,
    onToggleUserStatus,
    onMenuOpen
}: UserManagementTableProps) {
    const theme = useTheme();

    return (
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
                        ) : users.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} align="center">
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            color: "text.secondary",
                                            p: 3
                                        }}>
                                        No users found
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            users.map((user) => (
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
                                                    <Typography variant="body2" sx={{
                                                        color: "text.secondary"
                                                    }}>
                                                        ID: {user.ouid}
                                                    </Typography>
                                                )}
                                                {user.version && (
                                                    <Typography variant="caption" sx={{
                                                        color: "text.secondary"
                                                    }}>
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
                                                    onClick={() => onEditUser(user)}
                                                >
                                                    <Edit />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title={user.active ? 'Deactivate' : 'Activate'}>
                                                <IconButton
                                                    size="small"
                                                    onClick={() => onToggleUserStatus(user.id)}
                                                >
                                                    {user.active ? <Lock /> : <LockOpen />}
                                                </IconButton>
                                            </Tooltip>
                                            <IconButton
                                                size="small"
                                                onClick={(e) => onMenuOpen(e, user.id)}
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
                onPageChange={(_, newPage) => onPageChange(newPage)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => onRowsPerPageChange(parseInt(e.target.value, 10))}
                rowsPerPageOptions={[5, 10, 25, 50]}
            />
        </Paper>
    );
}
