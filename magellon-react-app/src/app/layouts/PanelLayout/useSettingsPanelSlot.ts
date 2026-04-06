import { create } from 'zustand';
import React from 'react';

/**
 * Allows any page/feature to register a React node to be rendered
 * in the SidePanelArea when activePanel === 'settings'.
 *
 * Usage:
 *   // In your feature component:
 *   useSettingsPanelSlot.getState().setContent(<MySettingsPanel ... />);
 *
 *   // On unmount:
 *   useSettingsPanelSlot.getState().clearContent();
 */

interface SettingsPanelSlotState {
    content: React.ReactNode | null;
    setContent: (node: React.ReactNode) => void;
    clearContent: () => void;
}

export const useSettingsPanelSlot = create<SettingsPanelSlotState>((set) => ({
    content: null,
    setContent: (node) => set({ content: node }),
    clearContent: () => set({ content: null }),
}));
