import { useEffect, useState } from 'react';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

/**
 * One session name, one import: asks the server (debounced) whether a new
 * import may use `name`. `problem` is the reason it can't ("Session 'x'
 * already exists (owner y)…"), or null when it's free or not checked yet.
 * The server checks again on submit, so this is only early feedback.
 */
export function useSessionNameCheck(name: string) {
    const [problem, setProblem] = useState<string | null>(null);
    const [checking, setChecking] = useState(false);

    useEffect(() => {
        const trimmed = name.trim();
        setProblem(null);
        if (!trimmed || /[\\/\s]/.test(trimmed)) return;
        let cancelled = false;
        setChecking(true);
        const timer = window.setTimeout(() => {
            apiClient.get<{ available: boolean; reason: string | null }>('/export/session-name/check', { params: { name: trimmed } })
                .then(({ data }) => { if (!cancelled) setProblem(data.available ? null : data.reason); })
                .catch(() => { /* the submit-time check still applies */ })
                .finally(() => { if (!cancelled) setChecking(false); });
        }, 400);
        return () => { cancelled = true; window.clearTimeout(timer); setChecking(false); };
    }, [name]);

    return { problem, checking };
}
