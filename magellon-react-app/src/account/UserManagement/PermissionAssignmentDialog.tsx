'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  Chip,
  List,
  ListItem,
  Divider,
  CircularProgress,
} from '@mui/material';
import { VpnKey, Navigation, DataObject, CheckCircle } from '@mui/icons-material';

import { PermissionManagementAPI } from './rbacApi';

interface PermissionAssignmentDialogProps {
  open: boolean;
  role: any;
  onClose: () => void;
  onSuccess: () => void;
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
      id={`permission-dialog-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

export default function PermissionAssignmentDialog({
  open,
  role,
  onClose,
  onSuccess,
}: PermissionAssignmentDialogProps) {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [permissions, setPermissions] = useState<any>(null);

  useEffect(() => {
    if (open && role) {
      loadPermissions();
    }
  }, [open, role]);

  const loadPermissions = async () => {
    setLoading(true);
    try {
      const data = await PermissionManagementAPI.getRolePermissionsSummary(role.oid);
      setPermissions(data);
    } catch (error) {
      console.error('Failed to load permissions:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Manage Permissions - {role?.name}
        {role?.is_administrative && (
          <Chip label="Admin" color="error" size="small" sx={{ ml: 2 }} />
        )}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              View and manage permissions assigned to this role. Use the Permission Management tab
              to add or remove permissions.
            </Typography>

            <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 2 }}>
              <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
                <Tab icon={<VpnKey />} label="Actions" iconPosition="start" />
                <Tab icon={<Navigation />} label="Navigation" iconPosition="start" />
                <Tab icon={<DataObject />} label="Types" iconPosition="start" />
              </Tabs>
            </Box>

            {/* Action Permissions */}
            <TabPanel value={tabValue} index={0}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Action permissions control what specific operations this role can perform.
              </Typography>
              <Divider sx={{ my: 2 }} />
              {permissions?.permissions.actions && permissions.permissions.actions.length > 0 ? (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {permissions.permissions.actions.map((action: string) => (
                    <Chip key={action} label={action} color="primary" />
                  ))}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                  No action permissions assigned
                </Typography>
              )}
            </TabPanel>

            {/* Navigation Permissions */}
            <TabPanel value={tabValue} index={1}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Navigation permissions control which pages and menu items this role can access.
              </Typography>
              <Divider sx={{ my: 2 }} />
              {permissions?.permissions.navigation && permissions.permissions.navigation.length > 0 ? (
                <List dense>
                  {permissions.permissions.navigation.map((nav: any, index: number) => (
                    <ListItem key={index}>
                      <CheckCircle
                        color={nav.allowed ? 'success' : 'error'}
                        fontSize="small"
                        sx={{ mr: 2 }}
                      />
                      <Typography variant="body2">{nav.path}</Typography>
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                  No navigation permissions assigned
                </Typography>
              )}
            </TabPanel>

            {/* Type Permissions */}
            <TabPanel value={tabValue} index={2}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Type permissions control CRUD operations on entity types.
              </Typography>
              <Divider sx={{ my: 2 }} />
              {permissions?.permissions.types && permissions.permissions.types.length > 0 ? (
                <List>
                  {permissions.permissions.types.map((type: any, index: number) => (
                    <ListItem key={index}>
                      <Box sx={{ width: '100%' }}>
                        <Typography variant="subtitle2" gutterBottom>
                          {type.type}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {type.read && <Chip label="Read" size="small" color="success" />}
                          {type.write && <Chip label="Write" size="small" color="info" />}
                          {type.create && <Chip label="Create" size="small" color="primary" />}
                          {type.delete && <Chip label="Delete" size="small" color="error" />}
                          {type.navigate && <Chip label="Navigate" size="small" color="default" />}
                        </Box>
                      </Box>
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 2 }}>
                  No type permissions assigned
                </Typography>
              )}
            </TabPanel>

            {/* Permission Counts */}
            {permissions?.counts && (
              <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Permission Summary
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Chip
                    icon={<VpnKey />}
                    label={`${permissions.counts.actions} Actions`}
                    size="small"
                  />
                  <Chip
                    icon={<Navigation />}
                    label={`${permissions.counts.navigation} Navigation`}
                    size="small"
                  />
                  <Chip
                    icon={<DataObject />}
                    label={`${permissions.counts.types} Types`}
                    size="small"
                  />
                </Box>
              </Box>
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
