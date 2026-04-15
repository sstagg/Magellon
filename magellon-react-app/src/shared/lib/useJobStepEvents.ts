import { useEffect, useRef, useState } from 'react';
import { useSocket } from './useSocket.ts';
import {
    JOIN_JOB_ROOM,
    LEAVE_JOB_ROOM,
    STEP_EVENT_NAME,
    StepEvent,
} from '../types/StepEvent.ts';

export interface UseJobStepEventsResult {
    events: StepEvent[];
    connected: boolean;
    /** Drop buffered events (useful when the user clears the panel). */
    clear: () => void;
}

/**
 * Subscribe to the per-job step-event stream on CoreService.
 *
 * Joins `job:<jobId>` on connect, listens for `step_event`, leaves the
 * room on unmount. Dedupes by CloudEvents `id` so a re-delivered event
 * from NATS doesn't double up in the list.
 *
 * Pass `null`/`undefined` for `jobId` to disable (useful when the
 * component mounts before a job is selected).
 */
export function useJobStepEvents(jobId: string | null | undefined): UseJobStepEventsResult {
    const { on, emit, connected } = useSocket();
    const [events, setEvents] = useState<StepEvent[]>([]);
    const seenIds = useRef<Set<string>>(new Set());

    useEffect(() => {
        if (!connected || !jobId) return;

        emit(JOIN_JOB_ROOM, { job_id: jobId });

        const off = on(STEP_EVENT_NAME, (event: StepEvent) => {
            // Only route to this hook instance if it matches this job.
            // (A second hook instance may be listening for a different job.)
            if (event?.data?.job_id !== jobId) return;
            if (seenIds.current.has(event.id)) return;
            seenIds.current.add(event.id);
            setEvents((prev) => [...prev, event]);
        });

        return () => {
            off();
            emit(LEAVE_JOB_ROOM, { job_id: jobId });
        };
    }, [connected, jobId, on, emit]);

    // Reset buffer when the target job changes.
    useEffect(() => {
        seenIds.current = new Set();
        setEvents([]);
    }, [jobId]);

    return {
        events,
        connected,
        clear: () => {
            seenIds.current = new Set();
            setEvents([]);
        },
    };
}
