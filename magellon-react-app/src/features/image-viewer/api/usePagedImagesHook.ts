import { useEffect, useState } from "react";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { fetchFilterSummary, fetchImagesPage, filterParam, type ImageQuery } from "./imagesApiReactQuery.tsx";
import type { PagedImageResponse } from "../../../entities/image/types.ts";
import type { ImageFilter } from "../lib/imageFilter.ts";

interface PagedImagesOptions {
    sessionName: string;
    parentId: string | null;
    pageSize: number;
    level: number;
    enabled?: boolean;
    query?: ImageQuery;
}

/** The query key part for an ImageQuery: the filter as sent, so unfinished edits don't refetch. */
const queryKeyOf = (query: ImageQuery = {}) => ({ ...query, filter: filterParam(query.filter) ?? null });

/** One level of a session's images (a column, a tree node), loaded a page at a time. */
export function useImageListQuery({ sessionName, parentId, pageSize, level, enabled = true, query }: PagedImagesOptions) {
    const shouldEnable = enabled && ((level === 0 && sessionName !== '') || (level > 0 && parentId !== null));

    return useInfiniteQuery<PagedImageResponse>({
        queryKey: ['images', sessionName, parentId, pageSize, queryKeyOf(query)],
        queryFn: ({ pageParam }) => fetchImagesPage(sessionName, parentId, pageParam as number, pageSize, query),
        initialPageParam: 1,
        getNextPageParam: (lastPage) => lastPage.next_page ?? undefined,
        retry: 3,
        enabled: shouldEnable,
        refetchOnMount: true,
        refetchOnWindowFocus: false,
    });
}

/** One page of a session's images (grid, table): filtered, sorted and paged by the server. */
export function useImagesPage(sessionName: string, page: number, pageSize: number, query: ImageQuery) {
    return useQuery<PagedImageResponse>({
        queryKey: ['images', sessionName, 'page', page, pageSize, queryKeyOf(query)],
        queryFn: () => fetchImagesPage(sessionName, null, page, pageSize, query),
        enabled: sessionName !== '',
        placeholderData: keepPreviousData,
        refetchOnWindowFocus: false,
    });
}

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delayMs);
        return () => clearTimeout(timer);
    }, [value, delayMs]);
    return debounced;
}

/** For the filter dialog: how many images match, and each number field's values. */
export function useFilterSummary(sessionName: string, filter: ImageFilter | null, enabled: boolean) {
    const sent = useDebouncedValue(filterParam(filter) ?? null);
    return useQuery({
        queryKey: ['images', sessionName, 'filter-summary', sent],
        queryFn: () => fetchFilterSummary(sessionName, sent),
        enabled: enabled && sessionName !== '',
        placeholderData: keepPreviousData,
        refetchOnWindowFocus: false,
    });
}
