// src/stores/useImageGalleryStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { InfiniteData } from 'react-query';
import ImageInfoDto, { PagedImageResponse } from '../types/ImageInfoDto';

export type LayoutOrientation = 'horizontal' | 'vertical';

export interface GalleryColumn {
  id: string;
  level: number;
  caption: string;
  parentId: string | null;
  images: InfiniteData<PagedImageResponse> | null;
  selectedImageId: string | null;
  isLoading: boolean;
  error: Error | null;
  hasMore: boolean;
}

interface ImageGalleryState {
  // Configuration
  orientation: LayoutOrientation;
  sessionName: string | null;
  
  // Data
  columns: GalleryColumn[];
  
  // Actions
  setOrientation: (orientation: LayoutOrientation) => void;
  setSessionName: (name: string | null) => void;
  
  addColumn: (level: number, caption: string) => void;
  selectImage: (columnIndex: number, imageId: string, hasChildren: boolean) => void;
  
  updateColumnImages: (columnIndex: number, images: InfiniteData<PagedImageResponse>) => void;
  updateColumnLoading: (columnIndex: number, isLoading: boolean) => void;
  updateColumnError: (columnIndex: number, error: Error | null) => void;
  
  clearColumnsAfter: (columnIndex: number) => void;
  resetGallery: () => void;
}

// Initial column data (can be configured)
const DEFAULT_COLUMNS = [
  { id: 'col-0', level: 0, caption: 'Atlas', parentId: null },
  { id: 'col-1', level: 1, caption: 'Grid Squares', parentId: null },
  { id: 'col-2', level: 2, caption: 'Holes', parentId: null },
  { id: 'col-3', level: 3, caption: 'Exposures', parentId: null },
].map(col => ({
  ...col,
  images: null,
  selectedImageId: null,
  isLoading: false,
  error: null,
  hasMore: false,
}));

export const useImageGalleryStore = create<ImageGalleryState>()(
  devtools(
    (set, get) => ({
      // Initial state
      orientation: 'horizontal',
      sessionName: null,
      columns: DEFAULT_COLUMNS,
      
      // Actions
      setOrientation: (orientation) => set({ orientation }),
      
      setSessionName: (name) => {
        set({ sessionName: name });
        get().resetGallery();
      },
      
      addColumn: (level, caption) => {
        const { columns } = get();
        const newColumn: GalleryColumn = {
          id: `col-${columns.length}`,
          level,
          caption,
          parentId: null,
          images: null,
          selectedImageId: null,
          isLoading: false,
          error: null,
          hasMore: false,
        };
        
        set({ columns: [...columns, newColumn] });
      },
      
      selectImage: (columnIndex, imageId, hasChildren) => {
        const { columns } = get();
        
        // Update current column selection
        const updatedColumns = [...columns];
        updatedColumns[columnIndex] = {
          ...updatedColumns[columnIndex],
          selectedImageId: imageId,
        };
        
        // Update parent ID for the next column if it exists
        if (columnIndex + 1 < updatedColumns.length) {
          updatedColumns[columnIndex + 1] = {
            ...updatedColumns[columnIndex + 1],
            parentId: hasChildren ? imageId : null,
            selectedImageId: null,
            images: null,
          };
        }
        
        set({ columns: updatedColumns });
        
        // Clear columns after the next one
        if (columnIndex + 1 < updatedColumns.length) {
          get().clearColumnsAfter(columnIndex + 1);
        }
      },
      
      updateColumnImages: (columnIndex, images) => {
        if (columnIndex >= get().columns.length) return;
        
        set(state => {
          const updatedColumns = [...state.columns];
          updatedColumns[columnIndex] = {
            ...updatedColumns[columnIndex],
            images,
            hasMore: images.pages[images.pages.length - 1].next_page !== null,
            isLoading: false,
            error: null,
          };
          return { columns: updatedColumns };
        });
      },
      
      updateColumnLoading: (columnIndex, isLoading) => {
        if (columnIndex >= get().columns.length) return;
        
        set(state => {
          const updatedColumns = [...state.columns];
          updatedColumns[columnIndex] = {
            ...updatedColumns[columnIndex],
            isLoading,
          };
          return { columns: updatedColumns };
        });
      },
      
      updateColumnError: (columnIndex, error) => {
        if (columnIndex >= get().columns.length) return;
        
        set(state => {
          const updatedColumns = [...state.columns];
          updatedColumns[columnIndex] = {
            ...updatedColumns[columnIndex],
            error,
            isLoading: false,
          };
          return { columns: updatedColumns };
        });
      },
      
      clearColumnsAfter: (columnIndex) => {
        const { columns } = get();
        
        const updatedColumns = columns.map((column, index) => {
          if (index <= columnIndex) return column;
          
          return {
            ...column,
            parentId: null,
            selectedImageId: null,
            images: null,
            isLoading: false,
            error: null,
          };
        });
        
        set({ columns: updatedColumns });
      },
      
      resetGallery: () => {
        set({
          columns: DEFAULT_COLUMNS,
        });
      },
    }),
    { name: 'image-gallery-store' }
  )
);
