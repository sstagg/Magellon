import { useEffect } from 'react';
import { IconButton, Tooltip } from '@mui/material';
import { Delete } from '@mui/icons-material';
import { useSessionAccess } from '../api/useSessionAccess.ts';
import { askDeleteSession, SESSION_DELETED_EVENT } from '../../session-delete/DeleteSessionDialog.tsx';

/**
 * Delete the selected session (its owner or an admin): opens the shared
 * confirmation; the delete runs in the background with a notification.
 */
export const DeleteSessionButton = ({ sessionName, onDeleted }: { sessionName: string; onDeleted: () => void }) => {
    const { canDelete } = useSessionAccess(sessionName);

    // Clear the selection once this session is gone (deleted here or in the Jobs tab).
    useEffect(() => {
        const handler = (e: Event) => { if ((e as CustomEvent<string>).detail === sessionName) onDeleted(); };
        window.addEventListener(SESSION_DELETED_EVENT, handler);
        return () => window.removeEventListener(SESSION_DELETED_EVENT, handler);
    }, [sessionName, onDeleted]);

    if (!sessionName || !canDelete) return null;

    return (
        <Tooltip title="Delete this session">
            <IconButton size="small" onClick={() => askDeleteSession(sessionName)} sx={{ p: 0.5 }}>
                <Delete fontSize="small" />
            </IconButton>
        </Tooltip>
    );
};
