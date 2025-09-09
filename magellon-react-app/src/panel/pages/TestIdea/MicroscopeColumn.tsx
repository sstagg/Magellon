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
        name: 'FEG Gun',
        width: 70,
        height: 40,
        baseColor: '#8B5CF6',
        shape: 'source',
        description: 'Field Emission Gun at 300kV',
        specifications: { voltage: '300kV', emission: 'Cold FEG', material: 'Tungsten' }
      },
      {
        id: 'anode',
        type: 'electrode',
        name: 'Anode',
        width: 90,
        height: 35,
        baseColor: '#F59E0B',
        shape: 'cylinder',
        description: 'Accelerating electrode',
        specifications: { material: 'Tungsten', voltage: '300V' }
      },
      {
        id: 'condenser-1',
        type: 'lens',
        name: 'C1 Lens',
        width: 85,
        height: 35,
        baseColor: '#3B82F6',
        shape: 'lens',
        description: 'First condenser lens',
        specifications: { focalLength: '50mm', current: '2.5A' }
      },
      {
        id: 'condenser-2',
        type: 'lens',
        name: 'C2 Lens',
        width: 85,
        height: 35,
        baseColor: '#3B82F6',
        shape: 'lens',
        description: 'Second condenser lens',
        specifications: { focalLength: '45mm', current: '3.0A' }
      },
      {
        id: 'c2-aperture',
        type: 'aperture',
        name: 'C2 Aperture',
        width: 100,
        height: 25,
        baseColor: '#8B5CF6',
        shape: 'aperture',
        description: 'C2 aperture - 50μm',
        specifications: { size: '50μm', material: 'Molybdenum' }
      },
      {
        id: 'objective-lens',
        type: 'lens',
        name: 'Obj Lens',
        width: 80,
        height: 35,
        baseColor: '#EF4444',
        shape: 'lens',
        description: 'Primary imaging lens',
        specifications: { focalLength: '2.5mm', sphericalAberration: '0.01mm' }
      },
      {
        id: 'obj-aperture',
        type: 'aperture',
        name: 'Obj Aperture',
        width: 95,
        height: 25,
        baseColor: '#A855F7',
        shape: 'aperture',
        description: 'Objective aperture - 100μm',
        specifications: { size: '100μm', material: 'Platinum' }
      },
      {
        id: 'sample-stage',
        type: 'sample',
        name: 'Sample',
        width: 50,
        height: 20,
        baseColor: '#F97316',
        shape: 'cylinder',
        description: 'Cryo specimen holder',
        specifications: { temperature: '-178°C', tiltRange: '±70°' }
      },
      {
        id: 'diffraction-lens',
        type: 'lens',
        name: 'Diff Lens',
        width: 85,
        height: 35,
        baseColor: '#10B981',
        shape: 'lens',
        description: 'Diffraction/intermediate lens',
        specifications: { focalLength: '120mm', magnification: '40x' }
      },
      {
        id: 'projection-1',
        type: 'lens',
        name: 'Proj 1',
        width: 85,
        height: 35,
        baseColor: '#10B981',
        shape: 'lens',
        description: 'First projector lens',
        specifications: { focalLength: '200mm', magnification: '100x' }
      },
      {
        id: 'projection-2',
        type: 'lens',
        name: 'Proj 2',
        width: 85,
        height: 35,
        baseColor: '#10B981',
        shape: 'lens',
        description: 'Second projector lens',
        specifications: { focalLength: '250mm', magnification: '200x' }
      },
      {
        id: 'apollo-camera',
        type: 'camera',
        name: 'Apollo Cam',
        width: 120,
        height: 50,
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
        height: 40,
        baseColor: '#8B5CF6',
        shape: 'source',
        description: 'Cold Field Emission Gun',
        specifications: { emission: 'Cold FEG', brightness: '10^9 A/cm²sr' }
      },
      {
        id: 'condenser-1',
        type: 'lens',
        name: 'C1 Lens',
        width: 85,
        height: 35,
        baseColor: '#3B82F6',
        shape: 'lens',
        description: 'First condenser lens',
        specifications: { focalLength: '50mm', current: '2.8A' }
      },
      {
        id: 'condenser-2',
        type: 'lens',
        name: 'C2 Lens',
        width: 85,
        height: 35,
        baseColor: '#3B82F6',
        shape: 'lens',
        description: 'Second condenser lens',
        specifications: { focalLength: '45mm', current: '3.2A' }
      },
      {
        id: 'scan-coils',
        type: 'coils',
        name: 'Scan Coils',
        width: 90,
        height: 35,
        baseColor: '#06B6D4',
        shape: 'cylinder',
        description: 'STEM scanning coils',
        specifications: { scanRate: '100MHz', deflectionAngle: '25mrad' }
      },
      {
        id: 'objective-lens',
        type: 'lens',
        name: 'Obj Lens',
        width: 80,
        height: 35,
        baseColor: '#EF4444',
        shape: 'lens',
        description: 'Aberration corrected objective',
        specifications: { focalLength: '1.8mm', corrector: 'CEOS' }
      },
      {
        id: 'sample-stage',
        type: 'sample',
        name: 'Sample',
        width: 50,
        height: 20,
        baseColor: '#F97316',
        shape: 'cylinder',
        description: 'High resolution specimen stage',
        specifications: { stability: '0.1Å/min', tiltRange: '±30°' }
      },
      {
        id: 'stem-detector-1',
        type: 'detector',
        name: 'HAADF',
        width: 100,
        height: 40,
        baseColor: '#84CC16',
        shape: 'detector',
        description: 'High-angle annular dark field',
        specifications: { innerAngle: '50mrad', outerAngle: '200mrad' }
      },
      {
        id: 'stem-detector-2',
        type: 'detector',
        name: 'ADF Det',
        width: 95,
        height: 40,
        baseColor: '#22C55E',
        shape: 'detector',
        description: 'Annular dark field detector',
        specifications: { innerAngle: '20mrad', outerAngle: '50mrad' }
      },
      {
        id: 'celeritas-camera',
        type: 'camera',
        name: 'Celeritas',
        width: 115,
        height: 50,
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

// Property Editor Component
const PropertyEditor: React.FC<{
  component: MicroscopeComponent;
  onUpdate: (updatedComponent: MicroscopeComponent) => void;
}> = ({ component, onUpdate }) => {
  const [editedComponent, setEditedComponent] = useState<MicroscopeComponent>(component);

  useEffect(() => {
    setEditedComponent(component);
  }, [component]);

  const handlePropertyChange = (path: string, value: any) => {
    const updated = { ...editedComponent };
    
    if (path.startsWith('specifications.')) {
      const specKey = path.replace('specifications.', '');
      if (!updated.specifications) updated.specifications = {};
      updated.specifications[specKey] = value;
    } else {
      (updated as any)[path] = value;
    }
    
    setEditedComponent(updated);
    onUpdate(updated);
  };

  const addSpecification = () => {
    const key = prompt('Enter specification key:');
    const value = prompt('Enter specification value:');
    if (key && value) {
      handlePropertyChange(`specifications.${key}`, value);
    }
  };

  const removeSpecification = (key: string) => {
    const updated = { ...editedComponent };
    if (updated.specifications) {
      delete updated.specifications[key];
    }
    setEditedComponent(updated);
    onUpdate(updated);
  };

  return (
    <div className="bg-white/10 backdrop-blur-xl rounded-xl p-5 border border-white/20 shadow-xl max-h-96 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Properties</h3>
        <div className="text-xs text-white/60">{component.id}</div>
      </div>
      
      <div className="space-y-3">
        {/* Basic Properties */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-white/80 block mb-1">Name</label>
            <input
              type="text"
              value={editedComponent.name}
              onChange={(e) => handlePropertyChange('name', e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white"
            />
          </div>
          <div>
            <label className="text-xs text-white/80 block mb-1">Type</label>
            <select
              value={editedComponent.type}
              onChange={(e) => handlePropertyChange('type', e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white"
            >
              <option value="source">Source</option>
              <option value="lens">Lens</option>
              <option value="aperture">Aperture</option>
              <option value="detector">Detector</option>
              <option value="camera">Camera</option>
              <option value="sample">Sample</option>
              <option value="electrode">Electrode</option>
              <option value="coils">Coils</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-white/80 block mb-1">Width</label>
            <input
              type="number"
              value={editedComponent.width}
              onChange={(e) => handlePropertyChange('width', parseInt(e.target.value))}
              className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white"
            />
          </div>
          <div>
            <label className="text-xs text-white/80 block mb-1">Height</label>
            <input
              type="number"
              value={editedComponent.height}
              onChange={(e) => handlePropertyChange('height', parseInt(e.target.value))}
              className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-white/80 block mb-1">Color</label>
            <input
              type="color"
              value={editedComponent.baseColor}
              onChange={(e) => handlePropertyChange('baseColor', e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded px-1 py-1 h-8"
            />
          </div>
          <div>
            <label className="text-xs text-white/80 block mb-1">Shape</label>
            <select
              value={editedComponent.shape}
              onChange={(e) => handlePropertyChange('shape', e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white"
            >
              <option value="cylinder">Cylinder</option>
              <option value="lens">Lens</option>
              <option value="aperture">Aperture</option>
              <option value="detector">Detector</option>
              <option value="source">Source</option>
              <option value="camera">Camera</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs text-white/80 block mb-1">Description</label>
          <textarea
            value={editedComponent.description || ''}
            onChange={(e) => handlePropertyChange('description', e.target.value)}
            rows={2}
            className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white resize-none"
          />
        </div>

        {/* Specifications */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-white/80">Specifications</label>
            <button
              onClick={addSpecification}
              className="text-xs bg-blue-500/20 hover:bg-blue-500/30 px-2 py-1 rounded border border-blue-400/30 text-blue-300"
            >
              + Add
            </button>
          </div>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {editedComponent.specifications && Object.entries(editedComponent.specifications).map(([key, value]) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  type="text"
                  value={key}
                  onChange={(e) => {
                    const newSpecs = { ...editedComponent.specifications };
                    delete newSpecs[key];
                    newSpecs[e.target.value] = value;
                    handlePropertyChange('specifications', newSpecs);
                  }}
                  className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white/80"
                  placeholder="Key"
                />
                <input
                  type="text"
                  value={String(value)}
                  onChange={(e) => handlePropertyChange(`specifications.${key}`, e.target.value)}
                  className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white"
                  placeholder="Value"
                />
                <button
                  onClick={() => removeSpecification(key)}
                  className="text-xs text-red-400 hover:text-red-300 px-1"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// Particle component for electron beam
const ElectronParticle: React.FC<{ delay: number }> = ({ delay }) => (
  <motion.div
    className="absolute w-0.5 h-0.5 bg-yellow-300 rounded-full opacity-60"
    initial={{ y: -10, opacity: 0 }}
    animate={{ 
      y: 15, 
      opacity: [0, 0.8, 0.8, 0],
      scale: [0.5, 1, 1, 0.5]
    }}
    transition={{
      duration: 1.2,
      delay,
      repeat: Infinity,
      ease: "linear"
    }}
  />
);

// Compact component renderer with centered labels
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

    const labelStyle = "absolute inset-0 flex items-center justify-center text-white text-xs font-medium text-center px-1 pointer-events-none select-none";

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
            <div className={labelStyle}>
              {component.name}
            </div>
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
              <div className={labelStyle}>
                {component.name}
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-2 h-2 border border-white/40 rounded-full" />
              </div>
            </div>
            <div 
              className="w-2 h-2 border-x border-white/20"
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
            <div className={labelStyle}>
              {component.name}
            </div>
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
              <div className={labelStyle}>
                {component.name}
              </div>
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
            <div className={labelStyle}>
              {component.name}
            </div>
            {/* Camera sensor grid */}
            <div className="absolute inset-2 grid grid-cols-4 grid-rows-4 gap-0.5 opacity-30">
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
            <div className={labelStyle}>
              {component.name}
            </div>
          </div>
        );
    }
  };

  return (
    <motion.div
      className="relative flex flex-col items-center mb-2 cursor-pointer"
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
        
        {/* Selection indicator */}
        <AnimatePresence>
          {isSelected && (
            <motion.div
              className="absolute inset-0 border-2 border-blue-400 rounded-full opacity-80"
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
      
      {/* Electron beam */}
      <div className="relative w-1 h-6 overflow-hidden">
        <div className="absolute left-1/2 transform -translate-x-1/2 w-px h-full bg-gradient-to-b from-yellow-300 via-yellow-400 to-yellow-500 opacity-50" />
        {[...Array(2)].map((_, i) => (
          <ElectronParticle key={i} delay={i * 0.6} />
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

  const handleComponentUpdate = (updatedComponent: MicroscopeComponent) => {
    const updatedComponents = currentConfig.components.map(c => 
      c.id === updatedComponent.id ? updatedComponent : c
    );
    setCurrentConfig({
      ...currentConfig,
      components: updatedComponents
    });
  };

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
      {/* Background particles */}
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
            className="w-80 space-y-4"
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            {/* Configuration Selector */}
            <div className="bg-white/10 backdrop-blur-xl rounded-xl p-5 border border-white/20 shadow-xl">
              <h2 className="text-xl font-semibold text-white mb-4 bg-gradient-to-r from-cyan-400 to-blue-600 bg-clip-text text-transparent">
                Microscope Configuration
              </h2>
              
              <div className="mb-4">
                <label className="text-sm text-white/80 mb-2 block">Select Configuration:</label>
                <select 
                  value={selectedConfig}
                  onChange={(e) => setSelectedConfig(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white backdrop-blur-sm"
                >
                  <option value="cryo-em-setup">Titan Krios with Apollo</option>
                  <option value="stem-setup">JEOL ARM300F STEM</option>
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

              {/* Export Configuration */}
              <button
                onClick={() => {
                  const configJson = JSON.stringify(currentConfig, null, 2);
                  navigator.clipboard.writeText(configJson);
                  alert('Configuration copied to clipboard!');
                }}
                className="w-full bg-green-500/20 hover:bg-green-500/30 px-3 py-2 rounded border border-green-400/30 text-green-300 text-sm"
              >
                Copy Configuration JSON
              </button>
            </div>

            {/* Property Explorer */}
            <AnimatePresence>
              {selectedComponent && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                >
                  <PropertyEditor
                    component={selectedComponent}
                    onUpdate={handleComponentUpdate}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Component List */}
            <div className="bg-white/10 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-xl">
              <h3 className="text-lg font-semibold text-white mb-3">Components</h3>
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {currentConfig.components.map((component, index) => (
                  <div
                    key={component.id}
                    className={`p-2 rounded cursor-pointer transition-colors text-sm ${
                      selectedId === component.id 
                        ? 'bg-blue-500/30 border border-blue-400/50' 
                        : 'bg-white/5 hover:bg-white/10'
                    }`}
                    onClick={() => setSelectedId(selectedId === component.id ? null : component.id)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-white font-medium">{component.name}</span>
                      <span className="text-white/60 text-xs">{component.type}</span>
                    </div>
                    <div className="text-white/50 text-xs mt-1">{component.description}</div>
                  </div>
                ))}
              </div>
            </div>
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