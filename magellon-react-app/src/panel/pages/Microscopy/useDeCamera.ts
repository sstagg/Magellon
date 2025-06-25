import { useState, useEffect, useCallback, useRef } from 'react';

// DE-SDK Property Definitions
export const DE_PROPERTIES = {
    // Hardware Configuration
    HARDWARE_BINNING_X: 'Hardware Binning X',
    HARDWARE_BINNING_Y: 'Hardware Binning Y',
    HARDWARE_ROI_OFFSET_X: 'Hardware ROI - Offset X',
    HARDWARE_ROI_OFFSET_Y: 'Hardware ROI - Offset Y',
    HARDWARE_ROI_SIZE_X: 'Hardware ROI - Size X',
    HARDWARE_ROI_SIZE_Y: 'Hardware ROI - Size Y',
    READOUT_SHUTTER: 'Readout - Shutter',
    READOUT_HARDWARE_HDR: 'Readout - Hardware HDR',

    // Timing & Exposure
    FRAMES_PER_SECOND: 'Frames Per Second',
    FRAME_TIME_NANOSECONDS: 'Frame Time (nanoseconds)',
    EXPOSURE_TIME_SECONDS: 'Exposure Time (seconds)',
    FRAME_COUNT: 'Frame Count',

    // Image Processing
    IMAGE_PROCESSING_MODE: 'Image Processing - Mode',
    IMAGE_PROCESSING_FLATFIELD: 'Image Processing - Flatfield Correction',
    IMAGE_PROCESSING_GAIN_MOVIE: 'Image Processing - Apply Gain on Movie',
    IMAGE_PROCESSING_GAIN_FINAL: 'Image Processing - Apply Gain on Final',

    // Software Processing
    BINNING_X: 'Binning X',
    BINNING_Y: 'Binning Y',
    BINNING_METHOD: 'Binning Method',
    CROP_OFFSET_X: 'Crop Offset X',
    CROP_OFFSET_Y: 'Crop Offset Y',
    CROP_SIZE_X: 'Crop Size X',
    CROP_SIZE_Y: 'Crop Size Y',

    // Autosave
    AUTOSAVE_DIRECTORY: 'Autosave Directory',
    AUTOSAVE_FILENAME_SUFFIX: 'Autosave Filename Suffix',
    AUTOSAVE_FILE_FORMAT: 'Autosave File Format',
    AUTOSAVE_MOVIE_FORMAT: 'Autosave Movie File Format',
    AUTOSAVE_FINAL_IMAGE: 'Autosave Final Image',
    AUTOSAVE_MOVIE: 'Autosave Movie',
    AUTOSAVE_MOVIE_SUM_COUNT: 'Autosave Movie Sum Count',

    // Presets
    PRESET_LIST: 'Preset - List',
    PRESET_CURRENT: 'Preset - Current',

    // System Status
    SYSTEM_STATUS: 'System Status',
    CAMERA_POSITION_STATUS: 'Camera Position Status',
    TEMPERATURE_DETECTOR_STATUS: 'Temperature - Detector Status',

    // Read-only Properties
    IMAGE_SIZE_X: 'Image Size X (pixels)',
    IMAGE_SIZE_Y: 'Image Size Y (pixels)',
    FRAMES_PER_SECOND_MAX: 'Frames Per Second (Max)',
};

// Property validation rules
export const PROPERTY_VALIDATION = {
    [DE_PROPERTIES.HARDWARE_BINNING_X]: { type: 'select', options: [1, 2], default: 1 },
    [DE_PROPERTIES.HARDWARE_BINNING_Y]: { type: 'select', options: [1, 2], default: 1 },
    [DE_PROPERTIES.READOUT_SHUTTER]: { type: 'select', options: ['Global', 'Rolling'], default: 'Rolling' },
    [DE_PROPERTIES.READOUT_HARDWARE_HDR]: { type: 'select', options: ['On', 'Off'], default: 'Off' },
    [DE_PROPERTIES.FRAMES_PER_SECOND]: { type: 'number', min: 0.06, max: 'dynamic', step: 0.01 },
    [DE_PROPERTIES.EXPOSURE_TIME_SECONDS]: { type: 'number', min: 0.001, max: 3600, step: 0.001 },
    [DE_PROPERTIES.FRAME_COUNT]: { type: 'number', min: 1, max: 1000000000, step: 1 },
    [DE_PROPERTIES.IMAGE_PROCESSING_MODE]: {
        type: 'select',
        options: ['Integrating', 'Counting', 'HDR Counting'],
        default: 'Integrating'
    },
    [DE_PROPERTIES.IMAGE_PROCESSING_FLATFIELD]: {
        type: 'select',
        options: ['None', 'Dark', 'Dark and Gain'],
        default: 'Dark and Gain'
    },
    [DE_PROPERTIES.BINNING_X]: {
        type: 'select',
        options: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024],
        default: 1
    },
    [DE_PROPERTIES.BINNING_Y]: {
        type: 'select',
        options: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024],
        default: 1
    },
    [DE_PROPERTIES.BINNING_METHOD]: {
        type: 'select',
        options: ['Average', 'Fourier Crop', 'Sample', 'Sum'],
        default: 'Average'
    },
    [DE_PROPERTIES.AUTOSAVE_FILE_FORMAT]: {
        type: 'select',
        options: ['Auto', 'MRC', 'TIFF', 'TIFF LZW'],
        default: 'Auto'
    },
    [DE_PROPERTIES.AUTOSAVE_MOVIE_FORMAT]: {
        type: 'select',
        options: ['Auto', 'MRC', 'TIFF', 'TIFF LZW', 'DE5', 'HSPY'],
        default: 'Auto'
    },
    [DE_PROPERTIES.AUTOSAVE_FINAL_IMAGE]: { type: 'select', options: ['On', 'Off'], default: 'On' },
    [DE_PROPERTIES.AUTOSAVE_MOVIE]: { type: 'select', options: ['On', 'Off'], default: 'Off' },
    [DE_PROPERTIES.AUTOSAVE_MOVIE_SUM_COUNT]: { type: 'number', min: 1, max: 1000, default: 1 },
};

// Linked properties that update when others change
export const LINKED_PROPERTIES = {
    [DE_PROPERTIES.FRAMES_PER_SECOND]: [DE_PROPERTIES.FRAME_TIME_NANOSECONDS],
    [DE_PROPERTIES.FRAME_TIME_NANOSECONDS]: [DE_PROPERTIES.FRAMES_PER_SECOND],
    [DE_PROPERTIES.EXPOSURE_TIME_SECONDS]: [DE_PROPERTIES.FRAME_COUNT],
    [DE_PROPERTIES.FRAME_COUNT]: [DE_PROPERTIES.EXPOSURE_TIME_SECONDS],
    [DE_PROPERTIES.HARDWARE_BINNING_X]: [DE_PROPERTIES.FRAMES_PER_SECOND_MAX],
    [DE_PROPERTIES.HARDWARE_BINNING_Y]: [DE_PROPERTIES.FRAMES_PER_SECOND_MAX],
    [DE_PROPERTIES.HARDWARE_ROI_SIZE_X]: [DE_PROPERTIES.FRAMES_PER_SECOND_MAX, DE_PROPERTIES.IMAGE_SIZE_X],
    [DE_PROPERTIES.HARDWARE_ROI_SIZE_Y]: [DE_PROPERTIES.FRAMES_PER_SECOND_MAX, DE_PROPERTIES.IMAGE_SIZE_Y],
};

interface DE_SDKClient {
    ListProperties(): Promise<string[]>;
    GetProperty(propertyName: string): Promise<any>;
    SetProperty(propertyName: string, value: any): Promise<boolean>;
    GetErrorDescription(): Promise<string>;
}

interface SystemStatus {
    system: string;
    position: string;
    temperature: string;
}

interface CameraSettings {
    [key: string]: any;
}

export interface UseDE_CameraReturn {
    // Connection state
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;

    // Properties
    availableProperties: string[];
    settings: CameraSettings;
    systemStatus: SystemStatus;

    // Actions
    setProperty: (propertyName: string, value: any) => Promise<void>;
    getProperty: (propertyName: string) => Promise<any>;
    refreshProperties: () => Promise<void>;
    loadPresets: () => Promise<string[]>;
    setPreset: (presetName: string) => Promise<void>;
    validateProperty: (propertyName: string, value: any) => boolean;

    // Utility
    isPropertyAvailable: (propertyName: string) => boolean;
    getPropertyOptions: (propertyName: string) => any[];
    debug: (propertyName?: string) => void;
}

export const useDeCamera = (client?: DE_SDKClient): UseDE_CameraReturn => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [availableProperties, setAvailableProperties] = useState<string[]>([]);
    const [settings, setSettings] = useState<CameraSettings>({});
    const [systemStatus, setSystemStatus] = useState<SystemStatus>({
        system: 'Disconnected',
        position: 'Unknown',
        temperature: 'Unknown'
    });

    const statusPollRef = useRef<NodeJS.Timeout>();

    // Check if property is available
    const isPropertyAvailable = useCallback((propertyName: string): boolean => {
        return availableProperties.includes(propertyName);
    }, [availableProperties]);

    // Validate property value
    const validateProperty = useCallback((propertyName: string, value: any): boolean => {
        const validation = PROPERTY_VALIDATION[propertyName];
        if (!validation) return true;

        switch (validation.type) {
            case 'select':
                return validation.options.includes(value);
            case 'number':
                const numValue = typeof value === 'string' ? parseFloat(value) : value;
                if (isNaN(numValue)) return false;
                if (validation.min !== undefined && numValue < validation.min) return false;
                if (validation.max !== undefined && validation.max !== 'dynamic' && numValue > validation.max) return false;
                return true;
            default:
                return true;
        }
    }, []);

    // Get property options for select inputs
    const getPropertyOptions = useCallback((propertyName: string): any[] => {
        const validation = PROPERTY_VALIDATION[propertyName];
        return validation?.options || [];
    }, []);

    // Load available properties from camera
    const loadAvailableProperties = useCallback(async (): Promise<void> => {
        if (!client) return;

        try {
            setIsLoading(true);
            const properties = await client.ListProperties();
            setAvailableProperties(properties);
            setIsConnected(true);
            setError(null);
        } catch (err) {
            setError(`Failed to load properties: ${err}`);
            setIsConnected(false);
        } finally {
            setIsLoading(false);
        }
    }, [client]);

    // Load current settings for all available properties
    const loadCurrentSettings = useCallback(async (): Promise<void> => {
        if (!client || availableProperties.length === 0) return;

        try {
            setIsLoading(true);
            const currentSettings: CameraSettings = {};

            // Load all available properties
            for (const prop of availableProperties) {
                try {
                    currentSettings[prop] = await client.GetProperty(prop);
                } catch (err) {
                    console.warn(`Failed to get property ${prop}:`, err);
                }
            }

            setSettings(currentSettings);
            setError(null);
        } catch (err) {
            setError(`Failed to load settings: ${err}`);
        } finally {
            setIsLoading(false);
        }
    }, [client, availableProperties]);

    // Set a property value
    const setProperty = useCallback(async (propertyName: string, value: any): Promise<void> => {
        if (!client) {
            throw new Error('Camera client not available');
        }

        if (!isPropertyAvailable(propertyName)) {
            console.warn(`Property ${propertyName} not available for this camera`);
            return;
        }

        if (!validateProperty(propertyName, value)) {
            throw new Error(`Invalid value for ${propertyName}: ${value}`);
        }

        try {
            setIsLoading(true);
            const success = await client.SetProperty(propertyName, value);

            if (success) {
                // Read back the actual value (camera may adjust it)
                const actualValue = await client.GetProperty(propertyName);

                setSettings(prev => ({
                    ...prev,
                    [propertyName]: actualValue
                }));

                // Update linked properties
                await updateLinkedProperties(propertyName);
                setError(null);
            } else {
                const errorDescription = await client.GetErrorDescription();
                throw new Error(`Failed to set ${propertyName}: ${errorDescription}`);
            }
        } catch (err) {
            setError(`Error setting ${propertyName}: ${err}`);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [client, isPropertyAvailable, validateProperty]);

    // Get a property value
    const getProperty = useCallback(async (propertyName: string): Promise<any> => {
        if (!client) {
            throw new Error('Camera client not available');
        }

        if (!isPropertyAvailable(propertyName)) {
            throw new Error(`Property ${propertyName} not available`);
        }

        try {
            const value = await client.GetProperty(propertyName);
            setSettings(prev => ({
                ...prev,
                [propertyName]: value
            }));
            return value;
        } catch (err) {
            setError(`Error getting ${propertyName}: ${err}`);
            throw err;
        }
    }, [client, isPropertyAvailable]);

    // Update linked properties
    const updateLinkedProperties = useCallback(async (changedProperty: string): Promise<void> => {
        if (!client) return;

        const linkedProps = LINKED_PROPERTIES[changedProperty];
        if (linkedProps) {
            const updates: CameraSettings = {};

            for (const prop of linkedProps) {
                if (isPropertyAvailable(prop)) {
                    try {
                        updates[prop] = await client.GetProperty(prop);
                    } catch (err) {
                        console.warn(`Failed to update linked property ${prop}:`, err);
                    }
                }
            }

            setSettings(prev => ({
                ...prev,
                ...updates
            }));
        }
    }, [client, isPropertyAvailable]);

    // Refresh all properties
    const refreshProperties = useCallback(async (): Promise<void> => {
        await loadAvailableProperties();
        await loadCurrentSettings();
    }, [loadAvailableProperties, loadCurrentSettings]);

    // Load presets
    const loadPresets = useCallback(async (): Promise<string[]> => {
        if (!client || !isPropertyAvailable(DE_PROPERTIES.PRESET_LIST)) {
            return [];
        }

        try {
            const presetList = await client.GetProperty(DE_PROPERTIES.PRESET_LIST);
            return typeof presetList === 'string' ? presetList.split(',') : [];
        } catch (err) {
            console.warn('Failed to load presets:', err);
            return [];
        }
    }, [client, isPropertyAvailable]);

    // Set preset
    const setPreset = useCallback(async (presetName: string): Promise<void> => {
        if (!client || !isPropertyAvailable(DE_PROPERTIES.PRESET_CURRENT)) {
            throw new Error('Presets not supported');
        }

        try {
            await client.SetProperty(DE_PROPERTIES.PRESET_CURRENT, presetName);
            // Reload all settings after preset change
            await loadCurrentSettings();
        } catch (err) {
            setError(`Failed to set preset: ${err}`);
            throw err;
        }
    }, [client, isPropertyAvailable, loadCurrentSettings]);

    // System status polling
    const pollSystemStatus = useCallback(async (): Promise<void> => {
        if (!client || !isConnected) return;

        try {
            const statusUpdates: Partial<SystemStatus> = {};

            if (isPropertyAvailable(DE_PROPERTIES.SYSTEM_STATUS)) {
                statusUpdates.system = await client.GetProperty(DE_PROPERTIES.SYSTEM_STATUS);
            }

            if (isPropertyAvailable(DE_PROPERTIES.CAMERA_POSITION_STATUS)) {
                statusUpdates.position = await client.GetProperty(DE_PROPERTIES.CAMERA_POSITION_STATUS);
            }

            if (isPropertyAvailable(DE_PROPERTIES.TEMPERATURE_DETECTOR_STATUS)) {
                statusUpdates.temperature = await client.GetProperty(DE_PROPERTIES.TEMPERATURE_DETECTOR_STATUS);
            }

            setSystemStatus(prev => ({ ...prev, ...statusUpdates }));
        } catch (err) {
            console.warn('Failed to poll system status:', err);
        }
    }, [client, isConnected, isPropertyAvailable]);

    // Debug utility
    const debug = useCallback((propertyName?: string): void => {
        if (propertyName) {
            console.log(`Property: ${propertyName}`);
            console.log(`Available: ${isPropertyAvailable(propertyName)}`);
            console.log(`Current Value: ${settings[propertyName]}`);
            console.log(`Validation:`, PROPERTY_VALIDATION[propertyName]);
        } else {
            console.log('Available Properties:', availableProperties);
            console.log('Current Settings:', settings);
            console.log('System Status:', systemStatus);
        }
    }, [availableProperties, settings, systemStatus, isPropertyAvailable]);

    // Initialize on client change
    useEffect(() => {
        if (client) {
            loadAvailableProperties();
        } else {
            setIsConnected(false);
            setAvailableProperties([]);
            setSettings({});
        }
    }, [client, loadAvailableProperties]);

    // Load settings when properties are available
    useEffect(() => {
        if (availableProperties.length > 0) {
            loadCurrentSettings();
        }
    }, [availableProperties, loadCurrentSettings]);

    // Start status polling when connected
    useEffect(() => {
        if (isConnected && client) {
            pollSystemStatus(); // Initial poll
            statusPollRef.current = setInterval(pollSystemStatus, 1000);

            return () => {
                if (statusPollRef.current) {
                    clearInterval(statusPollRef.current);
                }
            };
        }
    }, [isConnected, client, pollSystemStatus]);

    return {
        // Connection state
        isConnected,
        isLoading,
        error,

        // Properties
        availableProperties,
        settings,
        systemStatus,

        // Actions
        setProperty,
        getProperty,
        refreshProperties,
        loadPresets,
        setPreset,
        validateProperty,

        // Utility
        isPropertyAvailable,
        getPropertyOptions,
        debug,
    };
};