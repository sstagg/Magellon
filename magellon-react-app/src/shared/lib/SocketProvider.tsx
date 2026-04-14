import React, { useEffect } from 'react';
import { useSocket } from './useSocket.ts';
import { useJobStore, Job } from '../../app/layouts/PanelLayout/useJobStore.ts';
import { useLogStore, LogEntry } from '../../app/layouts/PanelLayout/useLogStore.ts';

/**
 * Global Socket.IO listener that routes events to Zustand stores.
 * Mount this once near the app root (inside PanelTemplate or App).
 *
 * Job payloads follow the backend envelope:
 *   { job_id, plugin_id, name, status, progress, num_items, started_at, ended_at, error, result }
 */
export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { on, connected } = useSocket();
    const addLog = useLogStore((s) => s.addLog);
    const upsertJob = useJobStore((s) => s.upsertJob);

    useEffect(() => {
        if (!connected) return;

        const offJob = on('job_update', (data: any) => {
            // Backend envelope is already the shape we store. Keep a small
            // fallback so legacy {id, type} payloads don't silently drop.
            const job: Job = {
                job_id: data.job_id ?? data.id,
                plugin_id: data.plugin_id,
                name: data.name || 'Job',
                status: data.status,
                progress: data.progress,
                num_items: data.num_items ?? data.num_particles,
                started_at: data.started_at,
                ended_at: data.ended_at,
                error: data.error,
                settings: data.settings,
                result: data.result,
            };
            if (!job.job_id) return;
            upsertJob(job);
        });

        const offLog = on('log_entry', (data: LogEntry) => {
            addLog(data);
        });

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
