import { useEffect, useState } from 'react';
import type { MouseEvent } from 'react';
import type { CreateUserRequest, UpdateUserRequest } from '../../auth/api/userApi.ts';
import { userApiService } from '../../auth/api/userApi.ts';
import type { SnackbarState, UserData } from './types.ts';
import { convertApiUserToUserData } from './types.ts';
import { useUserForm } from './useUserForm.ts';

export const useUserManagement = () => {
    const form = useUserForm();
    const { formData, resetForm, populateForm } = form;

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

    // Pagination state
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [snackbar, setSnackbar] = useState<SnackbarState>({
        open: false,
        message: '',
        severity: 'success'
    });

    // Load users on component mount and when filters change
    useEffect(() => {
        loadUsers();
    }, [page, rowsPerPage, statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        filterUsers();
    }, [users, searchTerm]); // eslint-disable-line react-hooks/exhaustive-deps

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
                message: `Failed to load users: ${  (error as Error).message}`,
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
                message: `Failed to create user: ${  (error as Error).message}`,
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
                message: `Failed to update user: ${  (error as Error).message}`,
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
                message: `Failed to delete user: ${  (error as Error).message}`,
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
                message: `Failed to update user status: ${  (error as Error).message}`,
                severity: 'error'
            });
        }
    };

    const openEditDialog = (user: UserData) => {
        setSelectedUser(user);
        populateForm(user);
        setIsEditDialogOpen(true);
    };

    const openDeleteDialog = (user: UserData) => {
        setSelectedUser(user);
        setIsDeleteDialogOpen(true);
    };

    const handleMenuOpen = (event: MouseEvent<HTMLElement>, userId: string) => {
        setMenuAnchor(event.currentTarget);
        setMenuUserId(userId);
    };

    const handleMenuClose = () => {
        setMenuAnchor(null);
        setMenuUserId(null);
    };

    const handleMenuEdit = () => {
        const user = users.find(u => u.id === menuUserId);
        if (user) openEditDialog(user);
        handleMenuClose();
    };

    const handleMenuDelete = () => {
        const user = users.find(u => u.id === menuUserId);
        if (user) openDeleteDialog(user);
        handleMenuClose();
    };

    const closeSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    return {
        form,
        users,
        filteredUsers,
        loading,
        searchTerm,
        setSearchTerm,
        statusFilter,
        setStatusFilter,
        totalUsers,
        isCreateDialogOpen,
        setIsCreateDialogOpen,
        isEditDialogOpen,
        setIsEditDialogOpen,
        isDeleteDialogOpen,
        setIsDeleteDialogOpen,
        selectedUser,
        menuAnchor,
        page,
        setPage,
        rowsPerPage,
        setRowsPerPage,
        snackbar,
        closeSnackbar,
        loadUsers,
        handleCreateUser,
        handleUpdateUser,
        handleDeleteUser,
        handleToggleUserStatus,
        openEditDialog,
        handleMenuOpen,
        handleMenuClose,
        handleMenuEdit,
        handleMenuDelete
    };
};
