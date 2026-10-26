import { useEffect, useState } from 'react';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useAuth } from '../../auth/model/AuthContext.tsx';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_WEB_API_URL);

export interface SessionAccess {
    canWrite: boolean;
    canDelete: boolean;
    /** False until the server answered; treat the session as read-only meanwhile. */
    loaded: boolean;
}

const READ_ONLY: SessionAccess = { canWrite: false, canDelete: false, loaded: false };

/**
 * What the current user may do in a session, from the same check the
 * picking/edit/delete endpoints enforce (role + ownership). Lets the UI hide
 * actions the backend would refuse. Defaults to read-only until known, so
 * editing controls never flash on for someone who can't use them. Re-asked
 * when the user's capabilities change (live role updates).
 */
export function useSessionAccess(sessionName: string | null | undefined): SessionAccess {
    const [access, setAccess] = useState<SessionAccess>(READ_ONLY);
    const { capabilities } = useAuth();
    const capabilityKey = `${capabilities.admin}|${capabilities.import_sessions}|${capabilities.view_all_sessions}`;

    useEffect(() => {
        setAccess(READ_ONLY);
        if (!sessionName) return;
        let cancelled = false;
        apiClient
            .get<{ can_write: boolean; can_delete: boolean }>(
                `/sessions/${encodeURIComponent(sessionName)}/access`,
            )
            .then(({ data }) => {
                if (!cancelled) setAccess({ canWrite: data.can_write, canDelete: data.can_delete, loaded: true });
            })
            .catch(() => {
                if (!cancelled) setAccess({ ...READ_ONLY, loaded: true });
            });
        return () => { cancelled = true; };
    }, [sessionName, capabilityKey]);

    return access;
}
