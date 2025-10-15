import { useState, useEffect } from 'react';

export const DE_PROPERTIES = {
    HARDWARE_BINNING_X: 'Hardware.Binning.X',
    HARDWARE_BINNING_Y: 'Hardware.Binning.Y',
    HARDWARE_ROI_OFFSET_X: 'Hardware.ROI.Offset.X',
    HARDWARE_ROI_OFFSET_Y: 'Hardware.ROI.Offset.Y',
    HARDWARE_ROI_SIZE_X: 'Hardware.ROI.Size.X',
    HARDWARE_ROI_SIZE_Y: 'Hardware.ROI.Size.Y',
    READOUT_SHUTTER: 'Readout.Shutter',
    READOUT_HARDWARE_HDR: 'Readout.Hardware.HDR',
    FRAMES_PER_SECOND: 'Acquisition.FramesPerSecond',
    FRAME_TIME_NANOSECONDS: 'Acquisition.FrameTime.Nanoseconds',
    EXPOSURE_TIME_SECONDS: 'Acquisition.ExposureTime.Seconds',
    FRAME_COUNT: 'Acquisition.FrameCount',
    IMAGE_PROCESSING_MODE: 'ImageProcessing.Mode',
    IMAGE_PROCESSING_FLATFIELD: 'ImageProcessing.Flatfield',
    IMAGE_PROCESSING_GAIN_MOVIE: 'ImageProcessing.Gain.Movie',
    IMAGE_PROCESSING_GAIN_FINAL: 'ImageProcessing.Gain.Final',
    BINNING_X: 'ImageProcessing.Binning.X',
    BINNING_Y: 'ImageProcessing.Binning.Y',
    BINNING_METHOD: 'ImageProcessing.Binning.Method',
    CROP_OFFSET_X: 'ImageProcessing.Crop.Offset.X',
    CROP_OFFSET_Y: 'ImageProcessing.Crop.Offset.Y',
    CROP_SIZE_X: 'ImageProcessing.Crop.Size.X',
    CROP_SIZE_Y: 'ImageProcessing.Crop.Size.Y',
    AUTOSAVE_DIRECTORY: 'Autosave.Directory',
    AUTOSAVE_FILENAME_SUFFIX: 'Autosave.FilenameSuffix',
    AUTOSAVE_FILE_FORMAT: 'Autosave.FileFormat',
    AUTOSAVE_MOVIE_FORMAT: 'Autosave.MovieFormat',
    AUTOSAVE_FINAL_IMAGE: 'Autosave.FinalImage',
    AUTOSAVE_MOVIE: 'Autosave.Movie',
    AUTOSAVE_MOVIE_SUM_COUNT: 'Autosave.Movie.SumCount',
    PRESET_LIST: 'Preset.List',
    PRESET_CURRENT: 'Preset.Current',
    SYSTEM_STATUS: 'System.Status',
    CAMERA_POSITION_STATUS: 'Camera.Position.Status',
    TEMPERATURE_DETECTOR_STATUS: 'Temperature.Detector.Status',
};

export const useDeCamera = (client: any) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [availableProperties, setAvailableProperties] = useState<string[]>([]);
    const [settings, setSettings] = useState<any>({});
    const [systemStatus, setSystemStatus] = useState<any>(null);

    const setProperty = async (propertyName: string, value: any) => {
        // Mock implementation
        console.log('Setting property:', propertyName, value);
    };

    const refreshProperties = async () => {
        // Mock implementation
        console.log('Refreshing properties');
    };

    const loadPresets = async () => {
        // Mock implementation
        return [];
    };

    const setPreset = async (presetName: string) => {
        // Mock implementation
        console.log('Setting preset:', presetName);
    };

    const debug = () => {
        // Mock implementation
        console.log('Debug info');
    };

    useEffect(() => {
        setIsConnected(true);
    }, []);

    return {
        isConnected,
        isLoading,
        error,
        availableProperties,
        settings,
        systemStatus,
        setProperty,
        refreshProperties,
        loadPresets,
        setPreset,
        debug,
    };
};
