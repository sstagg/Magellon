import type { AxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useSocket } from "../../../shared/lib/useSocket.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export type ImportStatus = "idle" | "scheduling" | "running" | "success" | "error";

// Step keys the Magellon importer reports. Other importers may emit a
// subset (or none) — the dialog tolerates missing keys at zero.
export type StepCounts = {
    png: number;
    fft: number;
    ctf: number;
    motioncor: number;
};

export type ImportSummary = {
    job_id: string;
    name: string;
    status: string;
    derived_status: string;
    total_tasks: number;
    terminal_tasks: number;
    totals: Record<string, number>;
    by_category: Record<string, Record<string, number>>;
    created_at?: string | null;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

const errorMessage = (err: unknown, fallback: string) => {
    const axiosError = err as AxiosError<{ detail?: string }>;
    return axiosError.response?.data?.detail || axiosError.message || fallback;
};

export type UseImportJobProgressResult = {
    status: ImportStatus;
    error: string | null;
    jobId: string | null;
    summary: ImportSummary | null;
    stepCounts: StepCounts | null;
    stepTotals: StepCounts | null;
    elapsedMs: number;
    sessionName: string | null;
    // Imperative actions invoked by the host component around the POST.
    scheduling: () => void;          // call before the import-start POST
    start: (jobId: string) => void;  // call with response.data.job_id on POST success
    fail: (message: string) => void; // call on POST failure
    reset: () => void;               // close / clear (host's dialog onClose)
};

/**
 * Owns the lifecycle of an import job: socket join, polling fallback,
 * /job/{id}/summary fetch, status derivation. Designed to be the only
 * shared state between any import-form component and the
 * ImportProgressDialog it renders.
 *
 * @param jobNamePrefix  Used to guard the "resume active job on mount"
 *   path so a Magellon page doesn't resume a Leginon job (or vice versa).
 *   Match against ImageJob.name (set by importer to e.g. "Import: 24DEC03A").
 *   Pass "" to disable the resume.
 */
export function useImportJobProgress(jobNamePrefix = "Import:"): UseImportJobProgressResult {
    const [status, setStatus] = useState<ImportStatus>("idle");
    const [error, setError] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [summary, setSummary] = useState<ImportSummary | null>(null);
    const [stepCounts, setStepCounts] = useState<StepCounts | null>(null);
    const [stepTotals, setStepTotals] = useState<StepCounts | null>(null);
    const [elapsedMs, setElapsedMs] = useState<number>(0);
    const { emit: socketEmit, on: socketOn } = useSocket();
    const statusRef = useRef(status);

    useEffect(() => { statusRef.current = status; }, [status]);

    const fetchSummary = useCallback(async (id: string) => {
        try {
            const response = await apiClient.get<ImportSummary>(`/export/job/${id}/summary`);
            const next = response.data;
            setSummary(next);
            if (TERMINAL_STATUSES.has(next.derived_status)) {
                setStatus(next.derived_status === "completed" ? "success" : "error");
                if (next.derived_status !== "completed") {
                    setError(`Import ${next.derived_status}`);
                }
            } else {
                setStatus("running");
            }
        } catch (err: unknown) {
            const axiosError = err as AxiosError<{ detail?: string }>;
            if (axiosError.response?.status !== 404) {
                setStatus("error");
                setError(errorMessage(err, "Could not read import progress"));
            }
        }
    }, []);

    // Resume monitoring if an import is already running on mount.
    useEffect(() => {
        if (!jobNamePrefix) return;
        apiClient.get<{ job_id: string; name?: string }>("/export/jobs/active")
            .then(({ data }) => {
                if (!data.name?.startsWith(jobNamePrefix)) return;
                setJobId(data.job_id);
                return fetchSummary(data.job_id);
            })
            .catch(() => {});
    }, [fetchSummary, jobNamePrefix]);

    // Socket.IO: join the job room, listen for live progress events.
    useEffect(() => {
        if (!jobId) return;
        socketEmit("join_job_room", { job_id: jobId });
        const off = socketOn("import_progress", (data: {
            job_id: string;
            event?: string;
            step_counts?: StepCounts;
            step_totals?: StepCounts;
            elapsed_ms?: number;
        }) => {
            if (data?.job_id === jobId && ["scheduling", "running"].includes(statusRef.current)) {
                fetchSummary(jobId);
                if (data.step_counts) setStepCounts(data.step_counts);
                if (data.step_totals) setStepTotals(data.step_totals);
                if (data.elapsed_ms !== undefined) setElapsedMs(data.elapsed_ms);
            }
        });
        return () => {
            off();
            socketEmit("leave_job_room", { job_id: jobId });
        };
    }, [jobId, socketEmit, socketOn, fetchSummary]);

    // Polling fallback every 5s for hosts where the socket misses an event.
    useEffect(() => {
        if (!jobId || !["scheduling", "running"].includes(status)) return;
        const timeout = window.setTimeout(() => fetchSummary(jobId), 0);
        const interval = window.setInterval(() => fetchSummary(jobId), 5000);
        return () => {
            window.clearTimeout(timeout);
            window.clearInterval(interval);
        };
    }, [jobId, status, fetchSummary]);

    const reset = useCallback(() => {
        if (["scheduling", "running"].includes(statusRef.current)) return;
        setStatus("idle");
        setError(null);
        setJobId(null);
        setSummary(null);
        setStepCounts(null);
        setStepTotals(null);
        setElapsedMs(0);
    }, []);

    const scheduling = useCallback(() => {
        setStatus("scheduling");
        setError(null);
        setSummary(null);
        setJobId(null);
        setStepCounts(null);
        setStepTotals(null);
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

    const sessionName = summary?.name?.replace(/^Import:\s*/i, "") ?? null;

    return {
        status, error, jobId, summary, stepCounts, stepTotals, elapsedMs,
        sessionName, scheduling, start, fail, reset,
    };
}
