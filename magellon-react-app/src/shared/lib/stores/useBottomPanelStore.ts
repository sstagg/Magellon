import { create } from 'zustand';

export type SidePanelType = 'jobs' | 'logs' | 'settings' | null;

interface SidePanelState {
    activePanel: SidePanelType;
    panelWidth: number;
    togglePanel: (panel: SidePanelType) => void;
    openPanel: (panel: SidePanelType) => void;
    closePanel: () => void;
}

export const useSidePanelStore = create<SidePanelState>((set) => ({
    activePanel: null,
    panelWidth: 360,
    togglePanel: (panel) => set((state) => ({
        activePanel: state.activePanel === panel ? null : panel,
    })),
    openPanel: (panel) => set({ activePanel: panel }),
    closePanel: () => set({ activePanel: null }),
}));

// Keep backward-compat alias
export const useBottomPanelStore = useSidePanelStore;
