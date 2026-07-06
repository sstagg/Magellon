import React from 'react';
import {
    Alert,
    Box,
    Button,
    Container,
    Paper,
    Snackbar,
    Typography
} from '@mui/material';
import { PersonAdd } from '@mui/icons-material';
import { useUserManagement } from '../model/useUserManagement.ts';
import UserStatsCards from './UserStatsCards.tsx';
import UserFilters from './UserFilters.tsx';
import UserManagementTable from './UserManagementTable.tsx';
import UserActionsMenu from './UserActionsMenu.tsx';
import UserFormDialog from './UserFormDialog.tsx';
import DeleteUserDialog from './DeleteUserDialog.tsx';

const UserManagementPage: React.FC = () => {
    const {
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
    } = useUserManagement();

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
                            <Typography variant="body1" sx={{
                                color: "text.secondary"
                            }}>
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
                <UserStatsCards users={users} totalUsers={totalUsers} />

                {/* Filters and Search */}
                <UserFilters
                    searchTerm={searchTerm}
                    onSearchTermChange={setSearchTerm}
                    statusFilter={statusFilter}
                    onStatusFilterChange={setStatusFilter}
                    loading={loading}
                    onRefresh={loadUsers}
                />

                {/* Users Table */}
                <UserManagementTable
                    users={filteredUsers}
                    loading={loading}
                    totalUsers={totalUsers}
                    page={page}
                    rowsPerPage={rowsPerPage}
                    onPageChange={setPage}
                    onRowsPerPageChange={(newRowsPerPage) => {
                        setRowsPerPage(newRowsPerPage);
                        setPage(0);
                    }}
                    onEditUser={openEditDialog}
                    onToggleUserStatus={handleToggleUserStatus}
                    onMenuOpen={handleMenuOpen}
                />

                {/* Action Menu */}
                <UserActionsMenu
                    anchorEl={menuAnchor}
                    onClose={handleMenuClose}
                    onEditUser={handleMenuEdit}
                    onDeleteUser={handleMenuDelete}
                />

                {/* Create User Dialog */}
                <UserFormDialog
                    mode="create"
                    open={isCreateDialogOpen}
                    form={form}
                    onClose={() => setIsCreateDialogOpen(false)}
                    onSubmit={handleCreateUser}
                />

                {/* Edit User Dialog */}
                <UserFormDialog
                    mode="edit"
                    open={isEditDialogOpen}
                    form={form}
                    onClose={() => setIsEditDialogOpen(false)}
                    onSubmit={handleUpdateUser}
                />

                {/* Delete Confirmation Dialog */}
                <DeleteUserDialog
                    open={isDeleteDialogOpen}
                    user={selectedUser}
                    onClose={() => setIsDeleteDialogOpen(false)}
                    onConfirm={handleDeleteUser}
                />

                {/* Snackbar for notifications */}
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={closeSnackbar}
                >
                    <Alert
                        severity={snackbar.severity}
                        onClose={closeSnackbar}
                    >
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>
        </Container>
    );
};

export default UserManagementPage;
