import { create } from 'zustand';

export interface Job {
    id: string;
    name: string;
    type: string;
    status: 'running' | 'completed' | 'failed' | 'queued';
    progress?: number;
    started_at?: string;
    duration?: string;
    num_particles?: number;
    error?: string;
    result?: any;
}

interface JobStore {
    jobs: Job[];
    addJob: (job: Job) => void;
    updateJob: (jobUpdate: Partial<Job> & { id: string }) => void;
    clearJobs: () => void;
}

export const useJobStore = create<JobStore>((set) => ({
    jobs: [],

    addJob: (job) => set((state) => ({
        jobs: [job, ...state.jobs],
    })),

    updateJob: (jobUpdate) => set((state) => ({
        jobs: state.jobs.map((j) =>
            j.id === jobUpdate.id ? { ...j, ...jobUpdate } : j
        ),
    })),

    clearJobs: () => set({ jobs: [] }),
}));
