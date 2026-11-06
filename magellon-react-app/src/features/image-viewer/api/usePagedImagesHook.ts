import {useEffect, useMemo} from "react";
import {useInfiniteQuery} from "@tanstack/react-query";
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import type {PagedImageResponse} from "../../../entities/image/types.ts";
import type ImageInfoDto from "../../../entities/image/types.ts";


interface PagedImagesOptions {
    sessionName: string;
    parentId: string | null;
    pageSize: number;
    level: number;
    enabled?: boolean; // Made optional with default value
}

export function useImageListQuery({ sessionName, parentId, pageSize, level, enabled = true }: PagedImagesOptions) {
    // Auto-enable when we have the required data
    const shouldEnable = enabled && (
        (// First level needs session
        ((level === 0 && sessionName !== '') || (level > 0 && parentId !== null)))       // Other levels need parent
    );

    return useInfiniteQuery<PagedImageResponse>({
        queryKey: ['images', sessionName, parentId, pageSize],
        queryFn: ({ pageParam }) =>
            fetchImagesPage(sessionName, parentId, pageParam as number, pageSize),
        initialPageParam: 1,
        getNextPageParam: (lastPage) => lastPage.next_page ?? undefined,
        retry: 3,
        enabled: shouldEnable,
        refetchOnMount: true,
        refetchOnWindowFocus: false,
    });
}

const ALL_LEVELS_PAGE_SIZE = 1000;

/** Every image of a session, at any level, for the Grid, Tree and Table layouts. */
export function useAllSessionImages(sessionName: string, enabled = true) {
    const { data, isLoading, isError, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery<PagedImageResponse>({
        queryKey: ['images', sessionName, 'all-levels'],
        queryFn: ({ pageParam }) =>
            fetchImagesPage(sessionName, null, pageParam as number, ALL_LEVELS_PAGE_SIZE, true),
        initialPageParam: 1,
        getNextPageParam: (lastPage) => lastPage.next_page ?? undefined,
        enabled: enabled && sessionName !== '',
        refetchOnWindowFocus: false,
    });

    useEffect(() => {
        if (hasNextPage && !isFetchingNextPage && !isError) fetchNextPage();
    }, [hasNextPage, isFetchingNextPage, isError, fetchNextPage]);

    const images = useMemo<ImageInfoDto[]>(() => data?.pages.flatMap((page) => page.result ?? []) ?? [], [data]);

    return { images, isLoading, isError, isLoadingMore: !!hasNextPage };
}
