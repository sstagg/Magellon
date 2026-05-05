/**
 * GET /system/stats — live host metrics for the plugins dashboard.
 *
 * Polled at 2s; the endpoint is cheap (one psutil walk + optional
 * NVML query) so this doesn't strain CoreService. When the user
 * navigates away from the page, react-query stops the polling
 * automatically.
 */
import { useQuery } from 'react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export interface CpuStats {
    percent: number;
    cores: number;
    /** Unix load average 1/5/15 min. null on Windows. */
    load_avg: number[] | null;
}

export interface RamStats {
    total_bytes: number;
    used_bytes: number;
    available_bytes: number;
    percent: number;
}

export interface NetworkStats {
    rx_bytes_per_sec: number;
    tx_bytes_per_sec: number;
    rx_total_bytes: number;
    tx_total_bytes: number;
}

export interface GpuDeviceStats {
    index: number;
    name: string;
    util_percent: number | null;
    memory_used_bytes: number | null;
    memory_total_bytes: number | null;
    temperature_c: number | null;
}

export interface GpuStats {
    available: boolean;
    devices: GpuDeviceStats[];
    error: string | null;
}

export interface SystemStatsResponse {
    cpu: CpuStats;
    ram: RamStats;
    network: NetworkStats;
    gpu: GpuStats;
    sampled_at: number;
}

export const fetchSystemStats = async (): Promise<SystemStatsResponse> => {
    const res = await api.get<SystemStatsResponse>('/system/stats');
    return res.data;
};

export const useSystemStats = (intervalMs: number = 2000) =>
    useQuery(['system-stats'], fetchSystemStats, {
        refetchInterval: intervalMs,
        // Smooth animation: keep prior values around while next sample
        // is in flight so the cards don't blink on every refetch.
        keepPreviousData: true,
        // 6h. We always refetch on interval anyway; the cache time keeps
        // the prior sample around across remounts of the page.
        staleTime: intervalMs * 2,
    });
