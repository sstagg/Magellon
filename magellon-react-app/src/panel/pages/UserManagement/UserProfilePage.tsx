import React, { useState, useEffect } from 'react';
import {
    Box,
    Container,
    Paper,
    Typography,
    Button,
    Grid,
    Card,
    CardContent,
    Avatar,
    Divider,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Alert,
    Snackbar,
    Chip,
    IconButton,
    InputAdornment,
    FormControlLabel,
    Switch,
    useTheme,
    alpha,
    Stack,
    CircularProgress
} from '@mui/material';
import {
    Person,
    Edit,
    Lock,
    VpnKey,
    History,
    Security,
    Visibility,
    VisibilityOff,
    Save,
    Cancel,
    Info,
    Schedule,
    Badge,
    Computer,
    Warning
} from '@mui/icons-material';
import { userApiService, ApiUser } from './userApi';

interface ProfileData {
    id: string;
    username: string;
    active: boolean;
    created_date: Date | null;
    last_modified_date: Date | null;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    change_password_on_first_logon?: boolean;
    object_type?: number;
    access_failed_count?: number;
    lockout_end?: Date | null;
}

interface PasswordChangeData {
    currentPassword: string;
    newPassword: string;
    confirmNewPassword: string;
}

const UserProfilePage: React.FC = () => {
    const theme = useTheme();
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Edit mode states
    const [isEditing, setIsEditing] = useState(false);
    const [editData, setEditData] = useState({
        username: '',
        ouid: '',
        version: ''
    });

    // Password change dialog
    const [isPasswordDialogOpen, setIsPasswordDialogOpen] = useState(false);
    const [passwordData, setPasswordData] = useState<PasswordChangeData>({
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: ''
    });
    const [showPasswords, setShowPasswords] = useState({
        current: false,
        new: false,
        confirm: false
    });

    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error' | 'info' | 'warning'
    });

    // Mock user ID - in a real app, this would come from authentication context
    const currentUserId = localStorage.getItem('currentUserId') || '1';

    useEffect(() => {
        loadProfile();
    }, []);

    const convertApiUserToProfileData = (apiUser: ApiUser): ProfileData => ({
        id: apiUser.oid,
        username: apiUser.username || '',
        active: apiUser.active || false,
        created_date: apiUser.created_date ? new Date(apiUser.created_date) : null,
        last_modified_date: apiUser.last_modified_date ? new Date(apiUser.last_modified_date) : null,
        omid: apiUser.omid,
        ouid: apiUser.ouid,
        sync_status: apiUser.sync_status,
        version: apiUser.version,
        change_password_on_first_logon: apiUser.change_password_on_first_logon,
        object_type: apiUser.object_type,
        access_failed_count: apiUser.access_failed_count,
        lockout_end: apiUser.lockout_end ? new Date(apiUser.lockout_end) : null
    });

    const loadProfile = async () => {
        setLoading(true);
        try {
            const apiUser = await userApiService.getUserById(currentUserId);
            const profileData = convertApiUserToProfileData(apiUser);
            setProfile(profileData);
            setEditData({
                username: profileData.username,
                ouid: profileData.ouid || '',
                version: profileData.version || ''
            });
        } catch (error) {
            console.error('Failed to load profile:', error);
            setSnackbar({
                open: true,
                message: 'Failed to load profile: ' + (error as Error).message,
                severity: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleSaveProfile = async () => {
        if (!profile) return;

        setSaving(true);
        try {
            const updateRequest = {
                oid: profile.id,
                username: editData.username,
                ouid: editData.ouid,
                version: editData.version
            };

            await userApiService.updateUser(updateRequest);
            setProfile(prev => prev ? { ...prev, ...editData } : null);
            setIsEditing(false);
            setSnackbar({
                open: true,
                message: 'Profile updated successfully',
                severity: 'success'
            });
        } catch (error) {
            console.error('Failed to update profile:', error);
            setSnackbar({
                open: true,
                message: 'Failed to update profile: ' + (error as Error).message,
                severity: 'error'
            });
        } finally {
            setSaving(false);
        }
    };

    const handleChangePassword = async () => {
        if (!profile) return;

        // Validation
        if (passwordData.newPassword !== passwordData.confirmNewPassword) {
            setSnackbar({
                open: true,
                message: 'New passwords do not match',
                severity: 'error'
            });
            return;
        }

        if (passwordData.newPassword.length < 6) {
            setSnackbar({
                open: true,
                message: 'Password must be at least 6 characters long',
                severity: 'error'
            });
            return;
        }

        try {
            await userApiService.changePassword(
                profile.id,
                passwordData.currentPassword,
                passwordData.newPassword
            );

            setIsPasswordDialogOpen(false);
            setPasswordData({
                currentPassword: '',
                newPassword: '',
                confirmNewPassword: ''
            });
            setSnackbar({
                open: true,
                message: 'Password changed successfully',
                severity: 'success'
            });
        } catch (error) {
            console.error('Failed to change password:', error);
            setSnackbar({
                open: true,
                message: 'Failed to change password: ' + (error as Error).message,
                severity: 'error'
            });
        }
    };

    const formatDate = (date: Date | null) => {
        if (!date) return 'Not available';
        return date.toLocaleDateString() + ' at ' + date.toLocaleTimeString();
    };

    const getAccountStatusColor = (active: boolean) => {
        return active ? 'success' : 'error';
    };

    if (loading) {
        return (
            <Container maxWidth="lg">
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                    <CircularProgress />
                </Box>
            </Container>
        );
    }

    if (!profile) {
        return (
            <Container maxWidth="lg">
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                    <Alert severity="error">Failed to load user profile</Alert>
                </Box>
            </Container>
        );
    }

    return (
        <Container maxWidth="lg">
            <Box sx={{ mt: 4, mb: 4 }}>
                {/* Header */}
                <Paper sx={{ p: 3, mb: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Avatar
                                sx={{
                                    width: 80,
                                    height: 80,
                                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                                    color: theme.palette.primary.main,
                                    fontSize: '2rem'
                                }}
                            >
                                {profile.username.charAt(0).toUpperCase()}
                            </Avatar>
                            <Box>
                                <Typography variant="h4" component="h1" gutterBottom>
                                    {profile.username}
                                </Typography>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    <Chip
                                        label={profile.active ? 'Active' : 'Inactive'}
                                        color={getAccountStatusColor(profile.active)}
                                        size="small"
                                    />
                                    {profile.change_password_on_first_logon && (
                                        <Chip
                                            icon={<Warning />}
                                            label="Password Change Required"
                                            color="warning"
                                            size="small"
                                        />
                                    )}
                                    {profile.lockout_end && new Date(profile.lockout_end) > new Date() && (
                                        <Chip
                                            icon={<Lock />}
                                            label="Account Locked"
                                            color="error"
                                            size="small"
                                        />
                                    )}
                                </Stack>
                            </Box>
                        </Box>
                        <Stack direction="row" spacing={2}>
                            <Button
                                variant={isEditing ? "outlined" : "contained"}
                                startIcon={isEditing ? <Cancel /> : <Edit />}
                                onClick={() => {
                                    if (isEditing) {
                                        setIsEditing(false);
                                        setEditData({
                                            username: profile.username,
                                            ouid: profile.ouid || '',
                                            version: profile.version || ''
                                        });
                                    } else {
                                        setIsEditing(true);
                                    }
                                }}
                            >
                                {isEditing ? 'Cancel' : 'Edit Profile'}
                            </Button>
                            {isEditing && (
                                <Button
                                    variant="contained"
                                    startIcon={<Save />}
                                    onClick={handleSaveProfile}
                                    disabled={saving}
                                >
                                    {saving ? 'Saving...' : 'Save Changes'}
                                </Button>
                            )}
                        </Stack>
                    </Box>
                </Paper>

                <Grid container spacing={3}>
                    {/* Profile Information */}
                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Person />
                                    Profile Information
                                </Typography>
                                <Divider sx={{ mb: 2 }} />

                                <Stack spacing={2}>
                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Username</Typography>
                                        {isEditing ? (
                                            <TextField
                                                fullWidth
                                                size="small"
                                                value={editData.username}
                                                onChange={(e) => setEditData({ ...editData, username: e.target.value })}
                                                sx={{ mt: 0.5 }}
                                            />
                                        ) : (
                                            <Typography variant="body1">{profile.username}</Typography>
                                        )}
                                    </Box>

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">User ID</Typography>
                                        <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                                            {profile.id}
                                        </Typography>
                                    </Box>

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">OUID</Typography>
                                        {isEditing ? (
                                            <TextField
                                                fullWidth
                                                size="small"
                                                value={editData.ouid}
                                                onChange={(e) => setEditData({ ...editData, ouid: e.target.value })}
                                                sx={{ mt: 0.5 }}
                                            />
                                        ) : (
                                            <Typography variant="body1">
                                                {profile.ouid || 'Not set'}
                                            </Typography>
                                        )}
                                    </Box>

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Version</Typography>
                                        {isEditing ? (
                                            <TextField
                                                fullWidth
                                                size="small"
                                                value={editData.version}
                                                onChange={(e) => setEditData({ ...editData, version: e.target.value })}
                                                sx={{ mt: 0.5 }}
                                            />
                                        ) : (
                                            <Typography variant="body1">
                                                {profile.version || 'Not set'}
                                            </Typography>
                                        )}
                                    </Box>

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Object Type</Typography>
                                        <Typography variant="body1">
                                            {profile.object_type || 'Default'}
                                        </Typography>
                                    </Box>
                                </Stack>
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Account Security */}
                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Security />
                                    Account Security
                                </Typography>
                                <Divider sx={{ mb: 2 }} />

                                <Stack spacing={2}>
                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Account Status</Typography>
                                        <Chip
                                            label={profile.active ? 'Active' : 'Inactive'}
                                            color={getAccountStatusColor(profile.active)}
                                            size="small"
                                            sx={{ mt: 0.5 }}
                                        />
                                    </Box>

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Failed Login Attempts</Typography>
                                        <Typography variant="body1" color={profile.access_failed_count && profile.access_failed_count > 0 ? 'error.main' : 'text.primary'}>
                                            {profile.access_failed_count || 0}
                                        </Typography>
                                    </Box>

                                    {profile.lockout_end && (
                                        <Box>
                                            <Typography variant="body2" color="text.secondary">Lockout Until</Typography>
                                            <Typography variant="body1" color="error.main">
                                                {formatDate(profile.lockout_end)}
                                            </Typography>
                                        </Box>
                                    )}

                                    <Box>
                                        <Typography variant="body2" color="text.secondary">Password Change Required</Typography>
                                        <Typography variant="body1">
                                            {profile.change_password_on_first_logon ? 'Yes' : 'No'}
                                        </Typography>
                                    </Box>

                                    <Button
                                        variant="outlined"
                                        startIcon={<VpnKey />}
                                        onClick={() => setIsPasswordDialogOpen(true)}
                                        fullWidth
                                    >
                                        Change Password
                                    </Button>
                                </Stack>
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Account Activity */}
                    <Grid item xs={12}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <History />
                                    Account Activity
                                </Typography>
                                <Divider sx={{ mb: 2 }} />

                                <Grid container spacing={3}>
                                    <Grid item xs={12} sm={6}>
                                        <Box>
                                            <Typography variant="body2" color="text.secondary">Account Created</Typography>
                                            <Typography variant="body1">
                                                {formatDate(profile.created_date)}
                                            </Typography>
                                        </Box>
                                    </Grid>
                                    <Grid item xs={12} sm={6}>
                                        <Box>
                                            <Typography variant="body2" color="text.secondary">Last Modified</Typography>
                                            <Typography variant="body1">
                                                {formatDate(profile.last_modified_date)}
                                            </Typography>
                                        </Box>
                                    </Grid>
                                </Grid>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Change Password Dialog */}
                <Dialog
                    open={isPasswordDialogOpen}
                    onClose={() => setIsPasswordDialogOpen(false)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>Change Password</DialogTitle>
                    <DialogContent>
                        <Stack spacing={2} sx={{ mt: 1 }}>
                            <TextField
                                fullWidth
                                label="Current Password"
                                type={showPasswords.current ? 'text' : 'password'}
                                value={passwordData.currentPassword}
                                onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton
                                                onClick={() => setShowPasswords({ ...showPasswords, current: !showPasswords.current })}
                                                edge="end"
                                            >
                                                {showPasswords.current ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }}
                            />

                            <TextField
                                fullWidth
                                label="New Password"
                                type={showPasswords.new ? 'text' : 'password'}
                                value={passwordData.newPassword}
                                onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton
                                                onClick={() => setShowPasswords({ ...showPasswords, new: !showPasswords.new })}
                                                edge="end"
                                            >
                                                {showPasswords.new ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }}
                            />

                            <TextField
                                fullWidth
                                label="Confirm New Password"
                                type={showPasswords.confirm ? 'text' : 'password'}
                                value={passwordData.confirmNewPassword}
                                onChange={(e) => setPasswordData({ ...passwordData, confirmNewPassword: e.target.value })}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton
                                                onClick={() => setShowPasswords({ ...showPasswords, confirm: !showPasswords.confirm })}
                                                edge="end"
                                            >
                                                {showPasswords.confirm ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }}
                            />

                            <Alert severity="info">
                                Password must be at least 6 characters long.
                            </Alert>
                        </Stack>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setIsPasswordDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleChangePassword}
                            variant="contained"
                            disabled={!passwordData.currentPassword || !passwordData.newPassword || !passwordData.confirmNewPassword}
                        >
                            Change Password
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Snackbar for notifications */}
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                >
                    <Alert
                        severity={snackbar.severity}
                        onClose={() => setSnackbar({ ...snackbar, open: false })}
                    >
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>
        </Container>
    );
};

export default UserProfilePage;