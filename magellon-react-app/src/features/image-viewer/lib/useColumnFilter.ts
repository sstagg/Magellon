import { useMemo, useState } from 'react';
import ImageInfoDto from '../../../entities/image/types.ts';

export interface ColumnFilter {
    search?: string;
    defocusMin?: number;
    defocusMax?: number;
    hasChildren?: boolean;
    magnification?: number;
}

export type SortField = 'name' | 'defocus' | 'children_count' | 'mag' | 'pixelSize';
export type SortDirection = 'asc' | 'desc';

export interface SortConfig {
    field: SortField;
    direction: SortDirection;
}

type SortableValue = string | number | undefined;

function getSortValue(image: ImageInfoDto, field: SortField): SortableValue {
    switch (field) {
        case 'name': return image.name?.toLowerCase();
        case 'defocus': return image.defocus;
        case 'children_count': return image.children_count;
        case 'mag': return image.mag;
        case 'pixelSize': return image.pixelSize;
        default: return undefined;
    }
}

function matchesFilter(image: ImageInfoDto, filter: ColumnFilter): boolean {
    if (filter.search && image.name &&
        !image.name.toLowerCase().includes(filter.search.toLowerCase())) {
        return false;
    }
    if (filter.defocusMin !== undefined &&
        (image.defocus === undefined || image.defocus < filter.defocusMin)) {
        return false;
    }
    if (filter.defocusMax !== undefined &&
        (image.defocus === undefined || image.defocus > filter.defocusMax)) {
        return false;
    }
    if (filter.hasChildren !== undefined &&
        ((image.children_count || 0) > 0) !== filter.hasChildren) {
        return false;
    }
    if (filter.magnification !== undefined && image.mag !== filter.magnification) {
        return false;
    }
    return true;
}

function compareValues(a: SortableValue, b: SortableValue, direction: SortDirection): number {
    if (a === undefined && b === undefined) return 0;
    if (a === undefined) return 1;
    if (b === undefined) return -1;

    let comparison = 0;
    if (a < b) comparison = -1;
    if (a > b) comparison = 1;

    return direction === 'desc' ? -comparison : comparison;
}

export function useColumnFilter(allImages: ImageInfoDto[]) {
    const [filter, setFilter] = useState<ColumnFilter>({});
    const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'name', direction: 'asc' });

    const { filteredImages, totalCount } = useMemo(() => {
        const filtered = allImages
            .filter(image => matchesFilter(image, filter))
            .sort((a, b) => compareValues(
                getSortValue(a, sortConfig.field),
                getSortValue(b, sortConfig.field),
                sortConfig.direction
            ));

        return { filteredImages: filtered, totalCount: allImages.length };
    }, [allImages, filter, sortConfig]);

    const resetFilter = () => setFilter({});

    return {
        filter,
        setFilter,
        resetFilter,
        sortConfig,
        setSortConfig,
        filteredImages,
        totalCount,
    };
}
