/**
 * Unit tests for the per-job step-event subscription hook.
 *
 * useSocket is mocked with a manual recorder so we can simulate the
 * server pushing events without standing up a Socket.IO connection.
 * The hook under test owns: room join/leave lifecycle, dedup by event
 * id, isolation between different jobs, and reset on jobId change.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

type Handler = (...args: any[]) => void;

const listeners = new Map<string, Set<Handler>>();
const emitted: Array<{ event: string; data: any }> = [];
let mockConnected = true;

vi.mock('../../shared/lib/useSocket.ts', () => ({
    useSocket: () => ({
        socket: null,
        connected: mockConnected,
        sid: 'test-sid',
        on: (event: string, handler: Handler) => {
            if (!listeners.has(event)) listeners.set(event, new Set());
            listeners.get(event)!.add(handler);
            return () => listeners.get(event)?.delete(handler);
        },
        emit: (event: string, data?: any) => {
            emitted.push({ event, data });
        },
    }),
}));

import { useJobStepEvents } from '../../shared/lib/useJobStepEvents.ts';
import {
    JOIN_JOB_ROOM,
    LEAVE_JOB_ROOM,
    STEP_EVENT_NAME,
    StepEvent,
} from '../../shared/types/StepEvent.ts';

function pushServerEvent(ev: StepEvent) {
    listeners.get(STEP_EVENT_NAME)?.forEach((h) => h(ev));
}

function makeEvent(jobId: string, id: string, type: StepEvent['type']): StepEvent {
    return {
        id,
        type,
        source: 'magellon/plugins/ctf',
        subject: `magellon.job.${jobId}.step.ctf`,
        time: new Date().toISOString(),
        data: { job_id: jobId, step: 'ctf' },
    };
}

beforeEach(() => {
    listeners.clear();
    emitted.length = 0;
    mockConnected = true;
});

describe('useJobStepEvents', () => {
    it('joins the job room on mount and leaves on unmount', () => {
        const jobId = 'job-1';
        const { unmount } = renderHook(() => useJobStepEvents(jobId));

        expect(emitted).toContainEqual({ event: JOIN_JOB_ROOM, data: { job_id: jobId } });

        unmount();
        expect(emitted).toContainEqual({ event: LEAVE_JOB_ROOM, data: { job_id: jobId } });
    });

    it('appends incoming step_event matching the job id', () => {
        const jobId = 'job-1';
        const { result } = renderHook(() => useJobStepEvents(jobId));

        act(() => {
            pushServerEvent(makeEvent(jobId, 'evt-1', 'magellon.step.started'));
            pushServerEvent(makeEvent(jobId, 'evt-2', 'magellon.step.completed'));
        });

        expect(result.current.events.map((e) => e.id)).toEqual(['evt-1', 'evt-2']);
    });

    it('dedupes by CloudEvents id (re-delivery is a no-op)', () => {
        const jobId = 'job-1';
        const { result } = renderHook(() => useJobStepEvents(jobId));

        act(() => {
            const ev = makeEvent(jobId, 'evt-dup', 'magellon.step.started');
            pushServerEvent(ev);
            pushServerEvent(ev);
            pushServerEvent(ev);
        });

        expect(result.current.events).toHaveLength(1);
    });

    it('ignores events that belong to a different job_id', () => {
        const jobId = 'job-1';
        const { result } = renderHook(() => useJobStepEvents(jobId));

        act(() => {
            pushServerEvent(makeEvent('job-other', 'evt-other', 'magellon.step.started'));
            pushServerEvent(makeEvent(jobId, 'evt-mine', 'magellon.step.completed'));
        });

        expect(result.current.events.map((e) => e.id)).toEqual(['evt-mine']);
    });

    it('resets the buffer when the watched jobId changes', () => {
        let jobId = 'job-1';
        const { result, rerender } = renderHook(() => useJobStepEvents(jobId));

        act(() => {
            pushServerEvent(makeEvent('job-1', 'evt-a', 'magellon.step.started'));
        });
        expect(result.current.events).toHaveLength(1);

        jobId = 'job-2';
        rerender();

        expect(result.current.events).toHaveLength(0);
    });

    it('does nothing when jobId is null', () => {
        renderHook(() => useJobStepEvents(null));
        expect(emitted).toEqual([]);
    });

    it('clear() empties the buffer and accepts re-delivery of cleared events', () => {
        const jobId = 'job-1';
        const { result } = renderHook(() => useJobStepEvents(jobId));

        act(() => {
            pushServerEvent(makeEvent(jobId, 'evt-1', 'magellon.step.started'));
        });
        expect(result.current.events).toHaveLength(1);

        act(() => {
            result.current.clear();
        });
        expect(result.current.events).toHaveLength(0);

        act(() => {
            pushServerEvent(makeEvent(jobId, 'evt-1', 'magellon.step.started'));
        });
        expect(result.current.events).toHaveLength(1);
    });
});
