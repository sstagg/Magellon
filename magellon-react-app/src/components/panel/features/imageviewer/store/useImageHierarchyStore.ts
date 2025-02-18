// stores/useImageHierarchyStore.ts
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import ImageInfoDto from "../ImageInfoDto.ts";


interface ImageColumn {
    images: ImageInfoDto[]
    parentImage: ImageInfoDto | null
    isLoading: boolean
    error: Error | null
    caption: string
    level: number
}

interface ImageHierarchyState {
    // State
    columns: ImageColumn[]
    selectedImages: (ImageInfoDto | null)[]
    sessionName: string | null

    // Actions
    setSessionName: (name: string) => void
    selectImage: (image: ImageInfoDto, columnIndex: number) => void
    clearColumnsAfter: (columnIndex: number) => void
    loadImagesForColumn: (columnIndex: number, parentId: string | null) => Promise<void>
    resetState: () => void
}

const INITIAL_COLUMNS = [
    { caption: 'Atlas', level: 0 },
    { caption: 'Grid Squares', level: 1 },
    { caption: 'Holes', level: 2 },
    { caption: 'Exposures', level: 3 }
].map(col => ({
    ...col,
    images: [],
    parentImage: null,
    isLoading: false,
    error: null
}))

export const useImageHierarchyStore = create<ImageHierarchyState>()(
    devtools(
        (set, get) => ({
            // Initial state
            columns: INITIAL_COLUMNS,
            selectedImages: new Array(INITIAL_COLUMNS.length).fill(null),
            sessionName: null,

            setSessionName: (name: string) => {
                set({ sessionName: name })
                // Reset columns when session changes
                get().resetState()
                // Load initial column
                get().loadImagesForColumn(0, null)
            },

            selectImage: (image: ImageInfoDto, columnIndex: number) => {
                const { selectedImages, loadImagesForColumn } = get()

                // Update selected images array
                const newSelectedImages = [...selectedImages]
                newSelectedImages[columnIndex] = image

                // Clear selections after current column
                for (let i = columnIndex + 1; i < newSelectedImages.length; i++) {
                    newSelectedImages[i] = null
                }

                set({ selectedImages: newSelectedImages })

                // Load children if this image has any
                if (image.children_count > 0) {
                    loadImagesForColumn(columnIndex + 1, image.oid)
                }
            },

            loadImagesForColumn: async (columnIndex: number, parentId: string | null) => {
                const { columns, sessionName } = get()
                if (!sessionName) return

                // Update loading state
                const newColumns = [...columns]
                newColumns[columnIndex] = {
                    ...newColumns[columnIndex],
                    isLoading: true,
                    error: null
                }
                set({ columns: newColumns })

                try {
                    const response = await fetch(`/api/images?sessionName=${sessionName}&parentId=${parentId}&level=${columnIndex}`)
                    const data = await response.json()

                    newColumns[columnIndex] = {
                        ...newColumns[columnIndex],
                        images: data,
                        isLoading: false,
                        parentId
                    }
                    set({ columns: newColumns })
                } catch (error) {
                    newColumns[columnIndex] = {
                        ...newColumns[columnIndex],
                        error: error instanceof Error ? error : new Error('Failed to load images'),
                        isLoading: false
                    }
                    set({ columns: newColumns })
                }
            },

            clearColumnsAfter: (columnIndex: number) => {
                const { columns } = get()
                const newColumns = columns.map((col, index) =>
                    index > columnIndex
                        ? { ...col, images: [], parentImage: null, error: null }
                        : col
                )
                set({ columns: newColumns })
            },

            resetState: () => {
                set({
                    columns: INITIAL_COLUMNS,
                    selectedImages: new Array(INITIAL_COLUMNS.length).fill(null)
                })
            }
        }),
        { name: 'image-hierarchy-store' }
    )
)