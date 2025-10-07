'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  Button,
  TextField,
  Chip,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Divider,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Add,
  Delete,
  VpnKey,
  Navigation,
  DataObject,
  Refresh,
} from '@mui/icons-material';

import { RoleAPI, PermissionManagementAPI } from './rbacApi';

interface PermissionManagementTabProps {
  currentUser: any;
  showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
  isSuperUser?: boolean;
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
      id={`permission-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

export default function PermissionManagementTab({
  currentUser,
  showSnackbar,
  isSuperUser = false,
}: PermissionManagementTabProps) {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<any[]>([]);
  const [selectedRole, setSelectedRole] = useState<string>('');

  // Action Permissions
  const [actionPermissions, setActionPermissions] = useState<any[]>([]);
  const [newAction, setNewAction] = useState('');

  // Navigation Permissions
  const [navigationPermissions, setNavigationPermissions] = useState<any[]>([]);
  const [newNavPath, setNewNavPath] = useState('');
  const [navAllowed, setNavAllowed] = useState(true);

  // Type Permissions
  const [typePermissions, setTypePermissions] = useState<any[]>([]);
  const [newType, setNewType] = useState('');
  const [typeStates, setTypeStates] = useState({
    read: false,
    write: false,
    create: false,
    delete: false,
    navigate: false,
  });

  // Quick Actions Dialog
  const [quickActionDialogOpen, setQuickActionDialogOpen] = useState(false);
  const [quickActionType, setQuickActionType] = useState<'full' | 'readonly'>('full');

  useEffect(() => {
    loadRoles();
  }, []);

  useEffect(() => {
    if (selectedRole) {
      loadPermissions();
    }
  }, [selectedRole]);

  const loadRoles = async () => {
    try {
      const data = await RoleAPI.getRoles();
      setRoles(data);
      if (data.length > 0 && !selectedRole) {
        setSelectedRole(data[0].oid);
      }
    } catch (error: any) {
      console.error('Failed to load roles:', error);
      showSnackbar('Failed to load roles', 'error');
    }
  };

  const loadPermissions = async () => {
    if (!selectedRole) return;

    setLoading(true);
    try {
      const [actions, navigation, types] = await Promise.all([
        PermissionManagementAPI.getRoleActionPermissions(selectedRole),
        PermissionManagementAPI.getRoleNavigationPermissions(selectedRole),
        PermissionManagementAPI.getRoleTypePermissions(selectedRole),
      ]);

      setActionPermissions(actions);
      setNavigationPermissions(navigation);
      setTypePermissions(types);
    } catch (error: any) {
      console.error('Failed to load permissions:', error);
      showSnackbar('Failed to load permissions', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Action Permissions Handlers
  const handleAddAction = async () => {
    if (!newAction.trim() || !selectedRole) return;

    setLoading(true);
    try {
      await PermissionManagementAPI.createActionPermission({
        action_id: newAction,
        role_id: selectedRole,
      });
      showSnackbar('Action permission added', 'success');
      setNewAction('');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to add action permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAction = async (permissionId: string) => {
    setLoading(true);
    try {
      await PermissionManagementAPI.deleteActionPermission(permissionId);
      showSnackbar('Action permission deleted', 'success');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to delete action permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Navigation Permissions Handlers
  const handleAddNavigation = async () => {
    if (!newNavPath.trim() || !selectedRole) return;

    setLoading(true);
    try {
      await PermissionManagementAPI.createNavigationPermission({
        item_path: newNavPath,
        navigate_state: navAllowed ? 1 : 0,
        role_id: selectedRole,
      });
      showSnackbar('Navigation permission added', 'success');
      setNewNavPath('');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to add navigation permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteNavigation = async (permissionId: string) => {
    setLoading(true);
    try {
      await PermissionManagementAPI.deleteNavigationPermission(permissionId);
      showSnackbar('Navigation permission deleted', 'success');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to delete navigation permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleNavigation = async (permissionId: string, currentState: number) => {
    setLoading(true);
    try {
      await PermissionManagementAPI.updateNavigationPermission(
        permissionId,
        currentState === 1 ? 0 : 1
      );
      showSnackbar('Navigation permission updated', 'success');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to update navigation permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Type Permissions Handlers
  const handleAddType = async () => {
    if (!newType.trim() || !selectedRole) return;

    setLoading(true);
    try {
      await PermissionManagementAPI.createTypePermission({
        target_type: newType,
        role: selectedRole,
        read_state: typeStates.read ? 1 : 0,
        write_state: typeStates.write ? 1 : 0,
        create_state: typeStates.create ? 1 : 0,
        delete_state: typeStates.delete ? 1 : 0,
        navigate_state: typeStates.navigate ? 1 : 0,
      });
      showSnackbar('Type permission added', 'success');
      setNewType('');
      setTypeStates({
        read: false,
        write: false,
        create: false,
        delete: false,
        navigate: false,
      });
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to add type permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteType = async (permissionId: string) => {
    setLoading(true);
    try {
      await PermissionManagementAPI.deleteTypePermission(permissionId);
      showSnackbar('Type permission deleted', 'success');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to delete type permission: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickAction = async () => {
    if (!newType.trim() || !selectedRole) return;

    setLoading(true);
    try {
      if (quickActionType === 'full') {
        await PermissionManagementAPI.grantFullAccess(selectedRole, newType);
      } else {
        await PermissionManagementAPI.grantReadOnly(selectedRole, newType);
      }
      showSnackbar(`${quickActionType === 'full' ? 'Full access' : 'Read-only'} granted`, 'success');
      setQuickActionDialogOpen(false);
      setNewType('');
      loadPermissions();
    } catch (error: any) {
      showSnackbar('Failed to grant access: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const selectedRoleName = roles.find((r) => r.oid === selectedRole)?.name || '';

  return (
    <Box>
      {/* Role Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Select Role</InputLabel>
                <Select
                  value={selectedRole}
                  label="Select Role"
                  onChange={(e) => setSelectedRole(e.target.value)}
                >
                  {roles.map((role) => (
                    <MenuItem key={role.oid} value={role.oid}>
                      {role.name} {role.is_administrative && '(Admin)'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                <Button startIcon={<Refresh />} onClick={loadPermissions} disabled={loading}>
                  Refresh
                </Button>
              </Box>
            </Grid>
          </Grid>

          {selectedRoleName && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Managing permissions for: <strong>{selectedRoleName}</strong>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Tabs */}
      <Card>
        <Tabs
          value={tabValue}
          onChange={(_, newValue) => setTabValue(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab icon={<VpnKey />} label="Action Permissions" iconPosition="start" />
          <Tab icon={<Navigation />} label="Navigation Permissions" iconPosition="start" />
          <Tab icon={<DataObject />} label="Type Permissions" iconPosition="start" />
        </Tabs>

        {/* Action Permissions Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" paragraph>
              Action permissions control specific operations that users with this role can perform.
            </Typography>

            {/* Add Action */}
            <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Enter action ID (e.g., CreateInvoice)"
                value={newAction}
                onChange={(e) => setNewAction(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddAction()}
              />
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleAddAction}
                disabled={loading || !newAction.trim()}
              >
                Add
              </Button>
            </Box>

            {/* Actions List */}
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
              </Box>
            ) : actionPermissions.length === 0 ? (
              <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                No action permissions assigned
              </Typography>
            ) : (
              <List>
                {actionPermissions.map((perm) => (
                  <ListItem
                    key={perm.oid}
                    secondaryAction={
                      <IconButton edge="end" onClick={() => handleDeleteAction(perm.oid)}>
                        <Delete />
                      </IconButton>
                    }
                  >
                    <Chip label={perm.action_id} color="primary" />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </TabPanel>

        {/* Navigation Permissions Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" paragraph>
              Navigation permissions control which pages and menu items users with this role can access.
            </Typography>

            {/* Add Navigation */}
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Enter path (e.g., /admin/dashboard)"
                value={newNavPath}
                onChange={(e) => setNewNavPath(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddNavigation()}
              />
              <FormControlLabel
                control={
                  <Switch checked={navAllowed} onChange={(e) => setNavAllowed(e.target.checked)} />
                }
                label="Allow"
              />
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleAddNavigation}
                disabled={loading || !newNavPath.trim()}
              >
                Add
              </Button>
            </Box>

            {/* Navigation List */}
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
              </Box>
            ) : navigationPermissions.length === 0 ? (
              <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                No navigation permissions assigned
              </Typography>
            ) : (
              <List>
                {navigationPermissions.map((perm) => (
                  <ListItem
                    key={perm.oid}
                    secondaryAction={
                      <>
                        <Switch
                          checked={perm.navigate_state === 1}
                          onChange={() => handleToggleNavigation(perm.oid, perm.navigate_state)}
                          disabled={loading}
                        />
                        <IconButton edge="end" onClick={() => handleDeleteNavigation(perm.oid)}>
                          <Delete />
                        </IconButton>
                      </>
                    }
                  >
                    <ListItemText
                      primary={perm.item_path}
                      secondary={perm.navigate_state === 1 ? 'Allowed' : 'Denied'}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </TabPanel>

        {/* Type Permissions Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" paragraph>
              Type permissions control CRUD operations on entity types (like Property, Invoice, etc.)
            </Typography>

            {/* Quick Actions */}
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <Button
                variant="outlined"
                onClick={() => {
                  setQuickActionType('full');
                  setQuickActionDialogOpen(true);
                }}
              >
                Grant Full Access
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  setQuickActionType('readonly');
                  setQuickActionDialogOpen(true);
                }}
              >
                Grant Read Only
              </Button>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Add Type Permission */}
            <TextField
              fullWidth
              size="small"
              placeholder="Enter type name (e.g., Property)"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              sx={{ mb: 2 }}
            />

            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={6} sm={4} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={typeStates.read}
                      onChange={(e) => setTypeStates({ ...typeStates, read: e.target.checked })}
                    />
                  }
                  label="Read"
                />
              </Grid>
              <Grid item xs={6} sm={4} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={typeStates.write}
                      onChange={(e) => setTypeStates({ ...typeStates, write: e.target.checked })}
                    />
                  }
                  label="Write"
                />
              </Grid>
              <Grid item xs={6} sm={4} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={typeStates.create}
                      onChange={(e) => setTypeStates({ ...typeStates, create: e.target.checked })}
                    />
                  }
                  label="Create"
                />
              </Grid>
              <Grid item xs={6} sm={4} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={typeStates.delete}
                      onChange={(e) => setTypeStates({ ...typeStates, delete: e.target.checked })}
                    />
                  }
                  label="Delete"
                />
              </Grid>
              <Grid item xs={6} sm={4} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={typeStates.navigate}
                      onChange={(e) => setTypeStates({ ...typeStates, navigate: e.target.checked })}
                    />
                  }
                  label="Navigate"
                />
              </Grid>
            </Grid>

            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleAddType}
              disabled={loading || !newType.trim()}
              fullWidth
            >
              Add Type Permission
            </Button>

            <Divider sx={{ my: 3 }} />

            {/* Type Permissions List */}
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
              </Box>
            ) : typePermissions.length === 0 ? (
              <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                No type permissions assigned
              </Typography>
            ) : (
              <List>
                {typePermissions.map((perm) => (
                  <ListItem
                    key={perm.oid}
                    secondaryAction={
                      <IconButton edge="end" onClick={() => handleDeleteType(perm.oid)}>
                        <Delete />
                      </IconButton>
                    }
                  >
                    <ListItemText
                      primary={perm.target_type}
                      secondary={
                        <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                          {perm.read_state === 1 && <Chip label="Read" size="small" color="success" />}
                          {perm.write_state === 1 && <Chip label="Write" size="small" color="info" />}
                          {perm.create_state === 1 && <Chip label="Create" size="small" color="primary" />}
                          {perm.delete_state === 1 && <Chip label="Delete" size="small" color="error" />}
                          {perm.navigate_state === 1 && <Chip label="Navigate" size="small" color="default" />}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </TabPanel>
      </Card>

      {/* Quick Action Dialog */}
      <Dialog open={quickActionDialogOpen} onClose={() => setQuickActionDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {quickActionType === 'full' ? 'Grant Full Access' : 'Grant Read-Only Access'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Type Name"
            placeholder="e.g., Property, Invoice, User"
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            sx={{ mt: 2 }}
          />
          <Alert severity="info" sx={{ mt: 2 }}>
            {quickActionType === 'full'
              ? 'This will grant Create, Read, Update, Delete, and Navigate permissions.'
              : 'This will grant only Read and Navigate permissions.'}
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setQuickActionDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleQuickAction} variant="contained" disabled={loading || !newType.trim()}>
            Grant Access
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
