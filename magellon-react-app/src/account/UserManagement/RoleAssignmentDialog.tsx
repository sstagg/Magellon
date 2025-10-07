'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Typography,
  CircularProgress,
  Box,
  Chip,
  Divider,
} from '@mui/material';
import { AdminPanelSettings, Security } from '@mui/icons-material';

import { RoleAPI, UserRoleAPI } from './rbacApi';

interface RoleAssignmentDialogProps {
  open: boolean;
  user: any;
  onClose: () => void;
  onSuccess: () => void;
}

export default function RoleAssignmentDialog({
  open,
  user,
  onClose,
  onSuccess,
}: RoleAssignmentDialogProps) {
  const [loading, setLoading] = useState(false);
  const [allRoles, setAllRoles] = useState<any[]>([]);
  const [userRoles, setUserRoles] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && user && (user.id || user.oid)) {
      loadData();
    }
  }, [open, user]);

  const loadData = async () => {
    const userId = user?.id || user?.oid;
    if (!user || !userId) {
      console.error('User or user ID is undefined', user);
      return;
    }

    setLoading(true);
    try {
      // Load all available roles
      console.log('Loading all roles...');
      const roles = await RoleAPI.getRoles();
      console.log('Loaded roles:', roles);
      setAllRoles(roles);

      // Load user's current roles
      console.log('Loading user roles for user ID:', userId);
      const currentRoles = await UserRoleAPI.getUserRoles(userId);
      console.log('User current roles:', currentRoles);
      setUserRoles(new Set(currentRoles.map((r: any) => r.role_id)));
    } catch (error) {
      console.error('Failed to load roles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRole = async (roleId: string, isChecked: boolean) => {
    const userId = user?.id || user?.oid;
    if (!userId) {
      console.error('Cannot toggle role: user ID is undefined');
      return;
    }

    console.log('Toggling role:', { roleId, isChecked, userId });

    setSaving(true);
    try {
      if (isChecked) {
        console.log('Assigning role...');
        await UserRoleAPI.assignRole({
          user_id: userId,
          role_id: roleId,
        });
        console.log('Role assigned successfully');
      } else {
        console.log('Removing role...');
        await UserRoleAPI.removeRole(userId, roleId);
        console.log('Role removed successfully');
      }

      // Update local state immediately
      const newUserRoles = new Set(userRoles);
      if (isChecked) {
        newUserRoles.add(roleId);
      } else {
        newUserRoles.delete(roleId);
      }
      console.log('Updated user roles set:', newUserRoles);
      setUserRoles(newUserRoles);

      // Notify parent of success
      onSuccess();
    } catch (error) {
      console.error('Failed to update role:', error);
      alert('Failed to update role: ' + (error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Manage Roles - {user?.username}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Assign or remove roles for this user. Changes are applied immediately.
            </Typography>
            <Divider sx={{ my: 2 }} />
            <FormGroup>
              {allRoles.map((role) => {
                const isChecked = userRoles.has(role.oid);
                console.log(`Role ${role.name} (${role.oid}): checked=${isChecked}, userRoles has:`, Array.from(userRoles));
                return (
                  <FormControlLabel
                    key={role.oid}
                    control={
                      <Checkbox
                        checked={isChecked}
                        onChange={(e) => handleToggleRole(role.oid, e.target.checked)}
                        disabled={saving}
                      />
                    }
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {role.is_administrative ? (
                          <AdminPanelSettings fontSize="small" color="error" />
                        ) : (
                          <Security fontSize="small" color="primary" />
                        )}
                        <Typography variant="body1">{role.name}</Typography>
                        {role.is_administrative && (
                          <Chip label="Admin" color="error" size="small" />
                        )}
                      </Box>
                    }
                  />
                );
              })}
            </FormGroup>
            {allRoles.length === 0 && (
              <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                No roles available
              </Typography>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button
          onClick={() => {
            onSuccess();
            onClose();
          }}
          variant="contained"
        >
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}
