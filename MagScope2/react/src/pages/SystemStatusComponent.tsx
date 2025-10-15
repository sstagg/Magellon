import React, { useState } from 'react';
import {
    Activity,
    Camera,
    Monitor,
    CheckCircle,
    AlertTriangle,
    XCircle,
    Settings,
    Gauge,
    Database,
    Wifi,
    WifiOff,
    ChevronDown,
    ChevronUp,
    Zap,
    Thermometer,
    Droplets,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

// Mock data
const mockSystemStatus = {
    microscope: {
        connected: true,
        model: 'Titan Krios G4',
        highTension: 300000,
        columnValve: 'open',
        vacuumStatus: 'ready',
        temperature: -192.3,
        autoloader: 'ready',
        refrigerantLevel: 85,
        beamCurrent: 150,
        gun: {
            status: 'ready',
            emission: 4.2,
        }
    },
    camera: {
        connected: true,
        model: 'DE-64',
        temperature: -15.2,
        mode: 'Integrating',
        fps: 40,
        binning: '1x1',
        status: 'ready',
        exposure: 1.0,
        frameCount: 40,
    },
    system: {
        dataPath: '/data/acquisitions',
        diskSpace: 75,
        networkStatus: 'connected',
        lastUpdate: new Date(),
    }
};

interface StatusIndicatorProps {
    status: 'ready' | 'warning' | 'error' | 'offline';
    label: string;
    size?: 'sm' | 'default';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status, label, size = 'sm' }) => {
    const getStatusConfig = () => {
        switch (status) {
            case 'ready':
                return { icon: CheckCircle, variant: 'default' as const, className: 'bg-green-500/10 text-green-700 border-green-500/20' };
            case 'warning':
                return { icon: AlertTriangle, variant: 'default' as const, className: 'bg-yellow-500/10 text-yellow-700 border-yellow-500/20' };
            case 'error':
                return { icon: XCircle, variant: 'destructive' as const, className: 'bg-red-500/10 text-red-700 border-red-500/20' };
            case 'offline':
                return { icon: WifiOff, variant: 'secondary' as const, className: 'bg-gray-500/10 text-gray-700 border-gray-500/20' };
            default:
                return { icon: CheckCircle, variant: 'default' as const, className: '' };
        }
    };

    const { icon: Icon, className } = getStatusConfig();
    const iconSize = size === 'sm' ? 14 : 18;

    return (
        <Badge variant="outline" className={cn('gap-1 font-medium', className)}>
            <Icon size={iconSize} />
            {label}
        </Badge>
    );
};

interface MetricItemProps {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    unit?: string;
    color?: string;
    progress?: number;
}

const MetricItem: React.FC<MetricItemProps> = ({
    icon,
    label,
    value,
    unit = '',
    progress
}) => {
    return (
        <div className="flex items-start gap-2">
            <div className="flex-shrink-0 mt-0.5">
                {icon}
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-sm font-semibold flex items-baseline gap-1">
                    {value}
                    {unit && <span className="text-xs text-muted-foreground font-normal">{unit}</span>}
                </div>
                {progress !== undefined && (
                    <Progress
                        value={progress}
                        className="h-1 mt-1"
                    />
                )}
            </div>
        </div>
    );
};

interface SystemStatusComponentProps {
    isConnected?: boolean;
    connectionStatus?: 'connected' | 'connecting' | 'disconnected';
    onConnect?: () => void;
    cameraConnected?: boolean;
    cameraLoading?: boolean;
    onCameraSettings?: () => void;
    defaultExpanded?: boolean;
}

export const SystemStatusComponent: React.FC<SystemStatusComponentProps> = ({
    isConnected = false,
    connectionStatus = 'disconnected',
    onConnect,
    cameraConnected = false,
    cameraLoading = false,
    onCameraSettings,
    defaultExpanded = true
}) => {
    const status = mockSystemStatus;
    const [expanded, setExpanded] = useState(defaultExpanded);

    return (
        <div>
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                    <Activity className="w-6 h-6 text-primary" />
                    <div className="flex flex-col">
                        <h2 className="text-xl font-bold">System Status</h2>
                        <p className="text-xs text-muted-foreground">
                            System operational • All subsystems nominal
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpanded(!expanded)}
                        className="ml-2"
                    >
                        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </Button>
                </div>

                <div className="flex items-center gap-2">
                    <StatusIndicator
                        status={status.microscope.connected ? 'ready' : 'offline'}
                        label="Microscope"
                    />
                    <StatusIndicator
                        status={status.camera.connected ? 'ready' : 'offline'}
                        label="Camera"
                    />
                    <Button variant="ghost" size="icon" className="ml-2">
                        <Settings className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Collapsible Content */}
            {expanded && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        {/* Microscope Section */}
                        <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
                                <div className="flex items-center gap-2 mb-3">
                                    <Monitor className="w-4 h-4 text-primary" />
                                    <h3 className="text-sm font-semibold text-primary">{status.microscope.model}</h3>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <MetricItem
                                        icon={<Zap className="w-3.5 h-3.5 text-primary" />}
                                        label="High Tension"
                                        value={(status.microscope.highTension / 1000).toFixed(0)}
                                        unit="kV"
                                    />
                                    <MetricItem
                                        icon={<Gauge className="w-3.5 h-3.5 text-primary" />}
                                        label="Beam Current"
                                        value={status.microscope.beamCurrent}
                                        unit="pA"
                                    />
                                    <MetricItem
                                        icon={<Thermometer className="w-3.5 h-3.5 text-blue-500" />}
                                        label="Cryo Temp"
                                        value={status.microscope.temperature}
                                        unit="°C"
                                    />
                                    <MetricItem
                                        icon={<Droplets className="w-3.5 h-3.5 text-green-500" />}
                                        label="Refrigerant"
                                        value={status.microscope.refrigerantLevel}
                                        unit="%"
                                        progress={status.microscope.refrigerantLevel}
                                    />
                                </div>
                            </div>

                            {/* Camera Section */}
                            <div className="p-4 rounded-lg bg-secondary/5 border border-secondary/10">
                                <div className="flex items-center gap-2 mb-3">
                                    <Camera className="w-4 h-4 text-secondary-foreground" />
                                    <h3 className="text-sm font-semibold">{status.camera.model}</h3>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <MetricItem
                                        icon={<Settings className="w-3.5 h-3.5" />}
                                        label="Mode"
                                        value={status.camera.mode}
                                    />
                                    <MetricItem
                                        icon={<Activity className="w-3.5 h-3.5" />}
                                        label="Frame Rate"
                                        value={status.camera.fps}
                                        unit="FPS"
                                    />
                                    <MetricItem
                                        icon={<Thermometer className="w-3.5 h-3.5 text-blue-500" />}
                                        label="Detector Temp"
                                        value={status.camera.temperature}
                                        unit="°C"
                                    />
                                    <MetricItem
                                        icon={<Gauge className="w-3.5 h-3.5" />}
                                        label="Exposure"
                                        value={status.camera.exposure}
                                        unit="s"
                                    />
                                </div>
                            </div>

                            {/* System Resources Section */}
                            <div className="p-4 rounded-lg bg-green-500/5 border border-green-500/10">
                                <div className="flex items-center gap-2 mb-3">
                                    <Database className="w-4 h-4 text-green-600" />
                                    <h3 className="text-sm font-semibold text-green-600">System Resources</h3>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <MetricItem
                                        icon={status.system.networkStatus === 'connected' ?
                                            <Wifi className="w-3.5 h-3.5 text-green-500" /> :
                                            <WifiOff className="w-3.5 h-3.5 text-red-500" />}
                                        label="Network"
                                        value={status.system.networkStatus === 'connected' ? 'Connected' : 'Offline'}
                                    />
                                    <MetricItem
                                        icon={<Database className="w-3.5 h-3.5" />}
                                        label="Storage"
                                        value={status.system.diskSpace}
                                        unit="%"
                                        progress={status.system.diskSpace}
                                    />
                                    <MetricItem
                                        icon={<Activity className="w-3.5 h-3.5" />}
                                        label="CPU"
                                        value="75"
                                        unit="%"
                                        progress={75}
                                    />
                                    <MetricItem
                                        icon={<Database className="w-3.5 h-3.5" />}
                                        label="Memory"
                                        value="60"
                                        unit="%"
                                        progress={60}
                                    />
                                </div>
                            </div>
                        </div>
                    </>
                )}

            {/* Quick Actions */}
            <div className="flex justify-end items-center gap-2 mt-4">
                <Button
                    variant={isConnected ? "outline" : "default"}
                    size="sm"
                    onClick={onConnect}
                    disabled={connectionStatus === 'connecting'}
                >
                    <Monitor className="w-4 h-4 mr-2" />
                    {connectionStatus === 'connecting' ? 'Connecting...' : isConnected ? 'Disconnect' : 'Connect'}
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    onClick={onCameraSettings}
                    disabled={!cameraConnected || cameraLoading}
                >
                    <Camera className="w-4 h-4 mr-2" />
                    Camera Settings
                </Button>

                <Badge className="bg-green-500 animate-pulse">Live</Badge>
            </div>
        </div>
    );
};
