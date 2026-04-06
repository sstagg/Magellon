import { create } from 'zustand';

export type SidePanelType = 'jobs' | 'logs' | null;

interface SidePanelState {
    activePanel: SidePanelType;
    panelWidth: number;
    togglePanel: (panel: SidePanelType) => void;
    closePanel: () => void;
}

export const useSidePanelStore = create<SidePanelState>((set) => ({
    activePanel: null,
    panelWidth: 320,
    togglePanel: (panel) => set((state) => ({
        activePanel: state.activePanel === panel ? null : panel,
    })),
    closePanel: () => set({ activePanel: null }),
}));

// Keep backward-compat alias
export const useBottomPanelStore = useSidePanelStore;
