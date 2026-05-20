
import {useInfiniteQuery, useQuery} from 'react-query';
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import {PagedImageResponse} from "../../../entities/image/types.ts";


export const useFetchImages = (
    sessionName: string,
    parentId: string | null,
    page: number,
    pageSize: number
) => {
    return useQuery(
        ['images', sessionName, parentId, page, pageSize],
        () => fetchImagesPage(sessionName, parentId, page, pageSize),
        {
            retry: 3, // Number of retries on failure (optional)

        }
    );
};


export const useInfiniteImages = (
    sessionName: string,
    parentId: string | null,
    initialPage: number,
    pageSize: number
) => {
    return useInfiniteQuery<PagedImageResponse>(
        ['images', sessionName, parentId, pageSize],
        ({ pageParam = initialPage }) => fetchImagesPage(sessionName, parentId, pageParam, pageSize),
        {
            getNextPageParam: (lastPage) => lastPage.next_page ?? undefined,
            retry: 3,
        }
    );
};