'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Container,
    Paper,
    Typography,
    Tabs,
    Tab,
    CircularProgress,
    Alert,
    Snackbar, Chip,
} from '@mui/material';
import {
    Person,
    Security,
    Shield,
    AdminPanelSettings,
    SupervisorAccount,
    Lock,
} from '@mui/icons-material';

// Import modular components
import UserManagementTab from './UserManagementTab';
import RoleManagementTab from './RoleManagementTab';
import PermissionManagementTab from './PermissionManagementTab';
import PermissionCheckerTab from './PermissionCheckerTab';
import SessionAccessManagementTab from './SessionAccessManagementTab';

// Import services
import { useAuth } from './AuthContext';
import { PermissionAPI } from './rbacApi';

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
            id={`account-tabpanel-${index}`}
            aria-labelledby={`account-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
        </div>
    );
}

export default function AccountPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const [tabValue, setTabValue] = useState(0);
    const [loading, setLoading] = useState(true);
    const [isAdmin, setIsAdmin] = useState(false);
    const [isSuperUser, setIsSuperUser] = useState(false);

    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error' | 'info' | 'warning',
    });

    useEffect(() => {
        if (!authLoading && user) {
            checkUserPermissions();
        } else if (!authLoading && !user) {
            setLoading(false);
        }
    }, [user, authLoading]);

    const checkUserPermissions = async () => {
        if (!user?.id) {
            setLoading(false);
            return;
        }

        setLoading(true);
        try {
            // Check if username is "super" - if so, grant superuser status
            const isSuperUserByUsername = user.username?.toLowerCase() === 'super';
            setIsSuperUser(isSuperUserByUsername);

            if (isSuperUserByUsername) {
                // Super user gets all permissions regardless of database
                setIsAdmin(true);
                console.log('Super user detected - granting full permissions');
            } else {
                // Regular user - check database permissions
                try {
                    const adminCheck = await PermissionAPI.isAdmin(user.id);
                    setIsAdmin(adminCheck.is_admin);
                } catch (error) {
                    console.error('Failed to check admin status:', error);
                    setIsAdmin(false);
                }
            }
        } catch (error) {
            console.error('Error checking user permissions:', error);
            setIsAdmin(false);
            setIsSuperUser(false);
        } finally {
            setLoading(false);
        }
    };

    const showSnackbar = (message: string, severity: 'success' | 'error' | 'info' | 'warning') => {
        setSnackbar({ open: true, message, severity });
    };

    // Show loading while auth is loading
    if (authLoading) {
        return (
            <Container maxWidth="xl">
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                    <CircularProgress />
                </Box>
            </Container>
        );
    }

    // Show message if not authenticated
    if (!isAuthenticated || !user) {
        return (
            <Container maxWidth="xl">
                <Box sx={{ py: 4 }}>
                    <Alert severity="warning">
                        You must be logged in to access account settings.
                    </Alert>
                </Box>
            </Container>
        );
    }

    // Show loading while checking permissions
    if (loading) {
        return (
            <Container maxWidth="xl">
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                    <CircularProgress />
                </Box>
            </Container>
        );
    }

    // Build tabs array to avoid Fragment issue
    const tabs = [
        <Tab key="profile" icon={<Person />} label="My Profile" iconPosition="start" />
    ];

    if (isAdmin || isSuperUser) {
        tabs.push(
            <Tab key="users" icon={<AdminPanelSettings />} label="User Management" iconPosition="start" />,
            <Tab key="roles" icon={<Security />} label="Role Management" iconPosition="start" />,
            <Tab key="permissions" icon={<Shield />} label="Permissions" iconPosition="start" />,
            <Tab key="checker" icon={<Security />} label="Permission Checker" iconPosition="start" />,
            <Tab key="session-access" icon={<Lock />} label="Session Access" iconPosition="start" />
        );
    }

    return (
        <Container maxWidth="xl">
            <Box sx={{ py: 4 }}>
                {/* Header */}
                <Paper sx={{ p: 3, mb: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                                <Typography variant="h4">
                                    Account Management
                                </Typography>
                                {isSuperUser && (
                                    <Chip
                                        icon={<SupervisorAccount />}
                                        label="SUPER USER"
                                        color="error"
                                        variant="filled"
                                        sx={{
                                            fontWeight: 'bold',
                                            fontSize: '0.875rem',
                                            animation: 'pulse 2s ease-in-out infinite',
                                            '@keyframes pulse': {
                                                '0%, 100%': {
                                                    opacity: 1,
                                                },
                                                '50%': {
                                                    opacity: 0.7,
                                                },
                                            },
                                        }}
                                    />
                                )}
                            </Box>
                            <Typography variant="body1" color="text.secondary">
                                {isSuperUser
                                    ? '🔐 Super user mode - Full system access with all permissions'
                                    : isAdmin
                                        ? 'Manage users, roles, and permissions across the system'
                                        : 'Manage your profile and view your permissions'}
                            </Typography>
                        </Box>
                    </Box>
                </Paper>

                {/* Super User Info Alert */}
                {isSuperUser && (
                    <Alert
                        severity="info"
                        sx={{ mb: 3 }}
                        icon={<SupervisorAccount />}
                    >
                        <Typography variant="subtitle2" gutterBottom>
                            <strong>Super User Mode Active</strong>
                        </Typography>
                        <Typography variant="body2">
                            You are logged in as the super user. You have unrestricted access to all features,
                            roles, and permissions regardless of database configuration. Use this power responsibly.
                        </Typography>
                    </Alert>
                )}

                {/* Tabs */}
                <Paper>
                    <Tabs
                        value={tabValue}
                        onChange={(_, newValue) => setTabValue(newValue)}
                        variant="scrollable"
                        scrollButtons="auto"
                        sx={{ borderBottom: 1, borderColor: 'divider' }}
                    >
                        {tabs}
                    </Tabs>

                    {/* My Profile Tab */}
                    <TabPanel value={tabValue} index={0}>
                        <UserManagementTab
                            currentUser={user}
                            isAdmin={isAdmin || isSuperUser}
                            onUpdate={checkUserPermissions}
                            showSnackbar={showSnackbar}
                            isSuperUser={isSuperUser}
                        />
                    </TabPanel>

                    {/* Admin Tabs */}
                    {(isAdmin || isSuperUser) && (
                        <>
                            <TabPanel value={tabValue} index={1}>
                                <UserManagementTab
                                    currentUser={user}
                                    isAdmin={isAdmin || isSuperUser}
                                    onUpdate={checkUserPermissions}
                                    showSnackbar={showSnackbar}
                                    adminMode
                                    isSuperUser={isSuperUser}
                                />
                            </TabPanel>

                            <TabPanel value={tabValue} index={2}>
                                <RoleManagementTab
                                    currentUser={user}
                                    showSnackbar={showSnackbar}
                                    isSuperUser={isSuperUser}
                                />
                            </TabPanel>

                            <TabPanel value={tabValue} index={3}>
                                <PermissionManagementTab
                                    currentUser={user}
                                    showSnackbar={showSnackbar}
                                    isSuperUser={isSuperUser}
                                />
                            </TabPanel>

                            <TabPanel value={tabValue} index={4}>
                                <PermissionCheckerTab
                                    currentUser={user}
                                    showSnackbar={showSnackbar}
                                />
                            </TabPanel>

                            <TabPanel value={tabValue} index={5}>
                                <SessionAccessManagementTab
                                    currentUser={user}
                                    showSnackbar={showSnackbar}
                                    isSuperUser={isSuperUser}
                                />
                            </TabPanel>
                        </>
                    )}
                </Paper>

                {/* Snackbar */}
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                >
                    <Alert
                        severity={snackbar.severity}
                        onClose={() => setSnackbar({ ...snackbar, open: false })}
                        variant="filled"
                        sx={{ width: '100%' }}
                    >
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>
        </Container>
    );
}
