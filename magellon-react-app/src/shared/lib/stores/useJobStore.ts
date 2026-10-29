import { create } from 'zustand';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Job {
    job_id: string;
    plugin_id?: string;
    name: string;
    status: JobStatus;
    progress?: number;
    num_items?: number;
    started_at?: string;
    ended_at?: string;
    /** Imports waiting in the queue: when submitted, and their place in line. */
    queued_at?: string;
    queue_position?: number;
    // Running jobs: task counts and estimated seconds left (from the server).
    tasks_total?: number;
    tasks_done?: number;
    eta_seconds?: number;
    /** Running imports: per plugin step, results so far and the commonest failure. */
    steps?: { step: string; total: number; ok: number; failed: number; reason?: string | null }[];
    // A running import still reading its session (no tasks yet).
    preparing?: boolean;
    // The session the job wrote into (finished imports can be deleted).
    session_name?: string | null;
    // Owner of the session / import (may stop or delete it, like admins).
    owner_id?: string | null;
    owner_name?: string | null;
    error?: string;
    settings?: Record<string, unknown>;
    result?: Record<string, unknown>;
}

interface JobStore {
    jobs: Job[];
    addJob: (job: Job) => void;
    updateJob: (jobUpdate: Partial<Job> & { job_id: string }) => void;
    upsertJob: (job: Job) => void;
    /** Replace the list with the server's (drops entries that no longer exist). */
    setJobs: (jobs: Job[]) => void;
    clearJobs: () => void;
}

export const useJobStore = create<JobStore>((set) => ({
    jobs: [],

    addJob: (job) => set((state) => ({
        jobs: [job, ...state.jobs],
    })),

    updateJob: (jobUpdate) => set((state) => ({
        jobs: state.jobs.map((j) =>
            j.job_id === jobUpdate.job_id ? { ...j, ...jobUpdate } : j
        ),
    })),

    upsertJob: (job) => set((state) => {
        const idx = state.jobs.findIndex((j) => j.job_id === job.job_id);
        if (idx === -1) return { jobs: [job, ...state.jobs] };
        const next = [...state.jobs];
        next[idx] = { ...next[idx], ...job };
        return { jobs: next };
    }),

    setJobs: (jobs) => set({ jobs }),

    clearJobs: () => set({ jobs: [] }),
}));
