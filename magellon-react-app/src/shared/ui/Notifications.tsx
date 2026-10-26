import { useEffect } from 'react';
import { create } from 'zustand';
import { Alert, CircularProgress, Snackbar, Stack } from '@mui/material';

type Severity = 'info' | 'success' | 'warning' | 'error';

interface Notice {
    id: number;
    message: string;
    severity: Severity;
    /** Shows a spinner and stays until updated (e.g. "Deleting…"). */
    busy?: boolean;
}

interface NoticeStore {
    notices: Notice[];
    push: (notice: Omit<Notice, 'id'>) => number;
    update: (id: number, notice: Partial<Omit<Notice, 'id'>>) => void;
    dismiss: (id: number) => void;
}

let nextId = 1;

/**
 * App-wide notifications (bottom-left, themed like the rest of the site).
 * `notify(...)` returns an id; `updateNotice(id, ...)` turns a busy notice
 * into its outcome ("Deleting x…" → "Deleted x").
 */
export const useNotifications = create<NoticeStore>((set) => ({
    notices: [],
    push: (notice) => {
        const id = nextId++;
        set((s) => ({ notices: [...s.notices, { ...notice, id }] }));
        return id;
    },
    update: (id, notice) => set((s) => ({
        notices: s.notices.map((n) => (n.id === id ? { ...n, ...notice } : n)),
    })),
    dismiss: (id) => set((s) => ({ notices: s.notices.filter((n) => n.id !== id) })),
}));

export const notify = (message: string, severity: Severity = 'info', busy = false) =>
    useNotifications.getState().push({ message, severity, busy });

export const updateNotice = (id: number, message: string, severity: Severity) =>
    useNotifications.getState().update(id, { message, severity, busy: false });

/** Renders the notifications; mount once (in the panel header). */
export const Notifier = () => {
    const { notices, dismiss } = useNotifications();
    return (
        <Snackbar open={notices.length > 0} anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}>
            <Stack spacing={1}>
                {notices.map((n) => (
                    <NoticeAlert key={n.id} notice={n} onClose={() => dismiss(n.id)} />
                ))}
            </Stack>
        </Snackbar>
    );
};

const NoticeAlert = ({ notice, onClose }: { notice: Notice; onClose: () => void }) => {
    // Outcomes disappear on their own; busy notices wait for their outcome.
    const autoClose = !notice.busy && notice.severity !== 'error';
    useEffect(() => {
        if (!autoClose) return;
        const timer = window.setTimeout(onClose, 6000);
        return () => window.clearTimeout(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoClose, notice.message]);
    return (
        <Alert
            variant="filled"
            severity={notice.severity}
            icon={notice.busy ? <CircularProgress size={18} color="inherit" /> : undefined}
            onClose={notice.busy ? undefined : onClose}
            sx={{ minWidth: 300, boxShadow: 3 }}
        >
            {notice.message}
        </Alert>
    );
};
