import { useEffect, useState } from 'react';
import { useImageListQuery } from '../../../../services/api/usePagedImagesHook';
import { useImageViewerStore } from '../store/imageViewerStore';

interface UseImageDataFetchingOptions {
    sessionName?: string;
    pageSize?: number;
}

export const useImageDataFetching = (options: UseImageDataFetchingOptions = {}) => {
    const { pageSize = 100 } = options;

    // Get store state and actions
    const {
        currentSession,
        currentImage,
        imageColumns,
        updateImageColumn
    } = useImageViewerStore();

    // Local state for query parameters
    const [level, setLevel] = useState<number>(0);
    const [parentId, setParentId] = useState<string | null>(null);

    const sessionName = options.sessionName || currentSession?.name;

    // Fetch paged images with current query parameters
    const {
        data,
        isSuccess,
        isLoading,
        isError,
        refetch,
    } = useImageListQuery({ sessionName, parentId, pageSize, level });

    // Update image columns when data changes or navigation occurs
    useEffect(() => {
        // Helper function to fetch data for a specific column
        const getImageColumnsData = async (columnIndex: number) => {
            if (columnIndex === -1) {
                // Root column - fetch top-level images
                setParentId(null);
                setLevel(0);
                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    updateImageColumn(0, { images: data });
                }
            } else if (
                imageColumns[columnIndex].selectedImage &&
                imageColumns[columnIndex].selectedImage?.children_count! > 0
            ) {
                // Child column - fetch images for selected parent
                setParentId(imageColumns[columnIndex].selectedImage!.oid);
                setLevel(columnIndex + 1);

                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    updateImageColumn(columnIndex + 1, { images: data });
                }
            }
        };

        // Fetch root column when session is selected
        if (currentSession !== null) {
            getImageColumnsData(-1);
        }

        // Fetch child columns when images are selected
        for (let i = 0; i < imageColumns.length - 1; i++) {
            if (imageColumns[i].selectedImage !== null && imageColumns[i].selectedImage?.oid !== null) {
                getImageColumnsData(i);
            }
        }
    }, [currentImage?.oid, level, data, isSuccess, currentSession]);

    return {
        data,
        isLoading,
        isError,
        isSuccess,
        refetch
    };
};
