// api/imageApi.js

import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { toApiError } from '../../../shared/api/apiError.ts';
import {settings} from '../../../shared/config/settings.ts'

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = `${settings.ConfigData.SERVER_WEB_API_URL }/images`;

import type ImageInfoDto from '../../../entities/image/types.ts';
import type { PagedImageResponse } from '../../../entities/image/types.ts';
import { activeFilter, type ImageFilter } from '../lib/imageFilter.ts';

export type ImageSort = 'related' | 'name' | 'mag' | 'defocus' | 'resolution' | 'pixelSize' | 'children';

/** What the server should select and how; all filtering, sorting and paging happen there. */
export interface ImageQuery {
    /** Every image of the session instead of one level. */
    allLevels?: boolean;
    filter?: ImageFilter | null;
    /** With a filter, also the images above each match (columns and tree). */
    includeAncestors?: boolean;
    /** Name contains. */
    search?: string;
    sort?: ImageSort;
    order?: 'asc' | 'desc';
}

/** The filter as the server takes it, or undefined when it has no finished condition. */
export const filterParam = (filter?: ImageFilter | null): string | undefined => {
    const active = filter ? activeFilter(filter) : null;
    return active ? JSON.stringify(active) : undefined;
};

const failure = (error: unknown, what: string): Error => {
    const err = toApiError(error);
    if (err.status === 401) return new Error('Please login to view images');
    if (err.status === 403) return new Error('You do not have permission to view images');
    return new Error(err.detail || `Failed to load ${what}`);
};

export const fetchImagesPage = async (
    sessionName: string,
    parentId: string | null,
    page: number,
    pageSize: number,
    query: ImageQuery = {}
): Promise<PagedImageResponse> => {
    try {
        const response = await apiClient.get(BASE_URL, {
            params: {
                session_name: sessionName,
                parentId,
                page,
                pageSize,
                ...(query.allLevels ? { all_levels: true } : {}),
                filter: filterParam(query.filter),
                ...(query.includeAncestors ? { include_ancestors: true } : {}),
                search: query.search?.trim() || undefined,
                sort: query.sort && query.sort !== 'related' ? query.sort : undefined,
                order: query.order === 'desc' ? 'desc' : undefined,
            },
        });
        return response.data;
    } catch (error) {
        throw failure(error, 'images');
    }
};

export interface FieldSummary {
    count: number;
    min: number | null;
    max: number | null;
    /** Every value, when there are only a few. */
    values: number[] | null;
}

export interface FilterSummary {
    total: number;
    matching: number;
    fields: Record<string, FieldSummary>;
}

/** filter: as filterParam makes it. */
export const fetchFilterSummary = async (sessionName: string, filter?: string | null): Promise<FilterSummary> => {
    try {
        const response = await apiClient.get(`${settings.ConfigData.SERVER_WEB_API_URL}/images-filter-summary`, {
            params: { session_name: sessionName, filter: filter ?? undefined },
        });
        return response.data;
    } catch (error) {
        throw failure(error, 'the filter summary');
    }
};

/** The image and every image above it, top level first. */
export const fetchImagePath = async (imageId: string): Promise<ImageInfoDto[]> => {
    try {
        const response = await apiClient.get(`${settings.ConfigData.SERVER_WEB_API_URL}/image-path`, {
            params: { image_id: imageId },
        });
        return response.data;
    } catch (error) {
        throw failure(error, 'the image path');
    }
};
