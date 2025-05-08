// stores/imageViewerStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import ImageInfoDto, { SessionDto, AtlasImageDto, PagedImageResponse } from '../ImageInfoDto';
import { ParticlePickingDto } from '../../../../../domains/ParticlePickingDto';
import { InfiniteData } from 'react-query';

// The ImageColumn interface that matches your current state structure
export interface ImageColumn {
    selectedImage: ImageInfoDto | null;
    caption: string;
    level: number;
    images: InfiniteData<PagedImageResponse> | null;
}

// Define view modes
export type ViewMode = 'grid' | 'tree' | 'table';

interface ImageViewerState {
    // Current selections
    currentSession: SessionDto | null;
    currentImage: ImageInfoDto | null;

    // Navigation state - keeping your current ImageColumn structure
    imageColumns: ImageColumn[];

    // Tab management
    activeTab: string;

    // Atlas management
    isAtlasVisible: boolean;
    currentAtlas: AtlasImageDto | null;
    atlasImages: AtlasImageDto[] | null;

    // Particle picking
    selectedParticlePicking: ParticlePickingDto | null;

    // View modes
    viewMode: ViewMode;

    // Image settings
    brightness: number;
    contrast: number;
    scale: number;

    // Dialog states
    isParticlePickingDialogOpen: boolean;

    // Actions
    setCurrentSession: (session: SessionDto | null) => void;
    setCurrentImage: (image: ImageInfoDto | null) => void;
    updateImageColumn: (columnIndex: number, columnData: Partial<ImageColumn>) => void;
    resetImageColumns: () => void;
    selectImageInColumn: (image: ImageInfoDto, columnIndex: number) => void;
    setAtlasImages: (atlasImages: AtlasImageDto[] | null) => void;
    setActiveTab: (tabId: string) => void;
    toggleAtlasVisibility: () => void;
    setCurrentAtlas: (atlas: AtlasImageDto) => void;
    setSelectedParticlePicking: (pp: ParticlePickingDto | null) => void;
    updateParticlePicking: (updatedPP: ParticlePickingDto) => void;
    setViewMode: (mode: ViewMode) => void;
    setBrightness: (value: number) => void;
    setContrast: (value: number) => void;
    setScale: (value: number) => void;
    openParticlePickingDialog: () => void;
    closeParticlePickingDialog: () => void;
}

const initialImageColumns: ImageColumn[] = [
    {
        caption: "GR",
        level: 0,
        images: null,
        selectedImage: null,
    },
    {
        caption: "SQ",
        level: 1,
        images: null,
        selectedImage: null,
    },
    {
        caption: "HL",
        level: 2,
        images: null,
        selectedImage: null,
    },
    {
        caption: "EX",
        level: 3,
        images: null,
        selectedImage: null,
    },
];

export const useImageViewerStore = create<ImageViewerState>()(
    persist(
        (set) => ({
            // Initial state
            currentSession: null,
            currentImage: null,
            imageColumns: [...initialImageColumns],
            activeTab: '1', // Default to first tab
            isAtlasVisible: true,
            currentAtlas: null,
            atlasImages: null,
            selectedParticlePicking: null,
            viewMode: 'grid',
            brightness: 50,
            contrast: 50,
            scale: 1,
            isParticlePickingDialogOpen: false,

            // Actions
            setCurrentSession: (session) => set({
                currentSession: session,
                currentImage: null,
                imageColumns: [...initialImageColumns],
            }),

            setCurrentImage: (image) => set({ currentImage: image }),

            updateImageColumn: (columnIndex, columnData) => set((state) => ({
                imageColumns: state.imageColumns.map((column, index) =>
                    index === columnIndex ? { ...column, ...columnData } : column
                )
            })),

            resetImageColumns: () => set({
                imageColumns: [...initialImageColumns],
                currentImage: null,
            }),

            selectImageInColumn: (image, columnIndex) => set((state) => {
                // Only proceed if this isn't the last column
                if (columnIndex >= state.imageColumns.length - 1) return state;

                const updatedImageColumns = state.imageColumns.map((column, index) => {
                    if (index === columnIndex) {
                        // Update the selectedImage property for the specified column
                        return {
                            ...column,
                            selectedImage: image,
                        };
                    } else if (index > columnIndex) {
                        // Clear selectedImage for columns to the right
                        return {
                            ...column,
                            selectedImage: null,
                            images: null
                        };
                    } else {
                        // Keep the rest of the properties unchanged
                        return column;
                    }
                });

                return {
                    imageColumns: updatedImageColumns,
                    currentImage: image,
                };
            }),

            setAtlasImages: (atlasImages) => set({ atlasImages }),

            setActiveTab: (tabId) => set({ activeTab: tabId }),

            toggleAtlasVisibility: () => set((state) => ({
                isAtlasVisible: !state.isAtlasVisible
            })),

            setCurrentAtlas: (atlas) => set({ currentAtlas: atlas }),

            setSelectedParticlePicking: (pp) => set({ selectedParticlePicking: pp }),

            updateParticlePicking: (updatedPP) => set({ selectedParticlePicking: updatedPP }),

            setViewMode: (mode) => set({ viewMode: mode }),

            setBrightness: (value) => set({ brightness: value }),

            setContrast: (value) => set({ contrast: value }),

            setScale: (value) => set({ scale: value }),

            openParticlePickingDialog: () => set({ isParticlePickingDialogOpen: true }),

            closeParticlePickingDialog: () => set({ isParticlePickingDialogOpen: false }),
        }),
        {
            name: 'magellon-image-viewer-storage', // name of the item in localStorage
            storage: createJSONStorage(() => localStorage),
            // Optionally, specify which parts of your state to persist
            partialize: (state) => ({
                currentSession: state.currentSession,
                currentImage: state.currentImage,
                viewMode: state.viewMode,
                isAtlasVisible: state.isAtlasVisible,
                activeTab: state.activeTab,
                // We don't persist large data objects like imageColumns.images
                // to avoid localStorage size limits
                imageColumns: state.imageColumns.map(col => ({
                    ...col,
                    images: null // Don't store large image data in localStorage
                }))
            }),
        }
    )
);