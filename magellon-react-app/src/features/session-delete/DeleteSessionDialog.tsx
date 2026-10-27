import { useState } from 'react';
import { create } from 'zustand';
import {
    Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography,
} from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import getAxiosClient from '../../shared/api/AxiosClient.ts';
import { settings } from '../../shared/config/settings.ts';
import { apiErrorMessage } from '../../shared/api/apiError.ts';
import { notify, updateNotice } from '../../shared/ui/Notifications.tsx';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

/** Fired on window when a session was deleted (detail: its name). */
export const SESSION_DELETED_EVENT = 'magellon:session-deleted';

/** Tell the open pages a session is gone (deleted here, or by stopping its
 * import): session lists reload and a page showing it lets it go. */
export const announceSessionDeleted = (name: string) =>
    window.dispatchEvent(new CustomEvent(SESSION_DELETED_EVENT, { detail: name }));

const useDeleteSessionStore = create<{ name: string | null; ask: (name: string) => void; close: () => void }>((set) => ({
    name: null,
    ask: (name) => set({ name }),
    close: () => set({ name: null }),
}));

/** Open the delete-session confirmation (from the Images page or Jobs tab). */
export const askDeleteSession = (name: string) => useDeleteSessionStore.getState().ask(name);

/**
 * The one delete-session confirmation: the user types the name, the delete
 * then runs in the background with a notification ("Deleting x…" → "Deleted
 * x"). The server decides who may delete (owner or admin). Mount once.
 */
export const DeleteSessionDialog = () => {
    const { name, close } = useDeleteSessionStore();
    const queryClient = useQueryClient();
    const [typed, setTyped] = useState('');

    const handleClose = () => { setTyped(''); close(); };

    const remove = async () => {
        if (!name) return;
        const session = name;
        handleClose();
        const notice = notify(`Deleting session ${session}…`, 'info', true);
        try {
            await apiClient.delete(`/export/session/${encodeURIComponent(session)}`);
            updateNotice(notice, `Session ${session} deleted`, 'success');
            await queryClient.invalidateQueries({ queryKey: ['sessionNames'] });
            announceSessionDeleted(session);
        } catch (err) {
            updateNotice(notice, `Could not delete ${session}: ${apiErrorMessage(err, 'unknown error')}`, 'error');
        }
    };

    return (
        <Dialog open={!!name} onClose={handleClose} maxWidth="xs" fullWidth>
            <DialogTitle>Delete session "{name}"?</DialogTitle>
            <DialogContent>
                <Typography variant="body2" sx={{ mb: 2 }}>
                    This permanently removes the session's images, CTF and MotionCor results, particle
                    picks and its files in Magellon's storage. The original data in research storage is
                    not touched.
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                    To confirm, type <strong>"{name}"</strong> exactly as shown (without the quotes):
                </Typography>
                <TextField
                    fullWidth
                    size="small"
                    autoFocus
                    placeholder={name ?? ''}
                    value={typed}
                    onChange={(e) => setTyped(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && typed.trim() === name) remove(); }}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Cancel</Button>
                <Button color="error" variant="contained" onClick={remove} disabled={typed.trim() !== name}>
                    Delete
                </Button>
            </DialogActions>
        </Dialog>
    );
};
