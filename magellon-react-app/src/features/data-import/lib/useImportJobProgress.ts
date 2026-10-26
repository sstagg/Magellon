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
    error?: string | null;
    /** Set while the import waits for a free slot (1 = next to start). */
    queue_position?: number | null;
    queue_waiting?: number;
    queue_limit?: number;
    /** Set when the import completed but some tasks failed. */
    warning?: string | null;
    /** Failed tasks grouped by step and reason, most common first. */
    problems?: { step: string; reason: string; count: number }[];
};

// Remaining-time estimate: completion rate over a sliding window, smoothed so
// the number settles instead of jumping with every poll.
const ETA_WINDOW_MS = 3 * 60 * 1000;
const ETA_SMOOTHING = 0.3;
type ProgressSample = { t: number; done: number };
type EtaState = { samples: ProgressSample[]; rate: number | null };  // rate: tasks per ms

const newEtaState = (): EtaState => ({ samples: [], rate: null });

/** Record this poll's progress and return the estimated ms remaining (or null). */
function estimateRemaining(state: EtaState, next: ImportSummary, now = Date.now()): number | null {
    const done = next.terminal_tasks;
    const remaining = next.total_tasks - done;
    const { samples } = state;
    const last = samples[samples.length - 1];
    if (!last || last.done !== done || now - last.t > 30000) samples.push({ t: now, done });
    while (samples.length > 2 && now - samples[0].t > ETA_WINDOW_MS) samples.shift();
    if (remaining <= 0 || done <= 0) return null;

    // Recent rate across the window; before there's history, fall back to the
    // average since the job was created (server time, UTC).
    let rate: number | null = null;
    const first = samples[0];
    if (samples.length >= 2 && done > first.done && now > first.t) {
        rate = (done - first.done) / (now - first.t);
    } else if (next.created_at) {
        const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(next.created_at) ? next.created_at : `${next.created_at}Z`;
        const created = Date.parse(iso);
        if (!Number.isNaN(created) && now > created) rate = done / (now - created);
    }
    if (rate && rate > 0) {
        state.rate = state.rate === null ? rate : ETA_SMOOTHING * rate + (1 - ETA_SMOOTHING) * state.rate;
    }
    return state.rate ? remaining / state.rate : null;
}

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
    /** Estimated ms until all tasks finish; null while there's no basis yet. */
    etaMs: number | null;
    sessionName: string | null;
    // Imperative actions invoked by the host component around the POST.
    scheduling: () => void;          // call before the import-start POST
    start: (jobId: string) => void;  // call with response.data.job_id on POST success
    succeed: () => void;             // sync paths with no pollable job_id
    fail: (message: string) => void; // call on POST failure
    reset: () => void;               // close: clears a finished import, minimises a running one
    /** The progress window was put in the background (the import keeps running). */
    minimized: boolean;
    minimize: () => void;
    /** A progress check failed transiently (network blip, restart); still retrying. */
    connectionIssue: boolean;
    cancelQueued: () => Promise<void>; // withdraw an import still waiting in the queue
    /** Stop a queued or running import and remove everything it created. */
    stop: () => Promise<void>;
    stopping: boolean;
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
    const [etaMs, setEtaMs] = useState<number | null>(null);
    const [minimized, setMinimized] = useState(false);
    const [connectionIssue, setConnectionIssue] = useState(false);
    const etaStateRef = useRef<EtaState>(newEtaState());
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
            setConnectionIssue(false);
            if (TERMINAL_STATUSES.has(next.derived_status)) {
                setStatus(next.derived_status === "completed" ? "success" : "error");
                setEtaMs(null);
                if (next.derived_status !== "completed") {
                    setError(next.error || `Import ${next.derived_status}`);
                }
            } else {
                setStatus("running");
                setEtaMs(estimateRemaining(etaStateRef.current, next));
            }
        } catch (err: unknown) {
            const axiosError = err as AxiosError<{ detail?: string }>;
            const code = axiosError.response?.status;
            // No response (network) or a gateway/server hiccup (e.g. a deploy):
            // the import itself is unaffected, so keep the window running and
            // keep polling instead of declaring it failed.
            if (code === undefined || code === 502 || code === 503 || code === 504) {
                setConnectionIssue(true);
            } else if (code !== 404) {
                setStatus("error");
                setError(errorMessage(err, "Could not read import progress"));
            }
            return;
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
                etaStateRef.current = newEtaState();
                setEtaMs(null);
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

    const minimize = useCallback(() => setMinimized(true), []);

    const reset = useCallback(() => {
        // Closing a running import only hides its window; it keeps going.
        if (["scheduling", "running"].includes(statusRef.current)) {
            setMinimized(true);
            return;
        }
        setMinimized(false);
        setConnectionIssue(false);
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
        etaStateRef.current = newEtaState();
        setEtaMs(null);
    }, []);

    const scheduling = useCallback(() => {
        setStatus("scheduling");
        setMinimized(false);
        setConnectionIssue(false);
        setError(null);
        setSummary(null);
        setJobId(null);
        setStepCounts(null);
        setStepTotals(null);
        setElapsedMs(0);
        etaStateRef.current = newEtaState();
        setEtaMs(null);
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

    // Stop the import (queued or running) and remove everything it created;
    // the summary then reports it "cancelled".
    const [stopping, setStopping] = useState(false);
    const stop = useCallback(async () => {
        const id = jobIdRef.current;
        if (!id) return;
        setStopping(true);
        try {
            await apiClient.post(`/export/job/${id}/stop`);
        } catch (err) {
            setError(errorMessage(err, "Could not stop the import"));
        } finally {
            setStopping(false);
        }
        await fetchSummary(id);
    }, [fetchSummary]);
    const cancelQueued = stop;

    const fail = useCallback((message: string) => {
        setStatus("error");
        setError(message);
    }, []);

    const sessionName = summary?.name?.replace(/^Import:\s*/i, "") ?? null;

    return {
        status, error, jobId, summary, stepCounts, stepTotals, elapsedMs, etaMs,
        sessionName, scheduling, start, succeed, fail, reset, cancelQueued, stop, stopping,
        minimized, minimize, connectionIssue,
    };
}
