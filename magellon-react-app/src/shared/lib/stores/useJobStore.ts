import { create } from 'zustand';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface Job {
    job_id: string;
    plugin_id?: string;
    name: string;
    status: JobStatus;
    progress?: number;
    num_items?: number;
    started_at?: string;
    ended_at?: string;
    error?: string;
    settings?: any;
    result?: any;
}

interface JobStore {
    jobs: Job[];
    addJob: (job: Job) => void;
    updateJob: (jobUpdate: Partial<Job> & { job_id: string }) => void;
    upsertJob: (job: Job) => void;
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

    clearJobs: () => set({ jobs: [] }),
}));
