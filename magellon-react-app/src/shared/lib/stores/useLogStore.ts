import { create } from 'zustand';

export interface LogEntry {
    id: string;
    timestamp: string;
    level: 'info' | 'warn' | 'error' | 'debug';
    message: string;
    source?: string;
}

interface LogStore {
    logs: LogEntry[];
    addLog: (entry: LogEntry) => void;
    clearLogs: () => void;
}

const MAX_LOGS = 500;

export const useLogStore = create<LogStore>((set) => ({
    logs: [],

    addLog: (entry) => set((state) => {
        const updated = [...state.logs, entry];
        // Keep only the last MAX_LOGS entries
        return { logs: updated.length > MAX_LOGS ? updated.slice(-MAX_LOGS) : updated };
    }),

    clearLogs: () => set({ logs: [] }),
}));
