import React, { useEffect, useState } from 'react';
import { History, X, Settings as SettingsIcon, Microscope as MicroscopeIcon } from 'lucide-react';
import { Layout, Model, TabNode } from 'flexlayout-react';
import 'flexlayout-react/style/dark.css';

// Import components
import { SystemStatusComponent } from './SystemStatusComponent';
import { GridAtlas } from './Microscopy/GridAtlas';
import { LiveView } from './Microscopy/LiveView';
import { ControlPanel } from './Microscopy/ControlPanel';
import { useMicroscopeStore } from './Microscopy/MicroscopeStore';
import { CameraSettingsDialog } from './Microscopy/CameraSettingsDialog';
import { MicroscopeDetailsPanel } from './Microscopy/MicroscopeDetailsPanel';
import { AdvancedSettingsPanel } from './Microscopy/AdvancedSettingsPanel';
import { useDeCamera, DE_PROPERTIES } from './Microscopy/useDeCamera.ts';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from '@/components/ui/sheet';
import { Alert, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { Zap } from 'lucide-react';

// Enhanced Mock API with camera integration
class MicroscopeAPI {
    connected: boolean;
    callbacks: Record<string, Function[]>;

    constructor() {
        this.connected = false;
        this.callbacks = {};
    }

    connect() {
        this.connected = true;
        setTimeout(() => {
            this.trigger('connected', { status: 'connected' });
        }, 500);
    }

    disconnect() {
        this.connected = false;
        this.trigger('disconnected', { status: 'disconnected' });
    }

    on(event: string, callback: Function) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    trigger(event: string, data: any) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(cb => cb(data));
        }
    }

    async getMicroscopeStatus() {
        return {
            connected: true,
            model: 'Titan Krios G4',
            highTension: 300000,
            columnValve: 'open',
            vacuumStatus: 'ready',
            temperature: -192.3,
            autoloader: 'ready',
            refrigerantLevel: 85,
            cameraConnected: true,
            cameraModel: 'DE-64',
            cameraTemperature: -15.2
        };
    }

    async getAtlasData() {
        const gridSquares = [];
        for (let row = 0; row < 10; row++) {
            for (let col = 0; col < 10; col++) {
                gridSquares.push({
                    id: `${row}-${col}`,
                    x: col * 100,
                    y: row * 100,
                    quality: Math.random() > 0.3 ? (Math.random() > 0.5 ? 'good' : 'medium') : 'bad' as 'good' | 'medium' | 'bad',
                    collected: Math.random() > 0.7,
                    iceThickness: Math.random() * 200 + 50
                });
            }
        }
        return { gridSquares, currentPosition: { x: 450, y: 450 } };
    }
}

// Mock DE-SDK Client
class MockDE_SDKClient {
    private properties: { [key: string]: any } = {
        [DE_PROPERTIES.HARDWARE_BINNING_X]: 1,
        [DE_PROPERTIES.HARDWARE_BINNING_Y]: 1,
        [DE_PROPERTIES.HARDWARE_ROI_OFFSET_X]: 0,
        [DE_PROPERTIES.HARDWARE_ROI_OFFSET_Y]: 0,
        [DE_PROPERTIES.HARDWARE_ROI_SIZE_X]: 4096,
        [DE_PROPERTIES.HARDWARE_ROI_SIZE_Y]: 4096,
        [DE_PROPERTIES.READOUT_SHUTTER]: 'Rolling',
        [DE_PROPERTIES.READOUT_HARDWARE_HDR]: 'Off',
        [DE_PROPERTIES.FRAMES_PER_SECOND]: 40,
        [DE_PROPERTIES.FRAME_TIME_NANOSECONDS]: 25000000,
        [DE_PROPERTIES.EXPOSURE_TIME_SECONDS]: 1.0,
        [DE_PROPERTIES.FRAME_COUNT]: 40,
        [DE_PROPERTIES.IMAGE_PROCESSING_MODE]: 'Integrating',
        [DE_PROPERTIES.IMAGE_PROCESSING_FLATFIELD]: 'Dark and Gain',
        [DE_PROPERTIES.IMAGE_PROCESSING_GAIN_MOVIE]: 'Off',
        [DE_PROPERTIES.IMAGE_PROCESSING_GAIN_FINAL]: 'On',
        [DE_PROPERTIES.BINNING_X]: 1,
        [DE_PROPERTIES.BINNING_Y]: 1,
        [DE_PROPERTIES.BINNING_METHOD]: 'Average',
        [DE_PROPERTIES.CROP_OFFSET_X]: 0,
        [DE_PROPERTIES.CROP_OFFSET_Y]: 0,
        [DE_PROPERTIES.CROP_SIZE_X]: 4096,
        [DE_PROPERTIES.CROP_SIZE_Y]: 4096,
        [DE_PROPERTIES.AUTOSAVE_DIRECTORY]: '/data/acquisitions',
        [DE_PROPERTIES.AUTOSAVE_FILENAME_SUFFIX]: '',
        [DE_PROPERTIES.AUTOSAVE_FILE_FORMAT]: 'Auto',
        [DE_PROPERTIES.AUTOSAVE_MOVIE_FORMAT]: 'Auto',
        [DE_PROPERTIES.AUTOSAVE_FINAL_IMAGE]: 'On',
        [DE_PROPERTIES.AUTOSAVE_MOVIE]: 'Off',
        [DE_PROPERTIES.AUTOSAVE_MOVIE_SUM_COUNT]: 1,
        [DE_PROPERTIES.PRESET_LIST]: 'Default,High Speed,High Quality,Counting Mode,Cryo-EM Standard',
        [DE_PROPERTIES.PRESET_CURRENT]: 'Default',
        [DE_PROPERTIES.SYSTEM_STATUS]: 'Ready',
        [DE_PROPERTIES.CAMERA_POSITION_STATUS]: 'Inserted',
        [DE_PROPERTIES.TEMPERATURE_DETECTOR_STATUS]: '-15.2',
    };

    async ListProperties(): Promise<string[]> {
        await new Promise(resolve => setTimeout(resolve, 100));
        return Object.keys(this.properties);
    }

    async GetProperty(propertyName: string): Promise<any> {
        await new Promise(resolve => setTimeout(resolve, 50));

        if (!(propertyName in this.properties)) {
            throw new Error(`Property ${propertyName} not found`);
        }

        return this.properties[propertyName];
    }

    async SetProperty(propertyName: string, value: any): Promise<boolean> {
        await new Promise(resolve => setTimeout(resolve, 100));

        if (!(propertyName in this.properties)) {
            return false;
        }

        // Simulate hardware adjustments for linked properties
        if (propertyName === DE_PROPERTIES.FRAMES_PER_SECOND) {
            this.properties[DE_PROPERTIES.FRAME_TIME_NANOSECONDS] = Math.round(1000000000 / value);
        } else if (propertyName === DE_PROPERTIES.EXPOSURE_TIME_SECONDS) {
            const fps = this.properties[DE_PROPERTIES.FRAMES_PER_SECOND];
            this.properties[DE_PROPERTIES.FRAME_COUNT] = Math.round(value * fps);
        }

        this.properties[propertyName] = value;
        return true;
    }

    async GetErrorDescription(): Promise<string> {
        return 'No error';
    }
}

// FlexLayout JSON configuration
const flexLayoutJson = {
    global: {
        tabEnableClose: false,
        tabEnableRename: false,
        tabEnableDrag: true,
        tabEnableFloat: true,
        borderBarSize: 30,
        borderEnableAutoHide: false,
    },
    layout: {
        type: "row",
        weight: 100,
        children: [
            {
                type: "tabset",
                weight: 33,
                children: [
                    {
                        type: "tab",
                        name: "Grid Atlas",
                        component: "GridAtlas",
                        config: {}
                    }
                ]
            },
            {
                type: "tabset",
                weight: 33,
                children: [
                    {
                        type: "tab",
                        name: "Live View",
                        component: "LiveView",
                        config: {}
                    }
                ]
            },
            {
                type: "tabset",
                weight: 34,
                children: [
                    {
                        type: "tab",
                        name: "Control Panel",
                        component: "ControlPanel",
                        config: {}
                    }
                ]
            }
        ]
    }
};

const microscopeAPI = new MicroscopeAPI();

export default function MicroscopyPageView() {
    // Camera-related state
    const [showCameraSettings, setShowCameraSettings] = useState(false);
    const [cameraClient] = useState(() => new MockDE_SDKClient());
    const [cameraError, setCameraError] = useState<string | null>(null);

    // FlexLayout model
    const [model] = useState(() => Model.fromJson(flexLayoutJson));

    // Initialize DE Camera hook
    const {
        isConnected: cameraConnected,
        isLoading: cameraLoading,
        error: cameraHookError,
        availableProperties,
        settings: cameraSettings,
        systemStatus: cameraSystemStatus,
        setProperty: setCameraProperty,
        refreshProperties: refreshCameraProperties,
    } = useDeCamera(cameraClient);

    // Get state and actions from microscope store
    const {
        isConnected,
        connectionStatus,
        setConnectionStatus,
        setIsConnected,
        setMicroscopeStatus,
        setAtlasData,
        acquisitionHistory,
        showHistory,
        setShowHistory,
        showSettings,
        setShowSettings
    } = useMicroscopeStore();

    // Additional drawer states for new panels
    const [showMicroscopePanel, setShowMicroscopePanel] = useState(false);
    const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

    // Initialize connection and API listeners
    useEffect(() => {
        microscopeAPI.on('connected', () => {
            setIsConnected(true);
            setConnectionStatus('connected');
            updateAllStatus();
        });

        microscopeAPI.on('disconnected', () => {
            setIsConnected(false);
            setConnectionStatus('disconnected');
        });
    }, [setIsConnected, setConnectionStatus]);

    // Handle camera errors
    useEffect(() => {
        if (cameraHookError) {
            setCameraError(cameraHookError);
        }
    }, [cameraHookError]);

    const updateAllStatus = async () => {
        try {
            const [microscope, atlas] = await Promise.all([
                microscopeAPI.getMicroscopeStatus(),
                microscopeAPI.getAtlasData()
            ]);
            setMicroscopeStatus(microscope as any);
            setAtlasData(atlas);
        } catch (error) {
            console.error('Failed to update status:', error);
        }
    };

    const handleConnect = () => {
        if (!isConnected) {
            setConnectionStatus('connecting');
            microscopeAPI.connect();
        } else {
            microscopeAPI.disconnect();
        }
    };

    // Handle camera property changes
    const handleCameraPropertyChange = async (propertyName: string, value: any) => {
        try {
            await setCameraProperty(propertyName, value);
            console.log(`Successfully set ${propertyName} to ${value}`);
            setCameraError(null);
        } catch (err) {
            const errorMsg = `Failed to set ${propertyName}: ${err}`;
            console.error(errorMsg);
            setCameraError(errorMsg);
        }
    };

    // FlexLayout factory function for rendering components
    const factory = (node: TabNode) => {
        const component = node.getComponent();

        switch (component) {
            case "GridAtlas":
                return <GridAtlas />;
            case "LiveView":
                return <LiveView />;
            case "ControlPanel":
                return <ControlPanel />;
            default:
                return <div>Component {component} not found</div>;
        }
    };

    return (
        <div className="fixed inset-0 top-16 bg-background flex flex-col overflow-hidden">
            {/* Fixed Header Section */}
            <div className="flex-shrink-0 p-3 md:p-6 pb-2 md:pb-4 border-b bg-background">
                {/* Header */}
                <div className="mb-4 flex justify-between items-center">
                    <div>
                        <h1 className="text-2xl md:text-4xl font-bold flex items-center gap-2">
                            <Zap className="w-6 h-6 md:w-8 h-8 text-primary" />
                            Microscope Control System
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            Advanced control interface for Titan Krios & Direct Electron cameras
                        </p>
                    </div>

                    <div className="flex gap-2">
                        <Button variant="ghost" size="icon" onClick={() => setShowHistory(true)} title="Acquisition History">
                            <Badge variant="secondary" className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs">
                                {acquisitionHistory.length}
                            </Badge>
                            <History className="w-5 h-5" />
                        </Button>

                        <Button variant="ghost" size="icon" onClick={() => setShowMicroscopePanel(true)} title="Microscope Details">
                            <MicroscopeIcon className="w-5 h-5" />
                        </Button>

                        <Button variant="ghost" size="icon" onClick={() => setShowAdvancedSettings(true)} title="Advanced Settings">
                            <SettingsIcon className="w-5 h-5" />
                        </Button>
                    </div>
                </div>

                {/* Error Handling */}
                {cameraError && (
                    <Alert variant="destructive" className="mb-4">
                        <AlertTitle>Camera Error</AlertTitle>
                        <p className="text-sm">{cameraError}</p>
                        <Button variant="ghost" size="sm" className="absolute top-2 right-2" onClick={() => setCameraError(null)}>
                            <X className="w-4 h-4" />
                        </Button>
                    </Alert>
                )}

                {/* System Status */}
                <SystemStatusComponent
                    isConnected={isConnected}
                    connectionStatus={connectionStatus}
                    onConnect={handleConnect}
                    cameraConnected={cameraConnected}
                    cameraLoading={cameraLoading}
                    onCameraSettings={() => setShowCameraSettings(true)}
                />
            </div>

            {/* FlexLayout Container - Uses remaining space */}
            <div className="flex-1 min-h-0 relative">
                <Layout
                    model={model}
                    factory={factory}
                />
            </div>

            {/* Camera Settings Dialog */}
            <CameraSettingsDialog
                open={showCameraSettings}
                onClose={() => setShowCameraSettings(false)}
                cameraSettings={cameraSettings}
                updateCameraSettings={() => {}}
                acquisitionSettings={cameraSettings}
                updateAcquisitionSettings={() => {}}
                availableProperties={availableProperties}
                systemStatus={cameraSystemStatus}
                onPropertyChange={handleCameraPropertyChange}
            />

            {/* Acquisition History Sheet */}
            <Sheet open={showHistory} onOpenChange={setShowHistory}>
                <SheetContent className="w-full sm:w-[400px]">
                    <SheetHeader>
                        <SheetTitle>Acquisition History</SheetTitle>
                    </SheetHeader>

                    <div className="mt-4">
                        {acquisitionHistory.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                                <p>No acquisitions yet</p>
                                <p className="text-sm">Start acquiring images to see them here</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {acquisitionHistory.map(item => (
                                    <div key={item.id} className="border rounded p-2 flex gap-2">
                                        <img
                                            src={item.thumbnail}
                                            alt="Thumbnail"
                                            className="w-16 h-16 object-cover rounded"
                                        />
                                        <div className="flex-1 text-sm">
                                            <div className="font-medium">
                                                {new Date(item.timestamp).toLocaleTimeString()}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {item.settings.exposure}ms • {item.settings.binning}x{item.settings.binning}
                                                {item.settings.electronCounting && ' • Counting'}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                Defocus: {item.metadata.defocus?.toFixed(1)}μm •
                                                Dose: {item.metadata.dose?.toFixed(1)} e⁻/Å²
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </SheetContent>
            </Sheet>

            {/* Microscope Details Sheet */}
            <Sheet open={showMicroscopePanel} onOpenChange={setShowMicroscopePanel}>
                <SheetContent className="w-full sm:w-[600px] overflow-y-auto">
                    <SheetHeader>
                        <SheetTitle>Microscope Details</SheetTitle>
                    </SheetHeader>

                    <div className="mt-4">
                        <MicroscopeDetailsPanel />
                    </div>
                </SheetContent>
            </Sheet>

            {/* Advanced Settings Sheet */}
            <Sheet open={showAdvancedSettings} onOpenChange={setShowAdvancedSettings}>
                <SheetContent className="w-full sm:w-[700px] overflow-y-auto">
                    <SheetHeader>
                        <SheetTitle>Advanced Settings</SheetTitle>
                    </SheetHeader>

                    <div className="mt-4">
                        <AdvancedSettingsPanel
                            cameraConnected={cameraConnected}
                            cameraLoading={cameraLoading}
                            availableProperties={availableProperties}
                            onRefreshCamera={refreshCameraProperties}
                            onOpenCameraSettings={() => setShowCameraSettings(true)}
                        />
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    );
}
