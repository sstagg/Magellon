// stores/useImageViewerStore.ts
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

import {settings} from "../../../../../core/settings.ts";
import {ParticlePickingDto} from "../../../../../domains/ParticlePickingDto.ts";
import ImageInfoDto, {ImageCtfInfo} from "../ImageInfoDto.ts";


const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL

interface ImageViewerState {
    // Selected Image State
    selectedImage: ImageInfoDto | null
    setSelectedImage: (image: ImageInfoDto | null) => void

    // Tab State
    activeTab: string
    setActiveTab: (tab: string) => void

    // Particle Picking State
    selectedParticlePicking: ParticlePickingDto | null
    setSelectedParticlePicking: (pp: ParticlePickingDto | null) => void
    particlePickingDialogOpen: boolean
    setParticlePickingDialogOpen: (open: boolean) => void

    // CTF Info State
    ctfInfo: ImageCtfInfo | null
    isCtfLoading: boolean
    ctfError: Error | null
    fetchCtfInfo: (imageName: string) => Promise<void>

    // Image URL Getters
    getThumbnailUrl: (imageName: string) => string
    getFftUrl: (imageName: string) => string
    getCtfUrl: (imageName: string, type: 'powerspec' | 'plots') => string

    // Actions
    saveParticlePicking: () => Promise<void>
    resetState: () => void
}


export const useImageViewerStore = create<ImageViewerState>()(
    devtools(
        (set, get) => ({
            // Initial State
            selectedImage: null,
            activeTab: '1',
            selectedParticlePicking: null,
            particlePickingDialogOpen: false,
            ctfInfo: null,
            isCtfLoading: false,
            ctfError: null,

            // Setters
            setSelectedImage: (image) => set({ selectedImage: image }),
            setActiveTab: (tab) => set({ activeTab: tab }),
            setSelectedParticlePicking: (pp) => set({ selectedParticlePicking: pp }),
            setParticlePickingDialogOpen: (open) => set({ particlePickingDialogOpen: open }),

            // URL Getters
            getThumbnailUrl: (imageName) => `${BASE_URL}/image_thumbnail?name=${imageName}`,
            getFftUrl: (imageName) => `${BASE_URL}/fft_image?name=${imageName}`,
            getCtfUrl: (imageName, type) => `${BASE_URL}/ctf_image?image_type=${type}&name=${imageName}`,

            // Async Actions
            fetchCtfInfo: async (imageName) => {
                set({ isCtfLoading: true, ctfError: null })
                try {
                    const response = await fetch(`${BASE_URL}/ctf_info?name=${imageName}`)
                    if (!response.ok) throw new Error('Failed to fetch CTF info')
                    const data = await response.json()
                    set({ ctfInfo: data, isCtfLoading: false })
                } catch (error) {
                    set({
                        ctfError: error instanceof Error ? error : new Error('Unknown error'),
                        isCtfLoading: false
                    })
                }
            },

            saveParticlePicking: async () => {
                const { selectedParticlePicking } = get()
                if (!selectedParticlePicking) return

                try {
                    const response = await fetch(`${BASE_URL}/particle-picking`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(selectedParticlePicking)
                    })

                    if (!response.ok) throw new Error('Failed to save particle picking')

                    const updatedPP = await response.json()
                    set({ selectedParticlePicking: updatedPP })
                } catch (error) {
                    console.error('Failed to save particle picking:', error)
                    throw error
                }
            },

            // Reset State
            resetState: () => set({
                selectedImage: null,
                activeTab: '1',
                selectedParticlePicking: null,
                particlePickingDialogOpen: false,
                ctfInfo: null,
                isCtfLoading: false,
                ctfError: null
            })
        }),
        { name: 'image-viewer-store' }
    )
)