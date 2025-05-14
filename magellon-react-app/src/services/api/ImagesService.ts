
import {useInfiniteQuery, useQuery} from 'react-query';
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import ImageInfoDto, {PagedImageResponse} from "../../components/features/session_viewer/ImageInfoDto.ts";


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


export const useInfiniteImages=(
                                    sessionName: string,
                                    parentId: string | null,
                                    _page: number,
                                    pageSize: number
                                )=>
    {
        const {
            data ,
            error,
            isLoading,
            isSuccess,
            isError,
            fetchNextPage,
            hasNextPage,
            isFetching,
            isFetchingNextPage,
            status,
        } =
            useInfiniteQuery<PagedImageResponse>(
                ['images', sessionName, parentId,  pageSize],
                ({ pageParam = _page }) => fetchImagesPage(sessionName, parentId, pageParam, pageSize),
                {
                    getNextPageParam: (lastPage, allPages) => {
                        if (lastPage.next_page !== null) {
                            // pageParam=lastPage.next_page;
                            return lastPage.next_page; // Return the next page number
                        }
                        return undefined; // No more pages to fetch
                    },
                    retry: 3, // Number of retries on failure (optional)
                }
            );

    };