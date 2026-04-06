import React, { useState, useEffect, useCallback } from 'react';
import { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';
import ImageInfoDto from '../../../entities/image/types.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import { useJobStore } from '../../../app/layouts/PanelLayout/useJobStore.ts';

export interface Point {
    x: number;
    y: number;
    id?: string;
    confidence?: number;
    type?: 'manual' | 'auto' | 'suggested';
    class?: string;
    timestamp?: number;
}

export interface ParticleClass {
    id: string;
    name: string;
    color: string;
    count: number;
    visible: boolean;
    icon?: React.ReactNode;
}

export type Tool = 'add' | 'remove' | 'select' | 'move' | 'box' | 'auto' | 'brush' | 'pan';
export type ViewMode = 'normal' | 'overlay' | 'heatmap' | 'comparison';

interface UseParticleOperationsParams {
    selectedParticlePicking: ParticlePickingDto | null;
    handleIppUpdate: (ipp: ParticlePickingDto) => void;
    selectedImage: ImageInfoDto | null;
    particleClasses: ParticleClass[];
    setParticleClasses: React.Dispatch<React.SetStateAction<ParticleClass[]>>;
    autoPickingThreshold: number;
    particleRadius: number;
    templatePaths: string[];
    imagePixelSize: number;
    templatePixelSize: number;
    diameterAngstrom: number;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
}

export function useParticleOperations({
    selectedParticlePicking,
    handleIppUpdate,
    selectedImage,
    particleClasses,
    setParticleClasses,
    autoPickingThreshold,
    particleRadius,
    templatePaths,
    imagePixelSize,
    templatePixelSize,
    diameterAngstrom,
    showSnackbar,
}: UseParticleOperationsParams) {
    const [particles, setParticles] = useState<Point[]>([]);
    const [selectedParticles, setSelectedParticles] = useState<Set<string>>(new Set());
    const [history, setHistory] = useState<Point[][]>([[]]);
    const [historyIndex, setHistoryIndex] = useState(0);
    const [copiedParticles, setCopiedParticles] = useState<Point[]>([]);
    const [isAutoPickingRunning, setIsAutoPickingRunning] = useState(false);
    const [autoPickingProgress, setAutoPickingProgress] = useState(0);

    const [stats, setStats] = useState({
        total: 0,
        manual: 0,
        auto: 0,
        avgConfidence: 0,
        particlesPerClass: {} as Record<string, number>
    });

    const updateStats = useCallback((particleList: Point[]) => {
        const manual = particleList.filter(p => p.type === 'manual').length;
        const auto = particleList.filter(p => p.type === 'auto').length;
        const avgConfidence = particleList.length > 0
            ? particleList.reduce((sum, p) => sum + (p.confidence || 1), 0) / particleList.length
            : 0;

        const particlesPerClass: Record<string, number> = {};
        particleClasses.forEach(cls => {
            particlesPerClass[cls.id] = particleList.filter(p => (p.class || '1') === cls.id).length;
        });

        setStats({
            total: particleList.length,
            manual,
            auto,
            avgConfidence,
            particlesPerClass
        });

        setParticleClasses(prev => prev.map(cls => ({
            ...cls,
            count: particlesPerClass[cls.id] || 0
        })));
    }, [particleClasses, setParticleClasses]);

    // Load particles when IPP changes
    useEffect(() => {
        if (selectedParticlePicking?.data_json) {
            try {
                const parsedParticles = selectedParticlePicking.data_json as Point[];
                setParticles(parsedParticles);
                updateStats(parsedParticles);
            } catch (error) {
                console.error('Error parsing particles:', error);
                showSnackbar('Error loading particles', 'error');
            }
        } else {
            setParticles([]);
            setHistory([[]]);
            setHistoryIndex(0);
        }
    }, [selectedParticlePicking]);

    // Update IPP when particles change
    useEffect(() => {
        if (selectedParticlePicking) {
            const updatedIpp = {
                ...selectedParticlePicking,
                data_json: particles,
                temp: JSON.stringify(particles)
            };
            handleIppUpdate(updatedIpp);
        }
    }, [particles]);

    const addToHistory = (newParticles: Point[]) => {
        const newHistory = history.slice(0, historyIndex + 1);
        newHistory.push([...newParticles]);
        setHistory(newHistory);
        setHistoryIndex(newHistory.length - 1);
    };

    const undo = () => {
        if (historyIndex > 0) {
            const newIndex = historyIndex - 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            updateStats(history[newIndex]);
            showSnackbar('Undo', 'info');
        }
    };

    const redo = () => {
        if (historyIndex < history.length - 1) {
            const newIndex = historyIndex + 1;
            setHistoryIndex(newIndex);
            setParticles(history[newIndex]);
            updateStats(history[newIndex]);
            showSnackbar('Redo', 'info');
        }
    };

    const selectAll = () => {
        const allIds = new Set(particles.map(p => p.id || ''));
        setSelectedParticles(allIds);
        showSnackbar(`Selected ${particles.length} particles`, 'info');
    };

    const deselectAll = () => {
        setSelectedParticles(new Set());
    };

    const deleteSelected = () => {
        const newParticles = particles.filter(p => !selectedParticles.has(p.id || ''));
        setParticles(newParticles);
        addToHistory(newParticles);
        setSelectedParticles(new Set());
        updateStats(newParticles);
        showSnackbar(`Deleted ${selectedParticles.size} particles`, 'success');
    };

    const copySelected = () => {
        const selected = particles.filter(p => selectedParticles.has(p.id || ''));
        setCopiedParticles(selected);
        showSnackbar(`Copied ${selected.length} particles`, 'success');
    };

    const pasteParticles = () => {
        if (copiedParticles.length === 0) return;

        const offset = 20;
        const newParticles = copiedParticles.map(p => ({
            ...p,
            id: `particle-${Date.now()}-${Math.random()}`,
            x: p.x + offset,
            y: p.y + offset
        }));

        const updatedParticles = [...particles, ...newParticles];
        setParticles(updatedParticles);
        addToHistory(updatedParticles);
        updateStats(updatedParticles);
        showSnackbar(`Pasted ${newParticles.length} particles`, 'success');
    };

    const runAutoPicking = async () => {
        if (!selectedImage?.name) {
            showSnackbar('No image selected for auto-picking', 'warning');
            return;
        }

        if (templatePaths.length === 0) {
            showSnackbar('No templates configured. Open Settings to add template files.', 'warning');
            return;
        }

        setIsAutoPickingRunning(true);
        setAutoPickingProgress(10);

        const API_URL = settings.ConfigData.SERVER_API_URL;

        try {
            const payload = {
                image_path: selectedImage.name,
                template_paths: templatePaths,
                image_pixel_size: imagePixelSize,
                template_pixel_size: templatePixelSize,
                diameter_angstrom: diameterAngstrom,
                threshold: autoPickingThreshold,
                max_peaks: 500,
                bin_factor: 1,
            };

            setAutoPickingProgress(30);

            const response = await fetch(`${API_URL}/plugins/pp/template-pick`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            setAutoPickingProgress(70);

            if (!response.ok) {
                const errData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errData.detail || `Server error ${response.status}`);
            }

            const result = await response.json();

            // Map backend ParticlePick to frontend Point format
            const autoParticles: Point[] = (result.particles || []).map((p: any, idx: number) => ({
                x: p.x,
                y: p.y,
                id: `auto-${Date.now()}-${idx}`,
                type: 'auto' as const,
                confidence: Math.min(p.score, 1.0),
                class: p.score >= autoPickingThreshold ? '1' : '4',
                timestamp: Date.now(),
            }));

            setAutoPickingProgress(90);

            const updatedParticles = [...particles, ...autoParticles];
            setParticles(updatedParticles);
            addToHistory(updatedParticles);
            updateStats(updatedParticles);

            setAutoPickingProgress(100);
            showSnackbar(`Auto-picking completed — ${autoParticles.length} particles detected`, 'success');

        } catch (err: any) {
            console.error('Auto-picking failed:', err);
            showSnackbar(`Auto-picking failed: ${err.message}`, 'error');
        } finally {
            setIsAutoPickingRunning(false);
            setAutoPickingProgress(0);
        }
    };

    const exportParticles = () => {
        const dataStr = JSON.stringify(particles, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
        const exportFileDefaultName = `particles-${selectedImage?.name || 'export'}.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        showSnackbar('Particles exported successfully', 'success');
    };

    const importParticles = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const imported = JSON.parse(e.target?.result as string);
                setParticles(imported);
                addToHistory(imported);
                updateStats(imported);
                showSnackbar('Particles imported successfully', 'success');
            } catch (error) {
                showSnackbar('Failed to import particles', 'error');
            }
        };
        reader.readAsText(file);
    };

    const handleParticlesUpdate = (newParticles: Point[]) => {
        setParticles(newParticles);
        addToHistory(newParticles);
        updateStats(newParticles);
    };

    return {
        particles,
        setParticles,
        selectedParticles,
        setSelectedParticles,
        history,
        historyIndex,
        copiedParticles,
        stats,
        isAutoPickingRunning,
        autoPickingProgress,
        addToHistory,
        undo,
        redo,
        selectAll,
        deselectAll,
        deleteSelected,
        copySelected,
        pasteParticles,
        updateStats,
        handleParticlesUpdate,
        exportParticles,
        importParticles,
        runAutoPicking,
    };
}
