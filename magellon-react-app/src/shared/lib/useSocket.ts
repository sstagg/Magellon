import { useEffect, useRef, useState, useCallback } from 'react';
import type { Socket } from 'socket.io-client';
import { io } from 'socket.io-client';
import { settings } from '../config/settings.ts';

const SOCKET_URL = settings.ConfigData.SERVER_API_URL;

let sharedSocket: Socket | null = null;
let refCount = 0;

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
    const socketRef = useRef<Socket | null>(null);

    useEffect(() => {
        const socket = getSocket();
        socketRef.current = socket;
        refCount++;

        const onConnect = () => setConnected(true);
        const onDisconnect = () => setConnected(false);

        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);

        if (socket.connected) {
            setConnected(true);
        }

        return () => {
            socket.off('connect', onConnect);
            socket.off('disconnect', onDisconnect);
            refCount--;
            if (refCount <= 0 && sharedSocket) {
                sharedSocket.disconnect();
                sharedSocket = null;
                refCount = 0;
            }
        };
    }, []);

    const on = useCallback(<T = unknown>(event: string, handler: (data: T) => void) => {
        socketRef.current?.on(event, handler as (data: unknown) => void);
        return () => { socketRef.current?.off(event, handler as (data: unknown) => void); };
    }, []);

    const emit = useCallback((event: string, data?: unknown) => {
        socketRef.current?.emit(event, data);
    }, []);

    return {
        socket: socketRef.current,
        connected,
        on,
        emit,
        sid: socketRef.current?.id,
    };
}
