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
export const MICROSCOPE_CONFIGS: Record<string, MicroscopeConfig> = {
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
                specifications: {voltage: '300kV', emission: 'Cold FEG', material: 'Tungsten'}
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
                specifications: {material: 'Tungsten', voltage: '300V'}
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
                specifications: {focalLength: '50mm', current: '2.5A'}
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
                specifications: {focalLength: '45mm', current: '3.0A'}
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
                specifications: {size: '50μm', material: 'Molybdenum'}
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
                specifications: {focalLength: '2.5mm', sphericalAberration: '0.01mm'}
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
                specifications: {size: '100μm', material: 'Platinum'}
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
                specifications: {temperature: '-178°C', tiltRange: '±70°'}
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
                specifications: {focalLength: '120mm', magnification: '40x'}
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
                specifications: {focalLength: '200mm', magnification: '100x'}
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
                specifications: {focalLength: '250mm', magnification: '200x'}
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
                specifications: {emission: 'Cold FEG', brightness: '10^9 A/cm²sr'}
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
                specifications: {focalLength: '50mm', current: '2.8A'}
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
                specifications: {focalLength: '45mm', current: '3.2A'}
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
                specifications: {scanRate: '100MHz', deflectionAngle: '25mrad'}
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
                specifications: {focalLength: '1.8mm', corrector: 'CEOS'}
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
                specifications: {stability: '0.1Å/min', tiltRange: '±30°'}
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
                specifications: {innerAngle: '50mrad', outerAngle: '200mrad'}
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
                specifications: {innerAngle: '20mrad', outerAngle: '50mrad'}
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