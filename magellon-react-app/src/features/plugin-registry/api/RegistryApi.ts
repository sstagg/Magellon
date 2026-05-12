/**
 * Hooks for the PE4 plugin registry merge endpoint
 * (``GET /plugins/registry/index``).
 *
 * One call returns hub catalog + local install state merged. The
 * page rendered on top reads this single response and slices it into
 * Browse / Update inbox / Local-only panes.
 */
import { useQuery } from 'react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);


export interface RegistryHubVersion {
    version: string;
    sdk_compat?: string | null;
    sha256?: string | null;
    size_bytes?: number | null;
    published_at?: string | null;
    archive_url?: string | null;
}


export interface RegistryPlugin {
    plugin_id: string;
    display_name: string;
    category?: string | null;
    is_verified: boolean;
    hub_versions: RegistryHubVersion[];
    latest_hub_version?: string | null;
    installed_version?: string | null;
    install_method?: string | null;
    update_available: boolean;
    /** ``"hub"`` when the plugin is in the hub catalog; ``"local-only"``
     *  when installed but absent from the hub (air-gapped/custom). */
    source: 'hub' | 'local-only';
}


export interface RegistryIndexResponse {
    hub_url: string;
    /** ``"ok"`` on success; ``"unreachable"`` / ``"http_<code>"`` otherwise. */
    hub_status: string;
    hub_error?: string | null;
    plugins: RegistryPlugin[];
}


export const useRegistryIndex = (hubUrlOverride?: string) =>
    useQuery(
        ['plugin-registry-index', hubUrlOverride ?? ''],
        async (): Promise<RegistryIndexResponse> => {
            const res = await api.get<RegistryIndexResponse>(
                '/plugins/registry/index',
                {
                    params: hubUrlOverride ? { hub_url: hubUrlOverride } : undefined,
                },
            );
            return res.data;
        },
        {
            // Hub catalog refreshes are infrequent; React-side staleness
            // should be measured in minutes, not seconds.
            staleTime: 5 * 60 * 1000,
            refetchOnWindowFocus: false,
        },
    );
