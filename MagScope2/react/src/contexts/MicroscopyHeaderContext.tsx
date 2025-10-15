import React, { createContext, useContext, useState, ReactNode } from 'react';

interface MicroscopyHeaderContextType {
  showHistory: boolean;
  setShowHistory: (show: boolean) => void;
  showMicroscopePanel: boolean;
  setShowMicroscopePanel: (show: boolean) => void;
  showAdvancedSettings: boolean;
  setShowAdvancedSettings: (show: boolean) => void;
  acquisitionHistoryCount: number;
  setAcquisitionHistoryCount: (count: number) => void;
}

const MicroscopyHeaderContext = createContext<MicroscopyHeaderContextType | undefined>(undefined);

export function MicroscopyHeaderProvider({ children }: { children: ReactNode }) {
  const [showHistory, setShowHistory] = useState(false);
  const [showMicroscopePanel, setShowMicroscopePanel] = useState(false);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [acquisitionHistoryCount, setAcquisitionHistoryCount] = useState(0);

  return (
    <MicroscopyHeaderContext.Provider
      value={{
        showHistory,
        setShowHistory,
        showMicroscopePanel,
        setShowMicroscopePanel,
        showAdvancedSettings,
        setShowAdvancedSettings,
        acquisitionHistoryCount,
        setAcquisitionHistoryCount,
      }}
    >
      {children}
    </MicroscopyHeaderContext.Provider>
  );
}

export function useMicroscopyHeader() {
  const context = useContext(MicroscopyHeaderContext);
  if (context === undefined) {
    throw new Error('useMicroscopyHeader must be used within a MicroscopyHeaderProvider');
  }
  return context;
}
