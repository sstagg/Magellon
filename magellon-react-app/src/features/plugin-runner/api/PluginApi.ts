import { useQuery, useMutation, useQueryClient } from 'react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import type { Job } from '../../../app/layouts/PanelLayout/useJobStore.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

// ---------------------------------------------------------------------------
// Types — mirror backend response shapes in plugins/controller.py
// ---------------------------------------------------------------------------

export interface PluginSummary {
    plugin_id: string;
    category: string;
    name: string;
    version: string;
    /** Bumped when input/output schema changes; used to invalidate cached forms. */
    schema_version?: string;
    description: string;
    developer: string;
    /**
     * - ``in-process``: PluginBase subclass discovered on disk; reachable
     *   via POST /plugins/{plugin_id}/jobs.
     * - ``broker``: external plugin (Docker container or separate
     *   process) that announced itself on ``magellon.plugins.liveness``;
     *   dispatch flows through the bus, not through this controller.
     *
     * Optional for backwards compatibility with older backend builds —
     * default to ``in-process`` when the field is missing.
     */
    kind?: 'in-process' | 'broker';
    /**
     * Hub state (H1). ``enabled`` gates whether the dispatcher will
     * route new tasks to this plugin; flips via POST
     * /plugins/{id}/enable|disable. ``is_default_for_category`` is true
     * for the impl that wins category-scoped dispatches (when multiple
     * impls of the same category are announced). Optional for older
     * backend builds — default ``enabled=true``, no default-badge.
     */
    enabled?: boolean;
    is_default_for_category?: boolean;
    /** SDK 1.1+ plugin's announced input queue. UI-surfaced for debug. */
    task_queue?: string | null;
}

export interface PluginInfo {
    name: string;
    developer: string;
    description: string;
    version: string;
}

export type JsonSchema = Record<string, any>;

export interface JobSubmitRequest {
    input: Record<string, any>;
    name?: string;
    image_id?: string;
    user_id?: string;
    msession_id?: string;
}

export interface BatchSubmitRequest {
    inputs: Record<string, any>[];
    name?: string;
    image_ids?: string[];
    user_id?: string;
    msession_id?: string;
}

export interface BatchSubmitResponse {
    jobs: Job[];
    count: number;
}

// ---------------------------------------------------------------------------
// Raw API
// ---------------------------------------------------------------------------

export const fetchPlugins = async (): Promise<PluginSummary[]> => {
    const res = await api.get('/plugins/');
    return res.data;
};

export const fetchPluginInfo = async (pluginId: string): Promise<PluginInfo> => {
    const res = await api.get(`/plugins/${pluginId}/info`);
    return res.data;
};

export const fetchPluginInputSchema = async (pluginId: string): Promise<JsonSchema> => {
    const res = await api.get(`/plugins/${pluginId}/schema/input`);
    return res.data;
};

export const fetchPluginOutputSchema = async (pluginId: string): Promise<JsonSchema> => {
    const res = await api.get(`/plugins/${pluginId}/schema/output`);
    return res.data;
};

export const submitPluginJob = async (
    pluginId: string,
    body: JobSubmitRequest,
    sid?: string,
): Promise<Job> => {
    const res = await api.post(`/plugins/${pluginId}/jobs`, body, {
        params: sid ? { sid } : undefined,
    });
    return res.data;
};

export const submitPluginBatch = async (
    pluginId: string,
    body: BatchSubmitRequest,
    sid?: string,
): Promise<BatchSubmitResponse> => {
    const res = await api.post(`/plugins/${pluginId}/jobs/batch`, body, {
        params: sid ? { sid } : undefined,
    });
    return res.data;
};

export const fetchJob = async (jobId: string): Promise<Job> => {
    const res = await api.get(`/plugins/jobs/${jobId}`);
    return res.data;
};

export const cancelJob = async (jobId: string): Promise<Job> => {
    const res = await api.delete(`/plugins/jobs/${jobId}`);
    return res.data;
};

export const fetchJobs = async (pluginId?: string): Promise<Job[]> => {
    const res = await api.get('/plugins/jobs', {
        params: pluginId ? { plugin_id: pluginId } : undefined,
    });
    return res.data;
};

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

export const usePlugins = () =>
    useQuery(['plugins'], fetchPlugins, { staleTime: 60_000 });

// ---------------------------------------------------------------------------
// Hub operator actions (H1): enable/disable + set-default-for-category
// ---------------------------------------------------------------------------

export const enablePlugin = async (pluginId: string) => {
    const res = await api.post(`/plugins/${pluginId}/enable`);
    return res.data;
};

export const disablePlugin = async (pluginId: string) => {
    const res = await api.post(`/plugins/${pluginId}/disable`);
    return res.data;
};

export const setCategoryDefault = async (category: string, pluginId: string) => {
    const short = pluginId.includes('/') ? pluginId.split('/').slice(1).join('/') : pluginId;
    const res = await api.post(`/plugins/categories/${category}/default`, {
        plugin_id: short,
    });
    return res.data;
};

export const useTogglePlugin = () => {
    const qc = useQueryClient();
    return useMutation(
        async ({ pluginId, enabled }: { pluginId: string; enabled: boolean }) =>
            (enabled ? enablePlugin : disablePlugin)(pluginId),
        {
            onSuccess: () => qc.invalidateQueries(['plugins']),
        },
    );
};

export const useSetCategoryDefault = () => {
    const qc = useQueryClient();
    return useMutation(
        async ({ category, pluginId }: { category: string; pluginId: string }) =>
            setCategoryDefault(category, pluginId),
        {
            onSuccess: () => qc.invalidateQueries(['plugins']),
        },
    );
};

// ---------------------------------------------------------------------------
// Install flow (H2): POST /plugins/install + lifecycle on /plugins/installed
// ---------------------------------------------------------------------------

export interface InstallVolume {
    host_path: string;
    container_path: string;
    read_only?: boolean;
}

export interface InstallPluginRequest {
    image_ref: string;
    env?: Record<string, string>;
    volumes?: InstallVolume[];
    network?: string | null;
}

export interface InstalledPlugin {
    install_id: string;
    image_ref: string;
    container_id: string;
    container_name: string;
    state: string;
    env: Record<string, string>;
    volumes: InstallVolume[];
    network: string | null;
    error: string | null;
    announcing_on_bus?: boolean;
}

export const installPlugin = async (body: InstallPluginRequest): Promise<InstalledPlugin> => {
    const res = await api.post('/plugins/install', body);
    return res.data;
};

/** Install a plugin from a .magplugin archive upload (H3a). */
export const installPluginArchive = async (
    archive: File,
): Promise<InstalledPlugin & { archive?: { plugin_id: string; name: string; version: string; category: string } }> => {
    const form = new FormData();
    form.append('archive', archive);
    const res = await api.post('/plugins/install/archive', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
};

export const fetchInstalled = async (): Promise<InstalledPlugin[]> => {
    const res = await api.get('/plugins/installed');
    return res.data.installed ?? [];
};

export const stopInstalled = async (installId: string): Promise<InstalledPlugin> => {
    const res = await api.post(`/plugins/installed/${installId}/stop`);
    return res.data;
};

export const removeInstalled = async (installId: string): Promise<InstalledPlugin> => {
    const res = await api.delete(`/plugins/installed/${installId}`);
    return res.data;
};

export const useInstalledPlugins = () =>
    useQuery(['plugins-installed'], fetchInstalled, {
        // Installed-plugin state moves slowly; cheap polling lets the
        // user see container-state changes (running → exited, etc.)
        // without refreshing the page manually.
        refetchInterval: 5000,
    });

export const useInstallPlugin = () => {
    const qc = useQueryClient();
    return useMutation(installPlugin, {
        onSuccess: () => {
            qc.invalidateQueries(['plugins-installed']);
            qc.invalidateQueries(['plugins']);
        },
    });
};

export const useInstallPluginArchive = () => {
    const qc = useQueryClient();
    return useMutation(installPluginArchive, {
        onSuccess: () => {
            qc.invalidateQueries(['plugins-installed']);
            qc.invalidateQueries(['plugins']);
        },
    });
};

export const useStopInstalled = () => {
    const qc = useQueryClient();
    return useMutation(stopInstalled, {
        onSuccess: () => qc.invalidateQueries(['plugins-installed']),
    });
};

export const useRemoveInstalled = () => {
    const qc = useQueryClient();
    return useMutation(removeInstalled, {
        onSuccess: () => {
            qc.invalidateQueries(['plugins-installed']);
            qc.invalidateQueries(['plugins']);
        },
    });
};

export const usePluginInputSchema = (pluginId: string | null) =>
    useQuery(
        ['plugin-schema-input', pluginId],
        () => fetchPluginInputSchema(pluginId!),
        { enabled: !!pluginId, staleTime: 60_000 },
    );

export const useSubmitPluginJob = (pluginId: string) =>
    useMutation((body: JobSubmitRequest & { sid?: string }) => {
        const { sid, ...payload } = body;
        return submitPluginJob(pluginId, payload, sid);
    });

export const useSubmitPluginBatch = (pluginId: string) =>
    useMutation((body: BatchSubmitRequest & { sid?: string }) => {
        const { sid, ...payload } = body;
        return submitPluginBatch(pluginId, payload, sid);
    });

export const useCancelJob = () =>
    useMutation((jobId: string) => cancelJob(jobId));

export const usePluginJobs = (pluginId?: string) =>
    useQuery(['plugin-jobs', pluginId ?? 'all'], () => fetchJobs(pluginId), {
        refetchInterval: 5000,
    });
