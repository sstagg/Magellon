import { useMemo, useState } from 'react';
import type ImageInfoDto from '../../../entities/image/types.ts';

/** The column's own name search; the image filter comes as the ids it leaves visible. */
export interface ColumnFilter {
    search?: string;
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

function compareValues(a: SortableValue, b: SortableValue, direction: SortDirection): number {
    if (a === undefined && b === undefined) return 0;
    if (a === undefined) return 1;
    if (b === undefined) return -1;

    let comparison = 0;
    if (a < b) comparison = -1;
    if (a > b) comparison = 1;

    return direction === 'desc' ? -comparison : comparison;
}

export function useColumnFilter(allImages: ImageInfoDto[], visibleIds?: Set<string> | null) {
    const [filter, setFilter] = useState<ColumnFilter>({});
    const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'name', direction: 'asc' });

    const { filteredImages, totalCount } = useMemo(() => {
        // Images with children stay first, whichever way the rest is sorted.
        const filtered = allImages
            .filter(image => (!visibleIds || visibleIds.has(image.oid)) &&
                (!filter.search || !!image.name?.toLowerCase().includes(filter.search.toLowerCase())))
            .sort((a, b) =>
                Number((b.children_count || 0) > 0) - Number((a.children_count || 0) > 0) ||
                compareValues(
                    getSortValue(a, sortConfig.field),
                    getSortValue(b, sortConfig.field),
                    sortConfig.direction
                ));

        return { filteredImages: filtered, totalCount: allImages.length };
    }, [allImages, filter, sortConfig, visibleIds]);

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
