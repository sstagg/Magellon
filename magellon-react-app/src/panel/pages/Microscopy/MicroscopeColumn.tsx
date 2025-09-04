import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Define the microscope component types
export interface MicroscopeComponent {
    id: string;
    type: string;
    name: string;
    width: number;
    height: number;
    baseColor: string;
    shape: 'cylinder' | 'lens' | 'aperture' | 'detector' | 'source' | 'camera';
    description?: string;
    specifications?: Record<string, any>;
}

export interface MicroscopeConfig {
    name: string;
    voltage: string;
    manufacturer: string;
    components: MicroscopeComponent[];
}

// Example JSON configurations for different microscope setups
const MICROSCOPE_CONFIGS: Record<string, MicroscopeConfig> = {
    'cryo-em-setup': {
        name: 'Titan Krios with Apollo Camera',
        voltage: '300kV',
        manufacturer: 'ThermoFisher / Direct Electron',
        components: [
            {
                id: 'electron-gun',
                type: 'source',
                name: 'FEG Electron Gun',
                width: 70,
                height: 25,
                baseColor: '#8B5CF6',
                shape: 'source',
                description: 'Field Emission Gun at 300kV',
                specifications: { voltage: '300kV', emission: 'Cold FEG' }
            },
            {
                id: 'anode',
                type: 'electrode',
                name: 'Anode',
                width: 90,
                height: 20,
                baseColor: '#F59E0B',
                shape: 'cylinder',
                description: 'Accelerating electrode',
                specifications: { material: 'Tungsten' }
            },
            {
                id: 'condenser-1',
                type: 'lens',
                name: 'C1 Lens',
                width: 85,
                height: 18,
                baseColor: '#3B82F6',
                shape: 'lens',
                description: 'First condenser lens'
            },
            {
                id: 'condenser-2',
                type: 'lens',
                name: 'C2 Lens',
                width: 85,
                height: 18,
                baseColor: '#3B82F6',
                shape: 'lens',
                description: 'Second condenser lens'
            },
            {
                id: 'c2-aperture',
                type: 'aperture',
                name: 'C2 Aperture',
                width: 100,
                height: 15,
                baseColor: '#8B5CF6',
                shape: 'aperture',
                description: 'C2 aperture - 50μm',
                specifications: { size: '50μm' }
            },
            {
                id: 'objective-lens',
                type: 'lens',
                name: 'Objective Lens',
                width: 80,
                height: 18,
                baseColor: '#EF4444',
                shape: 'lens',
                description: 'Primary imaging lens'
            },
            {
                id: 'obj-aperture',
                type: 'aperture',
                name: 'Objective Aperture',
                width: 95,
                height: 12,
                baseColor: '#A855F7',
                shape: 'aperture',
                description: 'Objective aperture - 100μm',
                specifications: { size: '100μm' }
            },
            {
                id: 'sample-stage',
                type: 'sample',
                name: 'Sample',
                width: 50,
                height: 10,
                baseColor: '#F97316',
                shape: 'cylinder',
                description: 'Cryo specimen holder'
            },
            {
                id: 'diffraction-lens',
                type: 'lens',
                name: 'Diffraction Lens',
                width: 85,
                height: 18,
                baseColor: '#10B981',
                shape: 'lens',
                description: 'Diffraction/intermediate lens'
            },
            {
                id: 'projection-1',
                type: 'lens',
                name: 'Projector 1',
                width: 85,
                height: 18,
                baseColor: '#10B981',
                shape: 'lens',
                description: 'First projector lens'
            },
            {
                id: 'projection-2',
                type: 'lens',
                name: 'Projector 2',
                width: 85,
                height: 18,
                baseColor: '#10B981',
                shape: 'lens',
                description: 'Second projector lens'
            },
            {
                id: 'apollo-camera',
                type: 'camera',
                name: 'DE Apollo Camera',
                width: 120,
                height: 35,
                baseColor: '#374151',
                shape: 'camera',
                description: 'Event-based direct detection camera',
                specifications: {
                    resolution: '4k × 4k',
                    pixelSize: '8μm',
                    frameRate: '60fps',
                    countingMode: 'Hardware electron counting',
                    manufacturer: 'Direct Electron'
                }
            }
        ]
    },
    'stem-setup': {
        name: 'JEOL ARM300F with Multiple Detectors',
        voltage: '300kV',
        manufacturer: 'JEOL',
        components: [
            {
                id: 'electron-gun',
                type: 'source',
                name: 'CFEG Gun',
                width: 70,
                height: 25,
                baseColor: '#8B5CF6',
                shape: 'source',
                description: 'Cold Field Emission Gun'
            },
            {
                id: 'condenser-1',
                type: 'lens',
                name: 'C1 Lens',
                width: 85,
                height: 18,
                baseColor: '#3B82F6',
                shape: 'lens',
                description: 'First condenser lens'
            },
            {
                id: 'condenser-2',
                type: 'lens',
                name: 'C2 Lens',
                width: 85,
                height: 18,
                baseColor: '#3B82F6',
                shape: 'lens',
                description: 'Second condenser lens'
            },
            {
                id: 'scan-coils',
                type: 'coils',
                name: 'Scan Coils',
                width: 90,
                height: 20,
                baseColor: '#06B6D4',
                shape: 'cylinder',
                description: 'STEM scanning coils'
            },
            {
                id: 'objective-lens',
                type: 'lens',
                name: 'Objective Lens',
                width: 80,
                height: 18,
                baseColor: '#EF4444',
                shape: 'lens',
                description: 'Aberration corrected objective'
            },
            {
                id: 'sample-stage',
                type: 'sample',
                name: 'Sample',
                width: 50,
                height: 10,
                baseColor: '#F97316',
                shape: 'cylinder',
                description: 'High resolution specimen stage'
            },
            {
                id: 'stem-detector-1',
                type: 'detector',
                name: 'HAADF Detector',
                width: 100,
                height: 25,
                baseColor: '#84CC16',
                shape: 'detector',
                description: 'High-angle annular dark field'
            },
            {
                id: 'stem-detector-2',
                type: 'detector',
                name: 'ADF Detector',
                width: 95,
                height: 25,
                baseColor: '#22C55E',
                shape: 'detector',
                description: 'Annular dark field detector'
            },
            {
                id: 'celeritas-camera',
                type: 'camera',
                name: 'DE Celeritas',
                width: 115,
                height: 35,
                baseColor: '#374151',
                shape: 'camera',
                description: '4D-STEM direct detection camera',
                specifications: {
                    resolution: '4k × 4k',
                    frameRate: '>2000fps',
                    application: '4D-STEM, ptychography',
                    manufacturer: 'Direct Electron'
                }
            }
        ]
    }
};

// Particle component for electron beam (more subtle)
const ElectronParticle: React.FC<{ delay: number }> = ({ delay }) => (
    <motion.div
        className="absolute w-0.5 h-0.5 bg-yellow-300 rounded-full opacity-60"
        initial={{ y: -20, opacity: 0 }}
        animate={{
            y: 20,
            opacity: [0, 0.8, 0.8, 0],
            scale: [0.5, 1, 1, 0.5]
        }}
        transition={{
            duration: 1.5,
            delay,
            repeat: Infinity,
            ease: "linear"
        }}
    />
);

// Compact component renderer with subtle animations
const MicroscopeComponentRenderer: React.FC<{
    component: MicroscopeComponent;
    isHovered: boolean;
    isSelected: boolean;
    onHover: () => void;
    onLeave: () => void;
    onSelect: () => void;
    index: number;
}> = ({ component, isHovered, isSelected, onHover, onLeave, onSelect, index }) => {

    const renderShape = () => {
        const baseStyle = {
            background: `linear-gradient(135deg, ${component.baseColor}, ${component.baseColor}dd)`,
        };

        switch (component.shape) {
            case 'source':
                return (
                    <div
                        className="relative rounded-t-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 15px ${component.baseColor}60` : `0 0 8px ${component.baseColor}40`
                        }}
                    >
                        <div className="absolute inset-1 bg-gradient-to-br from-white/20 to-transparent rounded-t-full" />
                        <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-4 h-1 bg-gradient-to-b from-yellow-300 to-yellow-500" />
                    </div>
                );

            case 'lens':
                return (
                    <div className="flex flex-col items-center">
                        <div
                            className="relative rounded-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                            style={{
                                ...baseStyle,
                                width: component.width,
                                height: component.height,
                                boxShadow: isHovered ? `0 0 12px ${component.baseColor}50` : `0 0 6px ${component.baseColor}30`
                            }}
                        >
                            <div className="absolute inset-1 border border-white/10 rounded-full" />
                            <div className="absolute inset-0 bg-gradient-radial from-white/20 via-transparent to-transparent rounded-full" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="w-2 h-2 border border-white/40 rounded-full" />
                            </div>
                        </div>
                        <div
                            className="w-2 h-3 border-x border-white/20"
                            style={{ background: `linear-gradient(to bottom, ${component.baseColor}, ${component.baseColor}aa)` }}
                        />
                    </div>
                );

            case 'aperture':
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 10px ${component.baseColor}40` : `0 0 5px ${component.baseColor}20`
                        }}
                    >
                        <div className="absolute inset-2 bg-black/50 rounded border border-white/10" />
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-1.5 h-1.5 border border-white/60 rounded-full bg-black/20" />
                        </div>
                    </div>
                );

            case 'detector':
                return (
                    <div className="flex items-center">
                        <div
                            className="relative rounded-r-full border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                            style={{
                                ...baseStyle,
                                width: component.width,
                                height: component.height,
                                boxShadow: isHovered ? `0 0 12px ${component.baseColor}50` : `0 0 6px ${component.baseColor}30`
                            }}
                        >
                            <div className="absolute inset-1 bg-gradient-to-l from-white/20 to-transparent rounded-r-full" />
                            <div className="absolute right-1 top-1/2 transform -translate-y-1/2 w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                            <div className="absolute left-2 top-1/2 transform -translate-y-1/2 w-0.5 h-0.5 bg-red-400 rounded-full" />
                        </div>
                    </div>
                );

            case 'camera':
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 15px ${component.baseColor}60` : `0 0 8px ${component.baseColor}40`
                        }}
                    >
                        <div className="absolute inset-1 bg-gradient-to-br from-white/20 to-transparent rounded" />
                        {/* Camera sensor grid */}
                        <div className="absolute inset-2 grid grid-cols-4 grid-rows-4 gap-0.5">
                            {[...Array(16)].map((_, i) => (
                                <div
                                    key={i}
                                    className="bg-blue-400/30 rounded-sm"
                                    style={{
                                        animationDelay: `${i * 0.1}s`,
                                        animation: isHovered ? 'pulse 2s infinite' : 'none'
                                    }}
                                />
                            ))}
                        </div>
                        {/* Status indicator */}
                        <div className="absolute top-1 right-1 w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                    </div>
                );

            default:
                return (
                    <div
                        className="relative rounded border border-white/30 backdrop-blur-sm shadow-lg overflow-hidden"
                        style={{
                            ...baseStyle,
                            width: component.width,
                            height: component.height,
                            boxShadow: isHovered ? `0 0 10px ${component.baseColor}40` : `0 0 5px ${component.baseColor}20`
                        }}
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent rounded" />
                    </div>
                );
        }
    };

    return (
        <motion.div
            className="relative flex flex-col items-center mb-3 cursor-pointer"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={{ scale: 1.02 }}
            onMouseEnter={onHover}
            onMouseLeave={onLeave}
            onClick={onSelect}
        >
            <div className="relative">
                {renderShape()}

                {/* Subtle selection indicator */}
                <AnimatePresence>
                    {isSelected && (
                        <motion.div
                            className="absolute inset-0 border border-blue-400 rounded-full opacity-80"
                            style={{
                                width: component.width + 8,
                                height: component.height + 8,
                                left: -4,
                                top: -4
                            }}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 0.8 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        />
                    )}
                </AnimatePresence>
            </div>

            {/* Compact component label */}
            <div className="mt-1 text-xs font-medium text-white/80 text-center px-1 py-0.5 bg-black/10 rounded backdrop-blur-sm">
                {component.name}
            </div>

            {/* Compact electron beam */}
            <div className="relative w-1 h-8 overflow-hidden">
                <div className="absolute left-1/2 transform -translate-x-1/2 w-px h-full bg-gradient-to-b from-yellow-300 via-yellow-400 to-yellow-500 opacity-50" />
                {[...Array(2)].map((_, i) => (
                    <ElectronParticle key={i} delay={i * 0.8} />
                ))}
            </div>
        </motion.div>
    );
};

// Main microscope column component
const MicroscopeColumn: React.FC = () => {
    const [selectedConfig, setSelectedConfig] = useState<string>('cryo-em-setup');
    const [currentConfig, setCurrentConfig] = useState<MicroscopeConfig>(MICROSCOPE_CONFIGS[selectedConfig]);
    const [hoveredId, setHoveredId] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    useEffect(() => {
        setCurrentConfig(MICROSCOPE_CONFIGS[selectedConfig]);
        setSelectedId(null);
        setHoveredId(null);
    }, [selectedConfig]);

    const selectedComponent = selectedId ? currentConfig.components.find(c => c.id === selectedId) : null;

    // Function to load JSON configuration (placeholder for real implementation)
    const loadConfigFromJSON = (jsonString: string) => {
        try {
            const config: MicroscopeConfig = JSON.parse(jsonString);
            setCurrentConfig(config);
            setSelectedId(null);
            setHoveredId(null);
        } catch (error) {
            console.error('Invalid JSON configuration:', error);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6 relative overflow-hidden">
            {/* Subtle background particles */}
            <div className="absolute inset-0 overflow-hidden">
                {[...Array(30)].map((_, i) => (
                    <motion.div
                        key={i}
                        className="absolute w-0.5 h-0.5 bg-white/10 rounded-full"
                        style={{
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                        }}
                        animate={{
                            y: [0, -10, 0],
                            opacity: [0.1, 0.3, 0.1],
                        }}
                        transition={{
                            duration: 4 + Math.random() * 2,
                            repeat: Infinity,
                            delay: Math.random() * 2,
                        }}
                    />
                ))}
            </div>

            <div className="max-w-7xl mx-auto relative z-10">
                <motion.h1
                    className="text-3xl font-bold text-white mb-6 text-center bg-gradient-to-r from-blue-400 to-purple-600 bg-clip-text text-transparent"
                    initial={{ opacity: 0, y: -30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    {currentConfig.name}
                </motion.h1>

                <div className="flex gap-6">
                    {/* Configuration Panel */}
                    <motion.div
                        className="w-80 bg-white/10 backdrop-blur-xl rounded-xl p-5 border border-white/20 shadow-xl"
                        initial={{ opacity: 0, x: -50 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                    >
                        <h2 className="text-xl font-semibold text-white mb-4 bg-gradient-to-r from-cyan-400 to-blue-600 bg-clip-text text-transparent">
                            Microscope Configuration
                        </h2>

                        {/* Configuration Selector */}
                        <div className="mb-4">
                            <label className="text-sm text-white/80 mb-2 block">Select Configuration:</label>
                            <select
                                value={selectedConfig}
                                onChange={(e) => setSelectedConfig(e.target.value)}
                                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white backdrop-blur-sm"
                            >
                                <option value="jeol-3200fs">JEOL JEM-3200FS</option>
                                <option value="titan-krios-k3">Titan Krios with K3</option>
                            </select>
                        </div>

                        {/* Microscope Info */}
                        <div className="bg-white/5 rounded-lg p-3 mb-4">
                            <div className="text-sm text-white/90 mb-1">
                                <strong>Voltage:</strong> {currentConfig.voltage}
                            </div>
                            <div className="text-sm text-white/90 mb-1">
                                <strong>Manufacturer:</strong> {currentConfig.manufacturer}
                            </div>
                            <div className="text-sm text-white/90">
                                <strong>Components:</strong> {currentConfig.components.length}
                            </div>
                        </div>

                        {/* JSON Configuration Area */}
                        <div className="mb-4">
                            <label className="text-sm text-white/80 mb-2 block">Load JSON Configuration:</label>
                            <textarea
                                placeholder="Paste JSON configuration here..."
                                rows={4}
                                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white backdrop-blur-sm text-xs placeholder-white/50"
                                onChange={(e) => {
                                    if (e.target.value.trim()) {
                                        loadConfigFromJSON(e.target.value);
                                    }
                                }}
                            />
                        </div>

                        {/* Selected Component Details */}
                        <AnimatePresence>
                            {selectedComponent && (
                                <motion.div
                                    className="bg-gradient-to-r from-blue-500/20 to-purple-600/20 backdrop-blur-sm rounded-lg p-4 border border-blue-400/30"
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <h3 className="text-white font-semibold mb-2">Selected Component</h3>
                                    <div className="space-y-1 text-sm">
                                        <div className="text-white/90 font-medium">{selectedComponent.name}</div>
                                        <div className="text-blue-300">Type: {selectedComponent.type}</div>
                                        <div className="text-white/70 text-xs">{selectedComponent.description}</div>
                                        {selectedComponent.specifications && (
                                            <div className="mt-2 p-2 bg-white/10 rounded text-xs">
                                                {Object.entries(selectedComponent.specifications).map(([key, value]) => (
                                                    <div key={key} className="text-white/80">
                                                        <strong>{key}:</strong> {value}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>

                    {/* Microscope Column */}
                    <motion.div
                        className="flex-1 flex flex-col items-center bg-white/10 backdrop-blur-xl rounded-xl p-6 border border-white/20 shadow-xl relative"
                        initial={{ opacity: 0, y: 50 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.4 }}
                    >
                        {/* Vacuum chamber visualization */}
                        <div className="absolute inset-3 bg-gradient-to-b from-blue-900/5 via-purple-900/5 to-blue-900/5 rounded-lg border border-cyan-400/10 backdrop-blur-sm" />

                        <div className="relative z-10 flex flex-col items-center py-6 max-h-[700px] overflow-y-auto custom-scrollbar">
                            <AnimatePresence>
                                {currentConfig.components.map((component, index) => (
                                    <MicroscopeComponentRenderer
                                        key={component.id}
                                        component={component}
                                        isHovered={hoveredId === component.id}
                                        isSelected={selectedId === component.id}
                                        onHover={() => setHoveredId(component.id)}
                                        onLeave={() => setHoveredId(null)}
                                        onSelect={() => setSelectedId(selectedId === component.id ? null : component.id)}
                                        index={index}
                                    />
                                ))}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                </div>
            </div>

            {/* Custom scrollbar styles */}
            <style jsx>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 3px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 3px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: rgba(255, 255, 255, 0.5);
                }
                .bg-gradient-radial {
                    background: radial-gradient(circle, var(--tw-gradient-stops));
                }
            `}</style>
        </div>
    );
};

export default MicroscopeColumn;