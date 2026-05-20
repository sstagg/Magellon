/**
 * Live tail of plugin logs via Socket.IO (Phase 6/7).
 *
 * Subscribes to the ``plugin:{plugin_id}`` room and accumulates one
 * ``plugin_log`` event per line. Bounded buffer so a chatty plugin
 * doesn't OOM the browser.
 *
 * Companion to the one-shot ``usePluginLogs`` query (installerApi.ts).
 * The pattern is:
 *   1. Render the one-shot tail on mount to give the panel content
 *      immediately.
 *   2. usePluginLogStream appends new lines as they arrive.
 *
 * The hook leaves the room on unmount; the server-side streamer stops
 * the follower when no clients remain.
 */
import { useEffect, useRef, useState } from 'react';
import { useSocket } from '../../../shared/lib/useSocket.ts';

export interface PluginLogLine {
    /** Monotonic counter so React keys are stable. */
    id: number;
    /** The line text (already CRLF-normalized server-side). */
    line: string;
    /** True when the server is reporting a follower failure (e.g.
     *  ``<docker CLI not available>``). Render in a different color. */
    error: boolean;
    /** Client-side receipt timestamp; servers don't emit one. */
    ts: number;
}

interface UsePluginLogStreamOptions {
    /** Maximum lines retained in the in-memory buffer. Default 2000 —
     *  enough for ~5 minutes of a chatty plugin. */
    bufferSize?: number;
    /** Pause subscription without unmounting. Useful when the user
     *  switches tabs but the component stays mounted. */
    paused?: boolean;
}

export function usePluginLogStream(
    pluginId: string | null | undefined,
    opts: UsePluginLogStreamOptions = {},
) {
    const { bufferSize = 2000, paused = false } = opts;
    const { socket, connected, emit } = useSocket();
    const [lines, setLines] = useState<PluginLogLine[]>([]);
    const counter = useRef(0);

    useEffect(() => {
        if (!pluginId || !socket || !connected || paused) return;

        let joined = false;

        const onLogLine = (payload: { line: string; error?: boolean }) => {
            counter.current += 1;
            const next: PluginLogLine = {
                id: counter.current,
                line: payload.line,
                error: !!payload.error,
                ts: Date.now(),
            };
            setLines((prev) => {
                const merged = [...prev, next];
                if (merged.length > bufferSize) {
                    return merged.slice(merged.length - bufferSize);
                }
                return merged;
            });
        };

        socket.on('plugin_log', onLogLine);

        // Join the plugin room. Server replies with {ok, room} or
        // {ok: false, error}; we don't surface the error UI-side here
        // (the one-shot /logs query already returns 404 with the same
        // info), but we log it for debugging.
        socket.emit(
            'join_plugin_room',
            { plugin_id: pluginId },
            (ack: { ok: boolean; error?: string }) => {
                joined = !!ack?.ok;
                if (!joined && ack?.error) {
                    console.warn(`join_plugin_room rejected: ${ack.error}`);
                }
            },
        );

        return () => {
            socket.off('plugin_log', onLogLine);
            if (joined) {
                emit('leave_plugin_room', { plugin_id: pluginId });
            }
        };
    }, [pluginId, socket, connected, paused, bufferSize, emit]);

    const clear = () => setLines([]);

    return { lines, connected, clear };
}
