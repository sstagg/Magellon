import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';

interface UsePanelLayoutOptions {
    /** Minimum pixel width of the left (column-browser) panel. */
    minPx?: number;
    /** Maximum pixel width of the left (column-browser) panel. */
    maxPx?: number;
    /** localStorage key for a user-overridden width. */
    storageKey: string;
}

interface UsePanelLayoutReturn {
    /** Initial user-overridden width in px (frozen at mount, never changes). */
    initialUserWidthPx: number | null;
    /** Write a new width to localStorage. Does NOT trigger a re-render. */
    persistWidth: (sizePx: number) => void;
    isDrawerOpen: boolean;
    leftMargin: number;
    minPx: number;
    maxPx: number;
}

const DRAWER_WIDTH = 240;

/**
 * Layout state for the images-page left panel.
 *
 * The initial user width is read from localStorage exactly once at mount.
 * After that the panel size is owned by `react-resizable-panels` — we never
 * call setState in response to drags, because re-rendering mid-drag
 * disrupts the library's pointer-tracking and breaks one of the drag
 * directions (see commit history).
 *
 * `persistWidth` writes to localStorage directly; the new value will be
 * picked up on the next page load.
 */
export const usePanelLayout = (options: UsePanelLayoutOptions): UsePanelLayoutReturn => {
    const {
        minPx = 260,
        maxPx = 1200,
        storageKey,
    } = options;

    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        if (typeof window === 'undefined') return false;
        const saved = window.localStorage.getItem('drawerOpen');
        return saved ? (JSON.parse(saved) as boolean) : false;
    });

    const initialUserWidthPx = useMemo<number | null>(() => {
        if (typeof window === 'undefined') return null;
        const saved = window.localStorage.getItem(storageKey);
        if (!saved) return null;
        const parsed = Number.parseInt(saved, 10);
        if (Number.isNaN(parsed)) return null;
        return Math.max(minPx, Math.min(maxPx, parsed));
    // We freeze this on mount; localStorage changes during the session
    // are intentionally ignored.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const handleDrawerChange = (e: Event) => {
            const custom = e as CustomEvent<{ isOpen: boolean }>;
            if (custom.detail) setIsDrawerOpen(custom.detail.isOpen);
        };
        const handleStorageChange = () => {
            if (typeof window === 'undefined') return;
            const saved = window.localStorage.getItem('drawerOpen');
            setIsDrawerOpen(saved ? (JSON.parse(saved) as boolean) : false);
        };
        window.addEventListener('drawer-state-changed', handleDrawerChange);
        window.addEventListener('storage', handleStorageChange);
        return () => {
            window.removeEventListener('drawer-state-changed', handleDrawerChange);
            window.removeEventListener('storage', handleStorageChange);
        };
    }, []);

    const persistWidth = useCallback((sizePx: number) => {
        if (typeof window === 'undefined') return;
        const clamped = Math.max(minPx, Math.min(maxPx, Math.round(sizePx)));
        window.localStorage.setItem(storageKey, String(clamped));
    }, [minPx, maxPx, storageKey]);

    const leftMargin = isDrawerOpen && !isMobile ? DRAWER_WIDTH : 0;

    return {
        initialUserWidthPx,
        persistWidth,
        isDrawerOpen,
        leftMargin,
        minPx,
        maxPx,
    };
};
