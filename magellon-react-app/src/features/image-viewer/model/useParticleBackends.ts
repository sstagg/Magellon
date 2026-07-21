import { useEffect, useState } from 'react';
import { TEMPLATE_PICKER_PATH } from '../lib/useParticleOperations.ts';
import { API_URL } from './particleSettingsCore.ts';
import type { BackendInfo } from './particleSettingsTypes.ts';

/** Backend list fetch + selection for the particle-settings panel. */
export function useParticleBackends(open: boolean) {
    const [backends, setBackends] = useState<BackendInfo[]>([]);
    const [selectedBackend, setSelectedBackend] = useState<string>('topaz-particle-picking');
    const [backendsLoading, setBackendsLoading] = useState(false);

    // Load live backends. ``cache: 'no-store'`` because the answer
    // changes whenever a plugin process restarts (capabilities,
    // http_endpoint, etc.); a browser-level GET cache would freeze
    // ``canPreview`` to whatever the panel saw on first open and the
    // side panel would keep showing the "no-save preview" alert long
    // after the backend recovered.
    useEffect(() => {
        if (!open) return;
        setBackendsLoading(true);
        const token = localStorage.getItem('access_token');
        const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/backends`, { cache: 'no-store', headers: authHeaders })
            .then((res) => res.ok ? res.json() : Promise.resolve([]))
            .then((data: BackendInfo[]) => {
                // Topaz always sorts to the top; otherwise preserve server order.
                const isTopaz = (id: string) => id === 'topaz-particle-picking' || id === 'topaz';
                const sorted = [...data].sort((a, b) => {
                    if (isTopaz(a.backend_id)) return -1;
                    if (isTopaz(b.backend_id)) return 1;
                    return 0;
                });
                setBackends(sorted);
                // Auto-select topaz if live; else first available; else keep current.
                const topazLive = sorted.find(b => isTopaz(b.backend_id));
                if (topazLive) {
                    setSelectedBackend(topazLive.backend_id);
                } else if (sorted.length > 0 && !sorted.some(b => b.backend_id === selectedBackend)) {
                    setSelectedBackend(sorted[0].backend_id);
                }
            })
            .catch(() => { /* backends endpoint optional — fall back to template-picker */ })
            .finally(() => setBackendsLoading(false));
    }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

    const activeBackend = backends.find(b => b.backend_id === selectedBackend);
    const backendEnabled = activeBackend?.enabled !== false;
    const canPreview = (activeBackend?.has_preview ?? (selectedBackend === 'template-picker')) && backendEnabled;
    const isTopazBackend = selectedBackend.replace('_', '-').toLowerCase().includes('topaz');

    return {
        backends,
        backendsLoading,
        selectedBackend,
        setSelectedBackend,
        backendEnabled,
        canPreview,
        isTopazBackend,
    };
}
