import { useEffect, useState, useCallback } from 'react';
import type { Socket } from 'socket.io-client';
import { io } from 'socket.io-client';
import { settings } from '../config/settings.ts';

const SOCKET_URL = settings.ConfigData.SERVER_API_URL;

let sharedSocket: Socket | null = null;
let refCount = 0;
let teardownTimer: ReturnType<typeof setTimeout> | null = null;

function getSocket(): Socket {
    if (!sharedSocket) {
        sharedSocket = io(SOCKET_URL, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 2000,
            // Function form so every (re)connect reads the current token,
            // not the one captured when the socket was first created.
            auth: (cb) => cb({ token: localStorage.getItem('access_token') }),
        });
    }
    return sharedSocket;
}

export function useSocket() {
    const [connected, setConnected] = useState(false);
    // State (not a ref): the first render must re-render once the socket
    // exists, and consumers reading `sid` need a value that updates when
    // the connection (re)establishes. The previous ref-based version
    // returned null/undefined on first render and never notified.
    const [socket, setSocket] = useState<Socket | null>(null);
    const [sid, setSid] = useState<string | undefined>(undefined);

    useEffect(() => {
        const s = getSocket();
        setSocket(s);
        refCount++;
        if (teardownTimer) {
            clearTimeout(teardownTimer);
            teardownTimer = null;
        }

        const onConnect = () => {
            setConnected(true);
            setSid(s.id);
        };
        const onDisconnect = () => {
            setConnected(false);
            setSid(undefined);
        };

        s.on('connect', onConnect);
        s.on('disconnect', onDisconnect);

        if (s.connected) {
            setConnected(true);
            setSid(s.id);
        }

        return () => {
            s.off('connect', onConnect);
            s.off('disconnect', onDisconnect);
            refCount--;
            if (refCount <= 0) {
                refCount = 0;
                // Delay teardown: route transitions briefly unmount every
                // consumer, and dropping the socket there would silently
                // lose server-side room membership. Only disconnect if
                // nobody remounts within the grace window.
                if (teardownTimer) clearTimeout(teardownTimer);
                teardownTimer = setTimeout(() => {
                    if (refCount <= 0 && sharedSocket) {
                        sharedSocket.disconnect();
                        sharedSocket = null;
                    }
                    teardownTimer = null;
                }, 5000);
            }
        };
    }, []);

    const on = useCallback(<T = unknown>(event: string, handler: (data: T) => void) => {
        const s = getSocket();
        s.on(event, handler as (data: unknown) => void);
        return () => { s.off(event, handler as (data: unknown) => void); };
    }, []);

    const emit = useCallback((event: string, data?: unknown) => {
        getSocket().emit(event, data);
    }, []);

    return {
        socket,
        connected,
        on,
        emit,
        sid,
    };
}
