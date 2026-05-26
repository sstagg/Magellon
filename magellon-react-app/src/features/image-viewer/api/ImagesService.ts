
import {useInfiniteQuery, useQuery} from '@tanstack/react-query';
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import type {PagedImageResponse} from "../../../entities/image/types.ts";


export const useFetchImages = (
    sessionName: string,
    parentId: string | null,
    page: number,
    pageSize: number
) => {
    return useQuery({
        queryKey: ['images', sessionName, parentId, page, pageSize],
        queryFn: () => fetchImagesPage(sessionName, parentId, page, pageSize),
        retry: 3,
    });
};


export const useInfiniteImages = (
    sessionName: string,
    parentId: string | null,
    initialPage: number,
    pageSize: number
) => {
    return useInfiniteQuery<PagedImageResponse>({
        queryKey: ['images', sessionName, parentId, pageSize],
        queryFn: ({ pageParam }) =>
            fetchImagesPage(sessionName, parentId, pageParam as number, pageSize),
        initialPageParam: initialPage,
        getNextPageParam: (lastPage) => lastPage.next_page ?? undefined,
        retry: 3,
    });
};