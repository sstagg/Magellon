import {
    Alert,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Typography
} from '@mui/material';
import type { UserData } from '../model/types.ts';

interface DeleteUserDialogProps {
    open: boolean;
    user: UserData | null;
    onClose: () => void;
    onConfirm: () => void;
}

export default function DeleteUserDialog({
    open,
    user,
    onClose,
    onConfirm
}: DeleteUserDialogProps) {
    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>Delete User</DialogTitle>
            <DialogContent>
                <Alert severity="warning" sx={{ mb: 2 }}>
                    This action cannot be undone. The user will be permanently deleted.
                </Alert>
                <Typography>
                    Are you sure you want to delete user <strong>{user?.username}</strong>?
                </Typography>
                <Typography
                    variant="body2"
                    sx={{
                        color: "text.secondary",
                        mt: 1
                    }}>
                    User ID: {user?.id}
                </Typography>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={onConfirm} variant="contained" color="error">
                    Delete User
                </Button>
            </DialogActions>
        </Dialog>
    );
}
