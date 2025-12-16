import { useCallback } from 'react';
import { useImageViewerStore, ImageColumn } from '../store/imageViewerStore.ts';
import ImageInfoDto, { SessionDto } from '../ImageInfoDto.ts';
import { SelectChangeEvent } from '@mui/material';

interface UseImageNavigationReturn {
    handleImageClick: (image: ImageInfoDto, columnIndex: number) => void;
    handleSessionSelect: (event: SelectChangeEvent) => void;
    navigateUp: () => void;
    resetNavigation: () => void;
}

export const useImageNavigation = (): UseImageNavigationReturn => {
    const {
        imageColumns,
        setCurrentSession,
        setCurrentImage,
        selectImageInColumn,
        resetImageColumns
    } = useImageViewerStore();

    // Handle image selection in a column
    const handleImageClick = useCallback((image: ImageInfoDto, columnIndex: number) => {
        if (columnIndex === imageColumns.length - 1) {
            // Last column - just set as current image
            setCurrentImage(image);
            return;
        }

        // Update selection and propagate to store
        selectImageInColumn(image, columnIndex);
        setCurrentImage(image);
    }, [imageColumns.length, selectImageInColumn, setCurrentImage]);

    // Handle session selection from dropdown
    const handleSessionSelect = useCallback((event: SelectChangeEvent) => {
        const selectedValue = event.target.value;

        // If "None" is selected (empty string), set session to null
        if (!selectedValue) {
            setCurrentSession(null);
            resetImageColumns();
            setCurrentImage(null);
            return;
        }

        const sessionDto: SessionDto = {
            Oid: selectedValue,
            name: selectedValue,
        };

        setCurrentSession(sessionDto);
        resetImageColumns();
        setCurrentImage(null);
    }, [setCurrentSession, resetImageColumns, setCurrentImage]);

    // Navigate up in hierarchy (go to parent)
    const navigateUp = useCallback(() => {
        // Find the first non-null column from right to left
        for (let i = imageColumns.length - 1; i >= 0; i--) {
            if (imageColumns[i].selectedImage) {
                // Clear this column and all to the right
                selectImageInColumn(null, i);
                setCurrentImage(i > 0 ? imageColumns[i - 1].selectedImage : null);
                return;
            }
        }
    }, [imageColumns, selectImageInColumn, setCurrentImage]);

    // Reset navigation to initial state
    const resetNavigation = useCallback(() => {
        resetImageColumns();
        setCurrentImage(null);
    }, [resetImageColumns, setCurrentImage]);

    return {
        handleImageClick,
        handleSessionSelect,
        navigateUp,
        resetNavigation
    };
};
