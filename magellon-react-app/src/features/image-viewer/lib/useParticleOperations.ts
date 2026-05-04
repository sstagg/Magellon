import React, { useState, useEffect, useCallback } from 'react';
import { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';
import ImageInfoDto from '../../../entities/image/types.ts';
import { settings } from '../../../shared/config/settings.ts';

// API path for the particle-picking feature endpoints. Lifted from
// the legacy ``/plugins/pp/template-pick`` URL in PI-4 — these aren't
// "plugin" endpoints, they're particle-picking features that happen
// to use template matching today.
export const TEMPLATE_PICKER_PATH = '/particle-picking';

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
    sessionName?: string;
    particleClasses: ParticleClass[];
    setParticleClasses: React.Dispatch<React.SetStateAction<ParticleClass[]>>;
    /** All algorithm params as a flat dict (driven by schema) */
    pickerParams: Record<string, any>;
    showSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
    /** Called after a successful run-and-save so the IPP dropdown refreshes. */
    onIppSaved?: (ippOid: string, ippName: string) => void;
}

export function useParticleOperations({
    selectedParticlePicking,
    handleIppUpdate,
    selectedImage,
    sessionName,
    particleClasses,
    setParticleClasses,
    pickerParams,
    showSnackbar,
    onIppSaved,
}: UseParticleOperationsParams) {
    const [particles, setParticles] = useState<Point[]>([]);
    const [selectedParticles, setSelectedParticles] = useState<Set<string>>(new Set());
    const [history, setHistory] = useState<Point[][]>([[]]);
    const [historyIndex, setHistoryIndex] = useState(0);
    const [copiedParticles, setCopiedParticles] = useState<Point[]>([]);
    const [isAutoPickingRunning, setIsAutoPickingRunning] = useState(false);
    const [autoPickingProgress, setAutoPickingProgress] = useState(0);
    // [height, width] of the coord space particles live in — set by the picker
    // backend so the canvas can size its viewBox to match particle positions.
    const [imageShape, setImageShape] = useState<[number, number] | null>(null);

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
                setImageShape(null);
            } catch (error) {
                console.error('Error parsing particles:', error);
                showSnackbar('Error loading particles', 'error');
            }
        } else {
            setParticles([]);
            setHistory([[]]);
            setHistoryIndex(0);
            setImageShape(null);
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

        const templatePaths = pickerParams.template_paths || [];
        if (templatePaths.length === 0) {
            showSnackbar('No templates configured. Open Settings to add template files.', 'warning');
            return;
        }

        setIsAutoPickingRunning(true);

        const API_URL = settings.ConfigData.SERVER_API_URL;
        const token = localStorage.getItem('access_token');
        const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

        // Image oid + session name together mean the image lives in our DB — go
        // through run-and-save so the result persists as an ImageMetaData row
        // (plugin_id=pp). Without both, fall back to the stateless sync call.
        const hasDbImage = !!(selectedImage.oid && sessionName);

        try {
            const picker_params: Record<string, any> = { ...pickerParams };
            delete picker_params.image_path;
            Object.keys(picker_params).forEach((k) => {
                if (picker_params[k] === null || picker_params[k] === undefined) delete picker_params[k];
            });

            let autoParticles: Point[] = [];
            let savedIpp: { oid: string; name: string } | null = null;

            if (hasDbImage) {
                const body = {
                    session_name: sessionName!,
                    image_oid: selectedImage.oid,
                    ipp_name: selectedParticlePicking?.name || `Auto-pick ${new Date().toISOString().slice(0, 16)}`,
                    picker_params,
                };
                const response = await fetch(`${API_URL}${TEMPLATE_PICKER_PATH}/run-and-save`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...authHeader },
                    body: JSON.stringify(body),
                });
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({ detail: response.statusText }));
                    throw new Error(errData.detail || `Server error ${response.status}`);
                }
                const result = await response.json();
                if (Array.isArray(result.image_shape) && result.image_shape.length === 2) {
                    setImageShape([result.image_shape[0], result.image_shape[1]]);
                }
                savedIpp = { oid: result.ipp_oid, name: result.ipp_name };

                // Fetch the saved data_json to render the newly-saved points.
                const fetchUrl = `${API_URL}${TEMPLATE_PICKER_PATH}`; // unused; we load via /web below
                // The saved Point objects live in data_json — reload so the
                // state matches what's in the DB and the dropdown entry.
                void fetchUrl;
                // Fall through: onIppSaved triggers a refresh in the caller, so
                // we just drop the preview points and let the reload repopulate.
            } else {
                // No DB image — use the stateless sync endpoint and keep
                // particles in local state only (e.g. the plugin test page).
                const payload: Record<string, any> = { ...picker_params };
                // For the stateless path the caller is responsible for providing
                // an image_path; preserve whatever was passed in pickerParams.
                if (pickerParams.image_path) payload.image_path = pickerParams.image_path;
                const response = await fetch(`${API_URL}${TEMPLATE_PICKER_PATH}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...authHeader },
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({ detail: response.statusText }));
                    throw new Error(errData.detail || `Server error ${response.status}`);
                }
                const result = await response.json();
                if (Array.isArray(result.image_shape) && result.image_shape.length === 2) {
                    setImageShape([result.image_shape[0], result.image_shape[1]]);
                }
                const threshold = pickerParams.threshold ?? 0.4;
                autoParticles = (result.particles || []).map((p: any, idx: number) => ({
                    x: p.x,
                    y: p.y,
                    id: `auto-${Date.now()}-${idx}`,
                    type: 'auto' as const,
                    confidence: Math.min(p.score, 1.0),
                    class: p.score >= threshold ? '1' : '4',
                    timestamp: Date.now(),
                }));

                const updatedParticles = [...particles, ...autoParticles];
                setParticles(updatedParticles);
                addToHistory(updatedParticles);
                updateStats(updatedParticles);
            }

            if (savedIpp) {
                showSnackbar(`Auto-picking saved as "${savedIpp.name}"`, 'success');
                onIppSaved?.(savedIpp.oid, savedIpp.name);
            } else {
                showSnackbar(`Auto-picking completed — ${autoParticles.length} particles detected`, 'success');
            }

        } catch (err: any) {
            console.error('Auto-picking failed:', err);
            showSnackbar(`Auto-picking failed: ${err.message}`, 'error');
        } finally {
            setIsAutoPickingRunning(false);
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
        imageShape,
        setImageShape,
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
