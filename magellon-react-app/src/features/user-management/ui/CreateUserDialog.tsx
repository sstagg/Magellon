import React, { useState } from 'react';
import {
    Box,
    TextField,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from '@mui/material';

interface CreateUserDialogProps {
    open: boolean;
    loading: boolean;
    onClose: () => void;
    onCreateUser: (userData: { username: string; password: string; email: string; active: boolean }) => void;
}

export default function CreateUserDialog({ open, loading, onClose, onCreateUser }: CreateUserDialogProps) {
    const [newUserData, setNewUserData] = useState({
        username: '',
        password: '',
        email: '',
        active: true,
    });

    const handleCreate = () => {
        onCreateUser(newUserData);
        setNewUserData({ username: '', password: '', email: '', active: true });
    };

    const handleClose = () => {
        onClose();
        setNewUserData({ username: '', password: '', email: '', active: true });
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>Create New User</DialogTitle>
            <DialogContent>
                <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                        fullWidth
                        label="Username"
                        value={newUserData.username}
                        onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                    />
                    <TextField
                        fullWidth
                        label="Password"
                        type="password"
                        value={newUserData.password}
                        onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                    />
                    <TextField
                        fullWidth
                        label="Email"
                        type="email"
                        value={newUserData.email}
                        onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                    />
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Cancel</Button>
                <Button onClick={handleCreate} variant="contained" disabled={loading}>
                    Create
                </Button>
            </DialogActions>
        </Dialog>
    );
}
