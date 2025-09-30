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
    if (open && user) {
      loadData();
    }
  }, [open, user]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load all available roles
      const roles = await RoleAPI.getRoles();
      setAllRoles(roles);

      // Load user's current roles
      const currentRoles = await UserRoleAPI.getUserRoles(user.id);
      setUserRoles(new Set(currentRoles.map((r: any) => r.role_id)));
    } catch (error) {
      console.error('Failed to load roles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRole = async (roleId: string, isChecked: boolean) => {
    setSaving(true);
    try {
      if (isChecked) {
        await UserRoleAPI.assignRole({
          user_id: user.id,
          role_id: roleId,
        });
      } else {
        await UserRoleAPI.removeRole(user.id, roleId);
      }

      // Update local state
      const newUserRoles = new Set(userRoles);
      if (isChecked) {
        newUserRoles.add(roleId);
      } else {
        newUserRoles.delete(roleId);
      }
      setUserRoles(newUserRoles);
    } catch (error) {
      console.error('Failed to update role:', error);
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
              {allRoles.map((role) => (
                <FormControlLabel
                  key={role.oid}
                  control={
                    <Checkbox
                      checked={userRoles.has(role.oid)}
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
              ))}
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
