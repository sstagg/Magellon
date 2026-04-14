import { useQuery, useMutation } from 'react-query';
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
    description: string;
    developer: string;
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

export const usePluginJobs = (pluginId?: string) =>
    useQuery(['plugin-jobs', pluginId ?? 'all'], () => fetchJobs(pluginId), {
        refetchInterval: 5000,
    });
