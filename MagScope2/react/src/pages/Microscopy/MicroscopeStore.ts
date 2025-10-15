import { create } from 'zustand';

// Types
interface StagePosition {
    x: number;
    y: number;
    z: number;
    alpha: number;
    beta: number;
}

interface OpticalSettings {
    magnification: number;
    defocus: number;
    spotSize: number;
    intensity: number;
    beamBlank: boolean;
}

interface AcquisitionSettings {
    exposure: number;
    binning: number;
    saveFrames: boolean;
    electronCounting: boolean;
    mode: string;
    frameTime: number;
    frameRate: number;
}

interface MicroscopeStatus {
    connected: boolean;
    model: string;
    highTension: number;
    columnValve: string;
    vacuumStatus: string;
    temperature: number;
    autoloader: string;
    refrigerantLevel: number;
}

interface GridSquare {
    id: string;
    x: number;
    y: number;
    quality: 'good' | 'medium' | 'bad';
    collected: boolean;
    iceThickness: number;
}

interface AtlasData {
    gridSquares: GridSquare[];
    currentPosition: { x: number; y: number };
}

interface AcquisitionHistoryItem {
    id: number;
    timestamp: string;
    settings: AcquisitionSettings;
    thumbnail: string;
    fft: string;
    metadata: {
        pixelSize: number;
        dose: number;
        defocus: number;
        astigmatism: number;
        magnification: number;
        binning: number;
        mode: string;
    };
}

interface AdvancedSettings {
    driftCorrection: boolean;
    autoFocus: boolean;
    autoStigmation: boolean;
    doseProtection: boolean;
    targetDefocus: number;
    defocusRange: number;
    beamTiltCompensation: boolean;
}

interface Preset {
    id: number;
    name: string;
    mag: number;
    defocus: number;
    spot: number;
}

// Store interface
interface MicroscopeStore {
    // Connection states
    isConnected: boolean;
    connectionStatus: 'disconnected' | 'connecting' | 'connected';

    // Microscope states
    microscopeStatus: MicroscopeStatus | null;
    stagePosition: StagePosition;
    opticalSettings: OpticalSettings;

    // Camera states
    acquisitionSettings: AcquisitionSettings;
    isAcquiring: boolean;
    lastImage: string | null;
    lastFFT: string | null;

    // UI states
    activeTab: number;
    showFFT: boolean;
    showHistory: boolean;
    showSettings: boolean;

    // Atlas states
    atlasData: AtlasData | null;
    selectedSquare: GridSquare | null;
    atlasZoom: number;

    // History and settings
    acquisitionHistory: AcquisitionHistoryItem[];
    advancedSettings: AdvancedSettings;

    // Presets
    presets: Preset[];

    // Actions
    setConnectionStatus: (status: 'disconnected' | 'connecting' | 'connected') => void;
    setIsConnected: (connected: boolean) => void;
    setMicroscopeStatus: (status: MicroscopeStatus | null) => void;
    updateStagePosition: (position: Partial<StagePosition>) => void;
    updateOpticalSettings: (settings: Partial<OpticalSettings>) => void;
    updateAcquisitionSettings: (settings: Partial<AcquisitionSettings>) => void;
    setIsAcquiring: (acquiring: boolean) => void;
    setLastImage: (image: string | null) => void;
    setLastFFT: (fft: string | null) => void;
    setActiveTab: (tab: number) => void;
    setShowFFT: (show: boolean) => void;
    setShowHistory: (show: boolean) => void;
    setShowSettings: (show: boolean) => void;
    setAtlasData: (data: AtlasData | null) => void;
    setSelectedSquare: (square: GridSquare | null) => void;
    setAtlasZoom: (zoom: number) => void;
    addToHistory: (item: AcquisitionHistoryItem) => void;
    updateAdvancedSettings: (settings: Partial<AdvancedSettings>) => void;
    applyPreset: (preset: Preset) => void;
}

export const useMicroscopeStore = create<MicroscopeStore>((set, get) => ({
    // Initial states
    isConnected: true,
    connectionStatus: 'connected',
    microscopeStatus: null,
    stagePosition: { x: 12.345, y: -23.456, z: 0.234, alpha: 0.0, beta: 0.0 },
    opticalSettings: {
        magnification: 81000,
        defocus: -2.0,
        spotSize: 3,
        intensity: 0.00045,
        beamBlank: false
    },
    acquisitionSettings: {
        exposure: 1000,
        binning: 1,
        saveFrames: false,
        electronCounting: true,
        mode: 'Counting',
        frameTime: 50,
        frameRate: 40
    },
    isAcquiring: false,
    lastImage: null,
    lastFFT: null,
    activeTab: 0,
    showFFT: false,
    showHistory: false,
    showSettings: false,
    atlasData: null,
    selectedSquare: null,
    atlasZoom: 1,
    acquisitionHistory: [],
    advancedSettings: {
        driftCorrection: true,
        autoFocus: true,
        autoStigmation: false,
        doseProtection: true,
        targetDefocus: -2.0,
        defocusRange: 0.5,
        beamTiltCompensation: true
    },
    presets: [
        { id: 1, name: 'Atlas', mag: 200, defocus: -100, spot: 5 },
        { id: 2, name: 'Square', mag: 2000, defocus: -50, spot: 4 },
        { id: 3, name: 'Hole', mag: 10000, defocus: -10, spot: 3 },
        { id: 4, name: 'Focus', mag: 50000, defocus: -2, spot: 3 },
        { id: 5, name: 'Record', mag: 81000, defocus: -2, spot: 3 }
    ],

    // Actions
    setConnectionStatus: (status) => set({ connectionStatus: status }),
    setIsConnected: (connected) => set({ isConnected: connected }),
    setMicroscopeStatus: (status) => set({ microscopeStatus: status }),

    updateStagePosition: (position) =>
        set((state) => ({
            stagePosition: { ...state.stagePosition, ...position }
        })),

    updateOpticalSettings: (settings) =>
        set((state) => ({
            opticalSettings: { ...state.opticalSettings, ...settings }
        })),

    updateAcquisitionSettings: (settings) =>
        set((state) => ({
            acquisitionSettings: { ...state.acquisitionSettings, ...settings }
        })),

    setIsAcquiring: (acquiring) => set({ isAcquiring: acquiring }),
    setLastImage: (image) => set({ lastImage: image }),
    setLastFFT: (fft) => set({ lastFFT: fft }),
    setActiveTab: (tab) => set({ activeTab: tab }),
    setShowFFT: (show) => set({ showFFT: show }),
    setShowHistory: (show) => set({ showHistory: show }),
    setShowSettings: (show) => set({ showSettings: show }),
    setAtlasData: (data) => set({ atlasData: data }),
    setSelectedSquare: (square) => set({ selectedSquare: square }),
    setAtlasZoom: (zoom) => set({ atlasZoom: zoom }),

    addToHistory: (item) =>
        set((state) => ({
            acquisitionHistory: [item, ...state.acquisitionHistory.slice(0, 19)]
        })),

    updateAdvancedSettings: (settings) =>
        set((state) => ({
            advancedSettings: { ...state.advancedSettings, ...settings }
        })),

    applyPreset: (preset) =>
        set((state) => ({
            opticalSettings: {
                ...state.opticalSettings,
                magnification: preset.mag,
                defocus: preset.defocus,
                spotSize: preset.spot
            }
        }))
}));
