import { useState } from 'react';
import { useJobStepEvents } from '../../../shared/lib/useJobStepEvents.ts';

/** Step-event progress for a dispatched (RMQ) picking job. */
export function useDispatchProgress() {
    const [dispatchJobId, setDispatchJobId] = useState<string | null>(null);

    const { events: dispatchEvents, connected: socketConnected } = useJobStepEvents(dispatchJobId);
    const latestDispatchEvent = dispatchEvents[dispatchEvents.length - 1];
    const latestProgressEvent = [...dispatchEvents].reverse().find((e) => e.type === 'magellon.step.progress');
    const dispatchPercent = (latestProgressEvent?.data as { percent?: number })?.percent;
    const dispatchMessage =
        (latestDispatchEvent?.data as { message?: string })?.message ||
        (latestProgressEvent?.data as { message?: string })?.message ||
        (latestDispatchEvent?.data as { error?: string })?.error ||
        'Task queued';
    const dispatchCompleted = dispatchEvents.some((e) => e.type === 'magellon.step.completed');
    const dispatchFailed = dispatchEvents.some((e) => e.type === 'magellon.step.failed');

    return {
        setDispatchJobId,
        socketConnected,
        dispatchPercent,
        dispatchMessage,
        dispatchCompleted,
        dispatchFailed,
    };
}
