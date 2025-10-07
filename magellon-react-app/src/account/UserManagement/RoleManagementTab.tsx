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
  TablePagination,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch,
  InputAdornment,
  CircularProgress,
  Avatar,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Grid,
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Search,
  MoreVert,
  AdminPanelSettings,
  Security,
  People,
  VpnKey,
  Refresh,
} from '@mui/icons-material';

import { RoleAPI, UserRoleAPI, PermissionManagementAPI } from './rbacApi';
import PermissionAssignmentDialog from './PermissionAssignmentDialog';
import RoleEditDialog from './RoleEditDialog';

interface RoleManagementTabProps {
  currentUser: any;
  showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
  isSuperUser?: boolean;
}

export default function RoleManagementTab({ currentUser, showSnackbar, isSuperUser = false }: RoleManagementTabProps) {
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<any[]>([]);
  const [filteredRoles, setFilteredRoles] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Dialogs
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [permissionDialogOpen, setPermissionDialogOpen] = useState(false);
  const [usersDialogOpen, setUsersDialogOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<any>(null);

  // Form data
  const [formData, setFormData] = useState({
    name: '',
    is_administrative: false,
    can_edit_model: false,
    permission_policy: 0,
  });

  // Menu
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [menuRole, setMenuRole] = useState<any>(null);

  // Statistics
  const [statistics, setStatistics] = useState<any>(null);

  // Role users
  const [roleUsers, setRoleUsers] = useState<any[]>([]);

  useEffect(() => {
    loadRoles();
    loadStatistics();
  }, []);

  useEffect(() => {
    filterRoles();
  }, [roles, searchTerm]);

  const loadRoles = async () => {
    setLoading(true);
    try {
      const data = await RoleAPI.getRoles();
      setRoles(data);
    } catch (error: any) {
      console.error('Failed to load roles:', error);
      showSnackbar('Failed to load roles: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const stats = await RoleAPI.getRoleStatistics();
      setStatistics(stats);
    } catch (error) {
      console.error('Failed to load statistics:', error);
    }
  };

  const filterRoles = () => {
    if (!searchTerm) {
      setFilteredRoles(roles);
      return;
    }
    const filtered = roles.filter((role) =>
      role.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredRoles(filtered);
  };

  const handleCreateRole = async () => {
    setLoading(true);
    try {
      await RoleAPI.createRole(formData);
      showSnackbar('Role created successfully', 'success');
      setCreateDialogOpen(false);
      resetForm();
      loadRoles();
      loadStatistics();
    } catch (error: any) {
      showSnackbar('Failed to create role: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateRole = async () => {
    if (!selectedRole) return;
    setLoading(true);
    try {
      await RoleAPI.updateRole({
        oid: selectedRole.oid,
        ...formData,
      });
      showSnackbar('Role updated successfully', 'success');
      setEditDialogOpen(false);
      setSelectedRole(null);
      resetForm();
      loadRoles();
    } catch (error: any) {
      showSnackbar('Failed to update role: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!selectedRole) return;
    setLoading(true);
    try {
      await RoleAPI.deleteRole(selectedRole.oid);
      showSnackbar('Role deleted successfully', 'success');
      setDeleteDialogOpen(false);
      setSelectedRole(null);
      loadRoles();
      loadStatistics();
    } catch (error: any) {
      showSnackbar('Failed to delete role: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadRoleUsers = async (role: any) => {
    setLoading(true);
    try {
      const response = await UserRoleAPI.getRoleUsers(role.oid);
      // Handle both array response and object with users property
      const users = Array.isArray(response) ? response : (response.users || []);
      setRoleUsers(users);
      setSelectedRole(role);
      setUsersDialogOpen(true);
    } catch (error: any) {
      showSnackbar('Failed to load role users: ' + error.message, 'error');
      setRoleUsers([]); // Set to empty array on error
    } finally {
      setLoading(false);
    }
  };

  const openEditDialog = (role: any) => {
    console.log('Opening edit dialog for role:', role);
    console.log('Role oid:', role.oid, 'Role Oid:', role.Oid);
    setSelectedRole(role);
    setFormData({
      name: role.name,
      is_administrative: role.is_administrative,
      can_edit_model: role.can_edit_model,
      permission_policy: role.permission_policy,
    });
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (role: any) => {
    setSelectedRole(role);
    setDeleteDialogOpen(true);
  };

  const openPermissionDialog = (role: any) => {
    setSelectedRole(role);
    setPermissionDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      is_administrative: false,
      can_edit_model: false,
      permission_policy: 0,
    });
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, role: any) => {
    setMenuAnchor(event.currentTarget);
    setMenuRole(role);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
    setMenuRole(null);
  };

  const paginatedRoles = filteredRoles.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  return (
    <Box>
      {/* Statistics Cards */}
      {statistics && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Avatar sx={{ bgcolor: 'primary.main' }}>
                    <Security />
                  </Avatar>
                  <Box>
                    <Typography variant="h4">{statistics.total_roles}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Roles
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Avatar sx={{ bgcolor: 'error.main' }}>
                    <AdminPanelSettings />
                  </Avatar>
                  <Box>
                    <Typography variant="h4">{statistics.administrative_roles_count}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Admin Roles
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Avatar sx={{ bgcolor: 'success.main' }}>
                    <People />
                  </Avatar>
                  <Box>
                    <Typography variant="h4">
                      {statistics.roles_with_user_counts?.reduce(
                        (sum: number, r: any) => sum + r.user_count,
                        0
                      ) || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Assignments
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Header with Search and Actions */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
        <TextField
          fullWidth
          placeholder="Search roles..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
        />
        <Button variant="outlined" startIcon={<Refresh />} onClick={loadRoles}>
          Refresh
        </Button>
        <Button variant="contained" startIcon={<Add />} onClick={() => setCreateDialogOpen(true)}>
          Create Role
        </Button>
      </Box>

      {/* Roles Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Card>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Role Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Users</TableCell>
                  <TableCell>Permissions</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginatedRoles.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center">
                      <Typography variant="body1" color="text.secondary" sx={{ p: 3 }}>
                        No roles found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedRoles.map((role) => {
                    const roleStats = statistics?.roles_with_user_counts?.find(
                      (r: any) => r.role_id === role.oid
                    );
                    const userCount = roleStats?.user_count || 0;

                    return (
                      <TableRow key={role.oid} hover>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Avatar
                              sx={{
                                bgcolor: role.is_administrative ? 'error.light' : 'primary.light',
                              }}
                            >
                              {role.is_administrative ? <AdminPanelSettings /> : <Security />}
                            </Avatar>
                            <Box>
                              <Typography variant="subtitle2">{role.name}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                ID: {role.oid.substring(0, 8)}...
                              </Typography>
                            </Box>
                          </Box>
                        </TableCell>
                        <TableCell>
                          {role.is_administrative ? (
                            <Chip label="Administrative" color="error" size="small" />
                          ) : (
                            <Chip label="Standard" color="default" size="small" />
                          )}
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={<People />}
                            label={userCount}
                            color={userCount > 0 ? 'primary' : 'default'}
                            size="small"
                            onClick={() => loadRoleUsers(role)}
                            sx={{ cursor: 'pointer' }}
                          />
                        </TableCell>
                        <TableCell>
                          <Button
                            size="small"
                            startIcon={<VpnKey />}
                            onClick={() => openPermissionDialog(role)}
                          >
                            Manage
                          </Button>
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="Edit">
                            <IconButton size="small" onClick={() => openEditDialog(role)}>
                              <Edit />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={role.is_administrative ? "Cannot delete administrative role" : "Delete"}>
                            <span>
                              <IconButton
                                size="small"
                                onClick={() => openDeleteDialog(role)}
                                disabled={role.is_administrative}
                              >
                                <Delete />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <IconButton size="small" onClick={(e) => handleMenuOpen(e, role)}>
                            <MoreVert />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={filteredRoles.length}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[5, 10, 25, 50]}
          />
        </Card>
      )}

      {/* Action Menu */}
      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={handleMenuClose}>
        <MenuItem
          onClick={() => {
            if (menuRole) openEditDialog(menuRole);
            handleMenuClose();
          }}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          <ListItemText>Edit Role</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (menuRole) openPermissionDialog(menuRole);
            handleMenuClose();
          }}
        >
          <ListItemIcon>
            <VpnKey />
          </ListItemIcon>
          <ListItemText>Manage Permissions</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (menuRole) loadRoleUsers(menuRole);
            handleMenuClose();
          }}
        >
          <ListItemIcon>
            <People />
          </ListItemIcon>
          <ListItemText>View Users</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (menuRole) openDeleteDialog(menuRole);
            handleMenuClose();
          }}
          disabled={menuRole?.is_administrative}
        >
          <ListItemIcon>
            <Delete />
          </ListItemIcon>
          <ListItemText>Delete Role</ListItemText>
        </MenuItem>
      </Menu>

      {/* Create Role Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Role</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              fullWidth
              label="Role Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
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
            <FormControlLabel
              control={
                <Switch
                  checked={formData.can_edit_model}
                  onChange={(e) => setFormData({ ...formData, can_edit_model: e.target.checked })}
                />
              }
              label="Can Edit Model"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateRole} variant="contained" disabled={loading}>
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Role Dialog - Comprehensive */}
      {selectedRole && (
        <RoleEditDialog
          open={editDialogOpen}
          role={selectedRole}
          onClose={() => {
            setEditDialogOpen(false);
            setSelectedRole(null);
          }}
          onSuccess={() => {
            loadRoles();
            loadStatistics();
          }}
          showSnackbar={showSnackbar}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm">
        <DialogTitle>Delete Role</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete role <strong>{selectedRole?.name}</strong>? This action
            cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteRole} variant="contained" color="error" disabled={loading}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Role Users Dialog */}
      <Dialog open={usersDialogOpen} onClose={() => setUsersDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Users in Role: {selectedRole?.name}</DialogTitle>
        <DialogContent>
          {roleUsers.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
              No users assigned to this role
            </Typography>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Username</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {roleUsers.map((user: any) => (
                    <TableRow key={user.user_id || user.id}>
                      <TableCell>{user.username}</TableCell>
                      <TableCell>{user.email || 'N/A'}</TableCell>
                      <TableCell>
                        <Chip
                          label={user.active ? 'Active' : 'Inactive'}
                          color={user.active ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUsersDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Permission Assignment Dialog */}
      {selectedRole && (
        <PermissionAssignmentDialog
          open={permissionDialogOpen}
          role={selectedRole}
          onClose={() => {
            setPermissionDialogOpen(false);
            setSelectedRole(null);
          }}
          onSuccess={() => {
            showSnackbar('Permissions updated successfully', 'success');
          }}
        />
      )}
    </Box>
  );
}
