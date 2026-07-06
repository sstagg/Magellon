import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    Grid,
    IconButton,
    InputAdornment,
    Switch,
    TextField
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import type { UserFormState } from '../model/useUserForm.ts';

interface UserFormDialogProps {
    mode: 'create' | 'edit';
    open: boolean;
    form: UserFormState;
    onClose: () => void;
    onSubmit: () => void;
}

export default function UserFormDialog({
    mode,
    open,
    form,
    onClose,
    onSubmit
}: UserFormDialogProps) {
    const {
        formData,
        setFormData,
        showPassword,
        setShowPassword,
        showConfirmPassword,
        setShowConfirmPassword
    } = form;
    const isCreate = mode === 'create';

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>{isCreate ? 'Create New User' : 'Edit User'}</DialogTitle>
            <DialogContent>
                <Grid container spacing={2} sx={{ mt: 1 }}>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label="Username"
                            value={formData.username}
                            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                            required
                        />
                    </Grid>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label="User ID (OUID)"
                            value={formData.ouid}
                            onChange={(e) => setFormData({ ...formData, ouid: e.target.value })}
                        />
                    </Grid>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label={isCreate ? 'Password' : 'New Password (leave empty to keep current)'}
                            type={showPassword ? 'text' : 'password'}
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            required={isCreate}
                            slotProps={{
                                input: {
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                                                {showPassword ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }
                            }}
                        />
                    </Grid>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label={isCreate ? 'Confirm Password' : 'Confirm New Password'}
                            type={showConfirmPassword ? 'text' : 'password'}
                            value={formData.confirmPassword}
                            onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                            required={isCreate}
                            slotProps={{
                                input: {
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end">
                                                {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }
                            }}
                        />
                    </Grid>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label="Version"
                            value={formData.version}
                            onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                        />
                    </Grid>
                    <Grid
                        size={{
                            xs: 12,
                            sm: 6
                        }}>
                        <TextField
                            fullWidth
                            label="Object Type"
                            type="number"
                            value={formData.object_type || ''}
                            onChange={(e) => setFormData({ ...formData, object_type: e.target.value ? parseInt(e.target.value) : undefined })}
                        />
                    </Grid>
                    <Grid size={12}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={formData.active}
                                    onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                                />
                            }
                            label="Active User"
                        />
                    </Grid>
                    <Grid size={12}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={formData.change_password_on_first_logon}
                                    onChange={(e) => setFormData({ ...formData, change_password_on_first_logon: e.target.checked })}
                                />
                            }
                            label="Change Password on First Login"
                        />
                    </Grid>
                </Grid>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={onSubmit} variant="contained">
                    {isCreate ? 'Create User' : 'Update User'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
