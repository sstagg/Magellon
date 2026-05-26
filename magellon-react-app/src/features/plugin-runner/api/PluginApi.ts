import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import type { Job } from '../../../shared/lib/stores/useJobStore.ts';

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
    /** PI-6+: all runtime plugins are broker-announced external plugins. */
    kind: 'broker';
    supported_transports?: string[];
    default_transport?: string;
    isolation?: string;
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
    /** Capability flags announced by the plugin (e.g. 'preview', 'sync'). */
    capabilities?: string[];
}

export interface PluginInfo {
    name: string;
    developer: string;
    description: string;
    version: string;
}

export type JsonSchema = Record<string, unknown>;

export interface JobSubmitRequest {
    input: Record<string, unknown>;
    name?: string;
    image_id?: string;
    user_id?: string;
    msession_id?: string;
    /**
     * Pin dispatch to a specific backend within the plugin's category.
     * ``null`` / ``undefined`` keeps the category-default behaviour.
     */
    target_backend?: string | null;
}

export interface BatchSubmitRequest {
    inputs: Record<string, unknown>[];
    name?: string;
    image_ids?: string[];
    user_id?: string;
    msession_id?: string;
    target_backend?: string | null;
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
    useQuery({ queryKey: ['plugins'], queryFn: fetchPlugins, staleTime: 60_000 });

// ---------------------------------------------------------------------------
// PM2 — Conditions[] (Kubernetes-style multi-axis status per plugin)
// ---------------------------------------------------------------------------

export type ConditionType =
    | 'Installed'
    | 'Enabled'
    | 'Live'
    | 'Healthy'
    | 'Default'
    | 'Paused';

export type ConditionStatus = 'True' | 'False' | 'Unknown';

export interface Condition {
    type: ConditionType;
    status: ConditionStatus;
    reason?: string | null;
    message?: string | null;
    last_transition_time?: string | null;
}

export const fetchPluginStatus = async (pluginId: string): Promise<Condition[]> => {
    const res = await api.get(`/plugins/${pluginId}/status`);
    return res.data;
};

export const usePluginStatus = (pluginId: string | null) =>
    useQuery({
        queryKey: ['plugin-status', pluginId],
        queryFn: () => fetchPluginStatus(pluginId!),
        enabled: !!pluginId,
        // Status moves on heartbeat (~15s); refresh every 10s to
        // keep chips lively without hammering the backend.
        refetchInterval: 10_000,
        staleTime: 5_000,
    });

// ---------------------------------------------------------------------------
// PM5 — Per-replica health for one plugin
// ---------------------------------------------------------------------------

export type ReplicaStatus = 'Healthy' | 'Stale' | 'Lost';

export interface ReplicaInfo {
    instance_id: string;
    host?: string | null;
    container_id?: string | null;
    last_heartbeat_at?: string | null;
    last_task_completed_at?: string | null;
    in_flight_task_count: number;
    status: ReplicaStatus;
}

export const fetchPluginReplicas = async (pluginId: string): Promise<ReplicaInfo[]> => {
    const res = await api.get(`/plugins/${pluginId}/replicas`);
    return res.data;
};

export const usePluginReplicas = (pluginId: string | null) =>
    useQuery({
        queryKey: ['plugin-replicas', pluginId],
        queryFn: () => fetchPluginReplicas(pluginId!),
        enabled: !!pluginId,
        refetchInterval: 10_000,
        staleTime: 5_000,
    });

// ---------------------------------------------------------------------------
// Installed catalog (DB-backed) — what's installed on this server, where it
// lives physically. Distinct from the live /plugins/ list which only sees
// currently-announcing plugins.
// ---------------------------------------------------------------------------

export type InstallMethod = 'docker' | 'uv' | 'archive' | 'discovered';

export interface InstalledPluginRow {
    plugin_id: string;
    manifest_plugin_id?: string | null;
    name: string;
    version?: string | null;
    category?: string | null;
    description: string;
    developer?: string | null;
    install_method?: InstallMethod | null;
    install_dir?: string | null;
    image_ref?: string | null;
    container_ref?: string | null;
    archive_id?: string | null;
    installed_date?: string | null;
    /** Supervisor-allocated FastAPI URL (e.g. ``http://127.0.0.1:18000``). */
    http_endpoint?: string | null;
    /** Numeric port portion of ``http_endpoint``. */
    port?: number | null;
    enabled: boolean;
    is_default_for_category: boolean;
}

export const fetchInstalledFromDb = async (): Promise<InstalledPluginRow[]> => {
    const res = await api.get('/plugins/db');
    return res.data;
};

export const useInstalledFromDb = () =>
    useQuery({
        queryKey: ['plugins-db'],
        queryFn: fetchInstalledFromDb,
        staleTime: 30_000,
    });

// ---------------------------------------------------------------------------
// PM6 — Available updates for installed plugins
// ---------------------------------------------------------------------------

export type UpdateSeverity = 'patch' | 'minor' | 'major';

export interface UpdateInfo {
    plugin_id: string;
    current_version: string;
    latest_version: string;
    channel: string;
    severity: UpdateSeverity;
    release_notes_url?: string | null;
    archive_url?: string | null;
}

export const fetchPluginUpdates = async (): Promise<UpdateInfo[]> => {
    const res = await api.get('/plugins/updates');
    return res.data;
};

export const usePluginUpdates = () =>
    useQuery({
        queryKey: ['plugin-updates'],
        queryFn: fetchPluginUpdates,
        // Updates change at the cadence of catalog uploads / hub
        // refreshes — minute-scale is fine.
        staleTime: 60_000,
    });

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
    return useMutation({
        mutationFn: async ({ pluginId, enabled }: { pluginId: string; enabled: boolean }) =>
            (enabled ? enablePlugin : disablePlugin)(pluginId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
    });
};

export const useSetCategoryDefault = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ category, pluginId }: { category: string; pluginId: string }) =>
            setCategoryDefault(category, pluginId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
    });
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

/** Install a plugin from a .mpn archive upload (H3a). */
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
    useQuery({
        queryKey: ['plugins-installed'],
        queryFn: fetchInstalled,
        // Installed-plugin state moves slowly; cheap polling lets the
        // user see container-state changes (running → exited, etc.)
        // without refreshing the page manually.
        refetchInterval: 5000,
    });

export const useInstallPlugin = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: installPlugin,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plugins-installed'] });
            qc.invalidateQueries({ queryKey: ['plugins'] });
        },
    });
};

export const useInstallPluginArchive = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: installPluginArchive,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plugins-installed'] });
            qc.invalidateQueries({ queryKey: ['plugins'] });
        },
    });
};

// ---------------------------------------------------------------------------
// Plugin catalog (H3b): shared library of archives published by authors
// ---------------------------------------------------------------------------

export interface CatalogEntry {
    catalog_id: string;
    plugin_id: string;
    name: string;
    version: string;
    category: string;
    sdk_compat: string;
    image_ref: string;
    description: string;
    developer: string;
    license: string;
    uploaded_at: string;
    uploaded_by: string | null;
}

export interface CatalogBrowseResponse {
    entries: CatalogEntry[];
    categories: Record<string, number>;
}

export const browseCatalog = async (
    params: { search?: string; category?: string } = {},
): Promise<CatalogBrowseResponse> => {
    const res = await api.get('/plugins/catalog', { params });
    return res.data;
};

export const uploadCatalogArchive = async (file: File): Promise<CatalogEntry> => {
    const form = new FormData();
    form.append('archive', file);
    const res = await api.post('/plugins/catalog', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
};

export const deleteCatalogEntry = async (catalogId: string) => {
    const res = await api.delete(`/plugins/catalog/${catalogId}`);
    return res.data;
};

export const installCatalogEntry = async (catalogId: string) => {
    const res = await api.post(`/plugins/catalog/${catalogId}/install`);
    return res.data;
};

export const useCatalog = (params: { search?: string; category?: string } = {}) => {
    const search = params.search ?? '';
    const category = params.category ?? '';
    return useQuery({
        queryKey: ['plugin-catalog', search, category],
        queryFn: () => browseCatalog({ search, category }),
        placeholderData: keepPreviousData,
        staleTime: 10_000,
    });
};

export const useUploadCatalog = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: uploadCatalogArchive,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['plugin-catalog'] }),
    });
};

export const useDeleteCatalog = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: deleteCatalogEntry,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['plugin-catalog'] }),
    });
};

export const useInstallCatalog = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: installCatalogEntry,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plugins-installed'] });
            qc.invalidateQueries({ queryKey: ['plugins'] });
        },
    });
};

export const useStopInstalled = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: stopInstalled,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins-installed'] }),
    });
};

export const useRemoveInstalled = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: removeInstalled,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plugins-installed'] });
            qc.invalidateQueries({ queryKey: ['plugins'] });
        },
    });
};

// ---------------------------------------------------------------------------
// Capabilities (X.1) — consolidated catalog of categories × backends.
// One snapshot the dispatcher AND this UI both read.
// ---------------------------------------------------------------------------

export interface CapabilitiesBackend {
    backend_id: string;
    plugin_id: string;
    name: string;
    version: string;
    schema_version: string;
    description?: string;
    developer?: string;
    capabilities: string[];
    isolation: string;
    default_transport: string;
    live_replicas: number;
    enabled: boolean;
    is_default_for_category: boolean;
    task_queue?: string | null;
}

export interface CategoryExample {
    /** Short label shown on the chip ("Default 300 kV"). */
    name: string;
    /** One-line context surfaced as tooltip ("Standard cryo conditions, K3 detector"). */
    description: string;
    /** Pre-fill values keyed by input-schema field name. */
    values: Record<string, unknown>;
}

export interface CapabilitiesCategory {
    code: number;
    name: string;
    description: string;
    /** Plugin_id of the operator-pinned default; null when none is pinned. */
    default_backend?: string | null;
    /** Sorted: default-flagged backend first, then alphabetical by backend_id. */
    backends: CapabilitiesBackend[];
    input_schema?: Record<string, unknown> | null;
    output_schema?: Record<string, unknown> | null;
    /** PE1-A: the subject kind tasks of this category consume. */
    subject_kind?: string;
    /** PE1-A: the subject kind the category emits when transforming. */
    produces_subject_kind?: string | null;
    /** PE1-B: per-input-field subject tags. */
    input_subjects?: Record<string, string>;
    /** PE1-B: per-output-field subject tags. */
    output_subjects?: Record<string, string>;
    /** PE5: Gradio-style examples for the test panel's pre-fill chips. */
    examples?: CategoryExample[];
}

export interface CapabilitiesResponse {
    sdk_version: string;
    categories: CapabilitiesCategory[];
}

export const fetchCapabilities = async (): Promise<CapabilitiesResponse> => {
    const res = await api.get('/plugins/capabilities');
    return res.data;
};

export const useCapabilities = () =>
    useQuery({
        queryKey: ['plugin-capabilities'],
        queryFn: fetchCapabilities,
        staleTime: 30_000,
    });


// ---------------------------------------------------------------------------
// Per-category backends (Wave 5) — reads GET /dispatch/{category}/backends
// for the drilldown page. Distinct from /plugins/capabilities which serves
// the whole catalog; the backends endpoint focuses on one category and
// adds install_method (live + DB cross-reference).
// ---------------------------------------------------------------------------

export interface CategoryBackendEntry {
    backend_id: string | null;
    plugin_id: string;
    version: string;
    capabilities: string[];
    http_endpoint: string | null;
    live_replicas: number;
    is_live: boolean;
    healthy: boolean;
    is_default: boolean;
    enabled: boolean;
    install_method: string | null;
    supports_sync: boolean;
    supports_preview: boolean;
}

export interface CategoryBackendsResponse {
    category: string;
    category_display_name: string;
    default_plugin_id: string | null;
    backends: CategoryBackendEntry[];
}

export const useCategoryBackends = (categorySlug: string | undefined) =>
    useQuery({
        queryKey: ['category-backends', categorySlug],
        queryFn: async () => {
            const res = await api.get<CategoryBackendsResponse>(
                `/dispatch/${encodeURIComponent(categorySlug!)}/backends`,
            );
            return res.data;
        },
        enabled: !!categorySlug,
        // Operators on the drilldown page want fresh data; default
        // bus + state changes propagate within seconds.
        staleTime: 5_000,
        refetchInterval: 10_000,
    });

/** Find the capabilities row for a plugin, by case-insensitive category name match.
 *  Returns ``null`` when no live broker backends exist for the category.
 */
export const useCategoryCapabilities = (categoryName: string | undefined) => {
    const q = useCapabilities();
    const cat = q.data?.categories.find(
        (c) => c.name.toLowerCase() === (categoryName ?? '').toLowerCase(),
    );
    return { ...q, data: cat ?? null };
};

export const usePluginInputSchema = (pluginId: string | null) =>
    useQuery({
        queryKey: ['plugin-schema-input', pluginId],
        queryFn: () => fetchPluginInputSchema(pluginId!),
        enabled: !!pluginId,
        staleTime: 60_000,
    });

export const usePluginOutputSchema = (pluginId: string | null) =>
    useQuery({
        queryKey: ['plugin-schema-output', pluginId],
        queryFn: () => fetchPluginOutputSchema(pluginId!),
        enabled: !!pluginId,
        staleTime: 60_000,
    });

// ---------------------------------------------------------------------------
// Sync dispatch — POST /dispatch/{category}/run for plugins advertising
// Capability.SYNC. The resolver picks a live backend matching the
// caller-supplied target_backend (if any), the operator-pinned default,
// or the first live + enabled backend in that category.
// ---------------------------------------------------------------------------

export interface SyncDispatchRequest {
    input: Record<string, unknown>;
    target_backend?: string | null;
    instance_id?: string | null;
}

export const dispatchSync = async (
    category: string,
    body: SyncDispatchRequest,
): Promise<unknown> => {
    const res = await api.post(`/dispatch/${encodeURIComponent(category)}/run`, body);
    return res.data;
};

export const useDispatchSync = (category: string) =>
    useMutation({
        mutationFn: (body: SyncDispatchRequest) => dispatchSync(category, body),
    });

export const useSubmitPluginJob = (pluginId: string) =>
    useMutation({
        mutationFn: (body: JobSubmitRequest & { sid?: string }) => {
            const { sid, ...payload } = body;
            return submitPluginJob(pluginId, payload, sid);
        },
    });

export const useSubmitPluginBatch = (pluginId: string) =>
    useMutation({
        mutationFn: (body: BatchSubmitRequest & { sid?: string }) => {
            const { sid, ...payload } = body;
            return submitPluginBatch(pluginId, payload, sid);
        },
    });

export const useCancelJob = () =>
    useMutation({ mutationFn: (jobId: string) => cancelJob(jobId) });

export const usePluginJobs = (pluginId?: string) =>
    useQuery({
        queryKey: ['plugin-jobs', pluginId ?? 'all'],
        queryFn: () => fetchJobs(pluginId),
        refetchInterval: 5000,
    });
