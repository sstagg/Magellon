import type { AxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useSocket } from "../../../shared/lib/useSocket.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

// ---------------------------------------------------------------------------
// Cross-instance dismissal coordination
//
// All four importer tabs are kept mounted simultaneously by MUI TabPanel
// (display:none when inactive, but never unmounted). Each has its own hook
// instance. When the user closes the dialog on one tab we must also reset
// the other three — otherwise the dialog reappears as soon as they navigate
// to that tab.
//
// We use a window-level custom event so hook instances coordinate without
// needing a shared React context.
// ---------------------------------------------------------------------------
const DISMISS_EVENT = "magellon:import-job-dismissed";
const _dismissed = new Set<string>();

function _broadcastDismissal(jobId: string) {
    _dismissed.add(jobId);
    window.dispatchEvent(new CustomEvent(DISMISS_EVENT, { detail: { jobId } }));
}

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
    succeed: () => void;             // sync paths with no pollable job_id
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
    const { emit: socketEmit, on: socketOn, connected: socketConnected } = useSocket();
    const statusRef = useRef(status);
    const jobIdRef = useRef(jobId);

    useEffect(() => { statusRef.current = status; }, [status]);
    useEffect(() => { jobIdRef.current = jobId; }, [jobId]);

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
                if (_dismissed.has(data.job_id)) return;  // user already closed this
                setJobId(data.job_id);
                return fetchSummary(data.job_id);
            })
            .catch(() => {});
    }, [fetchSummary, jobNamePrefix]);

    // Listen for dismissals broadcast by any other hook instance on this page.
    // Resets this instance when another tab's Close button was clicked.
    useEffect(() => {
        const handler = (e: Event) => {
            const dismissedId = (e as CustomEvent<{ jobId: string }>).detail.jobId;
            if (dismissedId === jobId) {
                setStatus("idle");
                setError(null);
                setJobId(null);
                setSummary(null);
                setStepCounts(null);
                setStepTotals(null);
                setElapsedMs(0);
            }
        };
        window.addEventListener(DISMISS_EVENT, handler);
        return () => window.removeEventListener(DISMISS_EVENT, handler);
    }, [jobId]);

    // Socket.IO: join the job room, listen for live progress events.
    // Depend on `socketConnected` so a reconnect re-runs the effect and
    // re-emits join_job_room — server-side room membership is dropped on
    // disconnect, and without re-joining the dialog stops receiving
    // per-step import_progress events even though /summary polling still
    // works (manifests as the per-step counters freezing partway through).
    useEffect(() => {
        if (!jobId || !socketConnected) return;
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
            // Best-effort: socket may already be disconnected (this cleanup
            // runs on socket-disconnect too) — emit is a no-op when
            // socketRef.current is null.
            socketEmit("leave_job_room", { job_id: jobId });
        };
    }, [jobId, socketConnected, socketEmit, socketOn, fetchSummary]);

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
        // Broadcast so every other mounted hook instance (hidden tabs) also closes.
        const currentJobId = jobIdRef.current;
        if (currentJobId) _broadcastDismissal(currentJobId);
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
        // Empty id is the "I called the sync endpoint and it didn't return a
        // poll-able job_id" path. Treat as immediate success rather than
        // sitting at scheduling forever.
        if (!id) {
            setStatus("success");
            return;
        }
        setJobId(id);
        setStatus("running");
    }, []);

    const succeed = useCallback(() => {
        setStatus("success");
        setError(null);
    }, []);

    const fail = useCallback((message: string) => {
        setStatus("error");
        setError(message);
    }, []);

    const sessionName = summary?.name?.replace(/^Import:\s*/i, "") ?? null;

    return {
        status, error, jobId, summary, stepCounts, stepTotals, elapsedMs,
        sessionName, scheduling, start, succeed, fail, reset,
    };
}
