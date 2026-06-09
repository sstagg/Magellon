import type { AxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useSocket } from "../../../shared/lib/useSocket.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export type ParticleExportStatus = "idle" | "scheduling" | "running" | "success" | "error";

export type ParticlePipelineStage = {
    key: string;
    label: string;
    status: string;
    progress: number;
    detail?: string | null;
};

export type ParticlePipelineChildJob = {
    key: string;
    label?: string;
    plugin_id?: string;
    job_id?: string;
    status?: string;
    artifact_id?: string;
};

export type ParticlePipelineSummary = {
    job_id: string;
    name: string;
    status: string;
    derived_status: string;
    progress: number;
    stage_key?: string | null;
    stages: ParticlePipelineStage[];
    child_jobs: ParticlePipelineChildJob[];
    settings: { session_name?: string | null; [key: string]: unknown };
    result?: {
        particle_stack_artifact_id?: string;
        class_averages_artifact_id?: string;
        output_root?: string;
        [key: string]: unknown;
    } | null;
    error?: string | null;
    created_at?: string | null;
    started_at?: string | null;
    ended_at?: string | null;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

const errorMessage = (err: unknown, fallback: string) => {
    const axiosError = err as AxiosError<{ detail?: string }>;
    return axiosError.response?.data?.detail || axiosError.message || fallback;
};

const elapsedFromSummary = (summary: ParticlePipelineSummary | null): number => {
    if (!summary) return 0;
    const start = Date.parse(summary.started_at || summary.created_at || "");
    if (!Number.isFinite(start)) return 0;
    const end = summary.ended_at ? Date.parse(summary.ended_at) : Date.now();
    if (!Number.isFinite(end)) return 0;
    return Math.max(0, end - start);
};

export type UseParticleExportPipelineProgressResult = {
    status: ParticleExportStatus;
    error: string | null;
    jobId: string | null;
    summary: ParticlePipelineSummary | null;
    elapsedMs: number;
    sessionName: string | null;
    scheduling: () => void;
    start: (jobId: string) => void;
    fail: (message: string) => void;
    reset: () => void;
};

export function useParticleExportPipelineProgress(): UseParticleExportPipelineProgressResult {
    const [status, setStatus] = useState<ParticleExportStatus>("idle");
    const [error, setError] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [summary, setSummary] = useState<ParticlePipelineSummary | null>(null);
    const [elapsedMs, setElapsedMs] = useState(0);
    const { emit: socketEmit, on: socketOn, connected: socketConnected } = useSocket();
    const statusRef = useRef(status);

    useEffect(() => { statusRef.current = status; }, [status]);

    const fetchSummary = useCallback(async (id: string) => {
        try {
            const response = await apiClient.get<ParticlePipelineSummary>(
                `/export/particle-pipeline/jobs/${id}/summary`,
            );
            const next = response.data;
            setSummary(next);
            setElapsedMs(elapsedFromSummary(next));
            if (TERMINAL_STATUSES.has(next.derived_status)) {
                setStatus(next.derived_status === "completed" ? "success" : "error");
                if (next.derived_status !== "completed") {
                    setError(next.error || `Particle pipeline ${next.derived_status}`);
                }
            } else {
                setStatus("running");
            }
        } catch (err: unknown) {
            const axiosError = err as AxiosError<{ detail?: string }>;
            if (axiosError.response?.status !== 404) {
                setStatus("error");
                setError(errorMessage(err, "Could not read particle pipeline progress"));
            }
        }
    }, []);

    useEffect(() => {
        apiClient.get<{ job_id: string }>("/export/particle-pipeline/jobs/active")
            .then(({ data }) => {
                setJobId(data.job_id);
                return fetchSummary(data.job_id);
            })
            .catch(() => {});
    }, [fetchSummary]);

    useEffect(() => {
        if (!jobId || !socketConnected) return;
        socketEmit("join_job_room", { job_id: jobId });
        const off = socketOn("import_progress", (data: { job_id: string }) => {
            if (data?.job_id === jobId && ["scheduling", "running"].includes(statusRef.current)) {
                fetchSummary(jobId);
            }
        });
        return () => {
            off();
            socketEmit("leave_job_room", { job_id: jobId });
        };
    }, [jobId, socketConnected, socketEmit, socketOn, fetchSummary]);

    useEffect(() => {
        if (!jobId || !["scheduling", "running"].includes(status)) return;
        const timeout = window.setTimeout(() => fetchSummary(jobId), 0);
        const interval = window.setInterval(() => fetchSummary(jobId), 5000);
        return () => {
            window.clearTimeout(timeout);
            window.clearInterval(interval);
        };
    }, [jobId, status, fetchSummary]);

    useEffect(() => {
        if (!["scheduling", "running"].includes(status)) return;
        const interval = window.setInterval(() => setElapsedMs(elapsedFromSummary(summary)), 1000);
        return () => window.clearInterval(interval);
    }, [status, summary]);

    const reset = useCallback(() => {
        if (["scheduling", "running"].includes(statusRef.current)) return;
        setStatus("idle");
        setError(null);
        setJobId(null);
        setSummary(null);
        setElapsedMs(0);
    }, []);

    const scheduling = useCallback(() => {
        setStatus("scheduling");
        setError(null);
        setSummary(null);
        setJobId(null);
        setElapsedMs(0);
    }, []);

    const start = useCallback((id: string) => {
        setJobId(id);
        setStatus("running");
    }, []);

    const fail = useCallback((message: string) => {
        setStatus("error");
        setError(message);
    }, []);

    return {
        status,
        error,
        jobId,
        summary,
        elapsedMs,
        sessionName: summary?.settings?.session_name ?? null,
        scheduling,
        start,
        fail,
        reset,
    };
}
