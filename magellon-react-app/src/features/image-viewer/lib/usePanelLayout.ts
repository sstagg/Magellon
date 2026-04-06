import { useState, useEffect, useCallback } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';

interface UsePanelLayoutOptions {
    defaultSize?: number;
    minSize?: number;
    maxSize?: number;
    storageKey: string;
}

// Layout type for react-resizable-panels v4
type Layout = { [panelId: string]: number };

interface UsePanelLayoutReturn {
    leftPanelSize: number;
    handleResize: (layout: Layout) => void;
    resetLayout: () => void;
    isDrawerOpen: boolean;
    leftMargin: number;
}

const DRAWER_WIDTH = 240;

export const usePanelLayout = (options: UsePanelLayoutOptions): UsePanelLayoutReturn => {
    const {
        defaultSize = 35,
        minSize = 25,
        maxSize = 50,
        storageKey
    } = options;

    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Track drawer state
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        if (typeof window === 'undefined') return false;
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Panel size with constraints
    const [leftPanelSize, setLeftPanelSize] = useState(() => {
        if (typeof window === 'undefined') return defaultSize;
        const saved = localStorage.getItem(storageKey);
        const mobileDefault = isMobile ? 100 : defaultSize;
        const parsedSize = saved ? parseInt(saved, 10) : mobileDefault;
        return Math.max(minSize, Math.min(maxSize, parsedSize));
    });

    // Listen for drawer state changes using custom event
    useEffect(() => {
        const handleDrawerChange = (e: CustomEvent) => {
            setIsDrawerOpen(e.detail.isOpen);
        };

        const handleStorageChange = () => {
            if (typeof window === 'undefined') return;
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('drawer-state-changed' as any, handleDrawerChange);
        window.addEventListener('storage', handleStorageChange);

        return () => {
            window.removeEventListener('drawer-state-changed' as any, handleDrawerChange);
            window.removeEventListener('storage', handleStorageChange);
        };
    }, []);

    // Handle panel resize with constraints (react-resizable-panels v4 API)
    const handleResize = useCallback((layout: Layout) => {
        // Get the first panel's size (session-navigator panel)
        const sessionNavigatorSize = layout['session-navigator'];
        if (sessionNavigatorSize !== undefined) {
            const constrainedSize = Math.max(minSize, Math.min(maxSize, sessionNavigatorSize));
            setLeftPanelSize(constrainedSize);
            if (typeof window !== 'undefined') {
                localStorage.setItem(storageKey, constrainedSize.toString());
            }
        }
    }, [minSize, maxSize, storageKey]);

    // Reset layout to defaults
    const resetLayout = useCallback(() => {
        setLeftPanelSize(defaultSize);
        if (typeof window !== 'undefined') {
            localStorage.removeItem(storageKey);
        }
    }, [defaultSize, storageKey]);

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return {
        leftPanelSize,
        handleResize,
        resetLayout,
        isDrawerOpen,
        leftMargin
    };
};
