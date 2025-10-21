/**
 * Object Permissions Manager
 *
 * Manages record-level (object) permissions for a type permission.
 * Allows creating criteria-based access control rules.
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  FormControlLabel,
  Switch,
  Grid,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  FilterList,
  CheckCircle,
  Cancel,
} from '@mui/icons-material';
import axios from 'axios';
import CriteriaBuilder from './CriteriaBuilder';
import { useSchema } from '../hooks/useSchema';
import { DatabaseSchema } from '../types/databaseSchema';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

interface ObjectPermission {
  oid: string;
  criteria: string;
  read_state: number;
  write_state: number;
  delete_state: number;
  navigate_state: number;
  type_permission_object: string;
  optimistic_lock_field: number;
  gc_record: number | null;
}

interface ObjectPermissionsManagerProps {
  typePermissionId: string;
  targetTypeName: string;
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

export default function ObjectPermissionsManager({
  typePermissionId,
  targetTypeName,
  showSnackbar,
}: ObjectPermissionsManagerProps) {
  const { schema, loading: schemaLoading, error: schemaError } = useSchema(false);

  const [objectPermissions, setObjectPermissions] = useState<ObjectPermission[]>([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPermission, setEditingPermission] = useState<ObjectPermission | null>(null);

  // Form state
  const [criteria, setCriteria] = useState('');
  const [readState, setReadState] = useState(true);
  const [writeState, setWriteState] = useState(false);
  const [deleteState, setDeleteState] = useState(false);
  const [navigateState, setNavigateState] = useState(true);

  useEffect(() => {
    if (typePermissionId) {
      loadObjectPermissions();
    }
  }, [typePermissionId]);

  const loadObjectPermissions = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get<ObjectPermission[]>(
        `/db/security/permissions/objects/type/${typePermissionId}`
      );
      setObjectPermissions(response.data);
    } catch (error: any) {
      console.error('Failed to load object permissions:', error);
      showSnackbar('Failed to load object permissions', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (permission?: ObjectPermission) => {
    console.log('handleOpenDialog called', { permission, typePermissionId, targetTypeName });
    if (permission) {
      // Edit existing
      setEditingPermission(permission);
      setCriteria(permission.criteria);
      setReadState(permission.read_state === 1);
      setWriteState(permission.write_state === 1);
      setDeleteState(permission.delete_state === 1);
      setNavigateState(permission.navigate_state === 1);
    } else {
      // Create new
      setEditingPermission(null);
      setCriteria('');
      setReadState(true);
      setWriteState(false);
      setDeleteState(false);
      setNavigateState(true);
    }
    setDialogOpen(true);
    console.log('Dialog opened, dialogOpen=true');
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingPermission(null);
    setCriteria('');
  };

  const handleSave = async () => {
    if (!criteria.trim()) {
      showSnackbar('Criteria cannot be empty', 'error');
      return;
    }

    try {
      const payload = {
        type_permission_object: typePermissionId,
        criteria: criteria.trim(),
        read_state: readState ? 1 : 0,
        write_state: writeState ? 1 : 0,
        delete_state: deleteState ? 1 : 0,
        navigate_state: navigateState ? 1 : 0,
      };

      if (editingPermission) {
        // Update existing
        await apiClient.put(
          `/db/security/permissions/objects/${editingPermission.oid}`,
          payload
        );
        showSnackbar('Object permission updated successfully', 'success');
      } else {
        // Create new
        await apiClient.post('/db/security/permissions/objects', payload);
        showSnackbar('Object permission created successfully', 'success');
      }

      handleCloseDialog();
      loadObjectPermissions();
    } catch (error: any) {
      console.error('Failed to save object permission:', error);
      showSnackbar(
        error.response?.data?.detail || 'Failed to save object permission',
        'error'
      );
    }
  };

  const handleDelete = async (permissionId: string) => {
    if (!confirm('Are you sure you want to delete this object permission?')) {
      return;
    }

    try {
      await apiClient.delete(`/db/security/permissions/objects/${permissionId}`);
      showSnackbar('Object permission deleted successfully', 'success');
      loadObjectPermissions();
    } catch (error: any) {
      console.error('Failed to delete object permission:', error);
      showSnackbar('Failed to delete object permission', 'error');
    }
  };

  const renderPermissionIcon = (state: number) => {
    return state === 1 ? (
      <CheckCircle fontSize="small" color="success" />
    ) : (
      <Cancel fontSize="small" color="disabled" />
    );
  };

  if (schemaLoading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  if (schemaError) {
    return <Alert severity="error">{schemaError}</Alert>;
  }

  if (!schema) {
    return <Alert severity="warning">Schema not loaded</Alert>;
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Object Permissions (Record-Level)
        </Typography>
        <Button
          startIcon={<Add />}
          variant="contained"
          onClick={() => handleOpenDialog()}
        >
          Add Object Permission
        </Button>
      </Box>

      {/* Info */}
      <Alert severity="info" icon={<FilterList />} sx={{ mb: 2 }}>
        <strong>Object Permissions for: {targetTypeName}</strong>
        <br />
        Object permissions define criteria-based record-level access control.
        Use criteria expressions to filter which records users can access.
        <br />
        <br />
        <strong>Debug Info:</strong> Loaded {objectPermissions.length} object permission(s)
      </Alert>

      {/* Permissions List */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={3}>
          <CircularProgress />
        </Box>
      ) : objectPermissions.length === 0 ? (
        <Card sx={{ bgcolor: 'background.default', border: '2px dashed #ccc' }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <FilterList sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No Object Permissions Yet
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              This type permission has no record-level filters defined.
              <br />
              Users will have access to ALL records of type <strong>{targetTypeName}</strong>
              <br />
              (subject to type-level permissions).
            </Typography>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => handleOpenDialog()}
              size="large"
              sx={{ mt: 2 }}
            >
              Create Your First Object Permission
            </Button>
            <Box sx={{ mt: 3, textAlign: 'left', maxWidth: 500, mx: 'auto' }}>
              <Typography variant="caption" color="text.secondary">
                <strong>Examples you can create:</strong>
              </Typography>
              <Typography variant="caption" component="div" color="text.secondary" sx={{ mt: 1 }}>
                • Users can only see their own records: <code>[user_id] = CurrentUserId()</code>
                <br />
                • Users can see active records: <code>[status] = 'active'</code>
                <br />
                • Users can see records they own or are assigned to: <code>[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()</code>
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <List>
          {objectPermissions.map((perm, index) => (
            <Card key={perm.oid} sx={{ mb: 2 }}>
              <CardContent>
                <Grid container spacing={2}>
                  {/* Criteria */}
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Criteria #{index + 1}
                    </Typography>
                    <Typography
                      variant="body2"
                      component="pre"
                      sx={{
                        bgcolor: 'background.default',
                        p: 1,
                        borderRadius: 1,
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                      }}
                    >
                      {perm.criteria || '(No criteria)'}
                    </Typography>
                  </Grid>

                  {/* Permissions */}
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      <Chip
                        icon={renderPermissionIcon(perm.read_state)}
                        label="Read"
                        size="small"
                        color={perm.read_state === 1 ? 'success' : 'default'}
                      />
                      <Chip
                        icon={renderPermissionIcon(perm.write_state)}
                        label="Write"
                        size="small"
                        color={perm.write_state === 1 ? 'success' : 'default'}
                      />
                      <Chip
                        icon={renderPermissionIcon(perm.delete_state)}
                        label="Delete"
                        size="small"
                        color={perm.delete_state === 1 ? 'success' : 'default'}
                      />
                      <Chip
                        icon={renderPermissionIcon(perm.navigate_state)}
                        label="Navigate"
                        size="small"
                        color={perm.navigate_state === 1 ? 'success' : 'default'}
                      />
                    </Box>
                  </Grid>

                  {/* Actions */}
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenDialog(perm)}
                        >
                          <Edit fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDelete(perm.oid)}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          ))}
        </List>
      )}

      {/* Create/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editingPermission ? 'Edit Object Permission' : 'Create Object Permission'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            {/* DEBUG INFO - Remove after testing */}
            <Alert severity="info" sx={{ mb: 2 }}>
              <strong>Debug:</strong>
              <br />
              Entity Name: {targetTypeName}
              <br />
              Schema Loaded: {schema ? 'Yes' : 'No'}
              <br />
              Entity Exists: {schema?.entities?.[targetTypeName] ? 'Yes' : 'No'}
              <br />
              {schema?.entities?.[targetTypeName] && (
                <>
                  Fields Available: {Object.keys(schema.entities[targetTypeName].fields || {}).length}
                </>
              )}
            </Alert>

            {/* Criteria Builder */}
            {!schema?.entities?.[targetTypeName] ? (
              <Alert severity="error">
                Entity "{targetTypeName}" not found in schema!
                <br />
                Available entities: {schema?.entities ? Object.keys(schema.entities).join(', ') : 'none'}
              </Alert>
            ) : (
              <CriteriaBuilder
                schema={schema}
                entityName={targetTypeName}
                initialCriteria={criteria}
                onChange={setCriteria}
              />
            )}

            <Divider sx={{ my: 3 }} />

            {/* Operation Toggles */}
            <Typography variant="subtitle1" gutterBottom>
              Allowed Operations
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={readState}
                      onChange={(e) => setReadState(e.target.checked)}
                    />
                  }
                  label="Read (View records)"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={writeState}
                      onChange={(e) => setWriteState(e.target.checked)}
                    />
                  }
                  label="Write (Edit records)"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={deleteState}
                      onChange={(e) => setDeleteState(e.target.checked)}
                    />
                  }
                  label="Delete (Remove records)"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={navigateState}
                      onChange={(e) => setNavigateState(e.target.checked)}
                    />
                  }
                  label="Navigate (Browse records)"
                />
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained" color="primary">
            {editingPermission ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
