import { useMemo } from 'react';
import { ImageColumnState } from '../../../panel/pages/ImagesPageView.tsx';

export const useVisibleColumns = (
    imageColumns: ImageColumnState[],
    autoHideEmpty: boolean
) => {
    return useMemo(() => {
        if (!imageColumns || !Array.isArray(imageColumns)) {
            return [];
        }

        if (!autoHideEmpty) return imageColumns;

        return imageColumns.filter((col, index) => {
            if (index === 0) return true;
            return col.images?.pages?.length > 0;
        });
    }, [imageColumns, autoHideEmpty]);
};

export const useColumnStatistics = (
    imageColumns: ImageColumnState[],
    visibleColumns: ImageColumnState[]
) => {
    return useMemo(() => {
        if (!imageColumns || !Array.isArray(imageColumns)) {
            return {
                totalColumns: 0,
                visibleCount: 0,
                totalImages: 0
            };
        }

        const totalColumns = imageColumns.length;
        const visibleCount = visibleColumns.length;
        const totalImages = imageColumns.reduce((sum, col) => {
            const imageCount = col.images?.pages?.reduce((pageSum, page) => pageSum + page.result.length, 0) || 0;
            return sum + imageCount;
        }, 0);

        return {
            totalColumns,
            visibleCount,
            totalImages
        };
    }, [imageColumns, visibleColumns]);
};