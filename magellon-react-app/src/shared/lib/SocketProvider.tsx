import React, { useEffect } from 'react';
import { useSocket } from './useSocket.ts';
import { useJobStore, Job } from '../../app/layouts/PanelLayout/useJobStore.ts';
import { useLogStore, LogEntry } from '../../app/layouts/PanelLayout/useLogStore.ts';

/**
 * Global Socket.IO listener that routes events to Zustand stores.
 * Mount this once near the app root (inside PanelTemplate or App).
 */
export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { on, connected } = useSocket();
    const addLog = useLogStore((s) => s.addLog);
    const { addJob, updateJob } = useJobStore();

    useEffect(() => {
        if (!connected) return;

        // Job updates from backend
        const offJob = on('job_update', (data: any) => {
            const job: Job = {
                id: data.id,
                name: data.name || 'Job',
                type: data.type || 'unknown',
                status: data.status,
                progress: data.progress,
                started_at: data.started_at,
                num_particles: data.num_particles,
                error: data.error,
                result: data.result,
            };

            // Check if job already exists in store
            const existing = useJobStore.getState().jobs.find((j) => j.id === job.id);
            if (existing) {
                updateJob(job);
            } else {
                addJob(job);
            }
        });

        // Log entries from backend
        const offLog = on('log_entry', (data: LogEntry) => {
            addLog(data);
        });

        // Also push a connection log
        addLog({
            id: `log-connect-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
            level: 'info',
            source: 'socket',
            message: 'Connected to server',
        });

        return () => {
            offJob();
            offLog();
        };
    }, [connected]);

    return <>{children}</>;
};
