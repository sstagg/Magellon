import { useCallback, useEffect, useState } from 'react';
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
    /** Current user-overridden width in px, or null when auto-fit applies. */
    userWidthPx: number | null;
    /** Called from Panel's onResize. Persists the user's pick. */
    onUserResize: (sizePx: number) => void;
    /** Forget the user override (e.g. operator double-clicked the separator). */
    resetLayout: () => void;
    isDrawerOpen: boolean;
    leftMargin: number;
    minPx: number;
    maxPx: number;
}

const DRAWER_WIDTH = 240;

/**
 * Layout state for the images-page left panel.
 *
 * Defaults to auto-fitting to the visible column count (computed at the call
 * site). The user can drag the splitter to override; the override is
 * persisted to localStorage and takes priority over auto-fit until reset.
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

    const [userWidthPx, setUserWidthPx] = useState<number | null>(() => {
        if (typeof window === 'undefined') return null;
        const saved = window.localStorage.getItem(storageKey);
        if (!saved) return null;
        const parsed = Number.parseInt(saved, 10);
        if (Number.isNaN(parsed)) return null;
        return Math.max(minPx, Math.min(maxPx, parsed));
    });

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

    const onUserResize = useCallback((sizePx: number) => {
        const clamped = Math.max(minPx, Math.min(maxPx, Math.round(sizePx)));
        setUserWidthPx(clamped);
        if (typeof window !== 'undefined') {
            window.localStorage.setItem(storageKey, String(clamped));
        }
    }, [minPx, maxPx, storageKey]);

    const resetLayout = useCallback(() => {
        setUserWidthPx(null);
        if (typeof window !== 'undefined') {
            window.localStorage.removeItem(storageKey);
        }
    }, [storageKey]);

    const leftMargin = isDrawerOpen && !isMobile ? DRAWER_WIDTH : 0;

    return {
        userWidthPx,
        onUserResize,
        resetLayout,
        isDrawerOpen,
        leftMargin,
        minPx,
        maxPx,
    };
};
