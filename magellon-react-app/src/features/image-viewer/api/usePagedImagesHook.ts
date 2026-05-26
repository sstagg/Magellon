import {useInfiniteQuery} from "@tanstack/react-query";
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import type {PagedImageResponse} from "../../../entities/image/types.ts";


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