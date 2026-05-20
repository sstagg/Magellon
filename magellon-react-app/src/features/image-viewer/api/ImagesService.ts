
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


export const useInfiniteImages=(
                                    sessionName: string,
                                    parentId: string | null,
                                    _page: number,
                                    pageSize: number
                                )=>
    {
        const {
            data: _data,
            error: _error,
            isLoading: _isLoading,
            isSuccess: _isSuccess,
            isError: _isError,
            fetchNextPage: _fetchNextPage,
            hasNextPage: _hasNextPage,
            isFetching: _isFetching,
            isFetchingNextPage: _isFetchingNextPage,
            status: _status,
        } =
            useInfiniteQuery<PagedImageResponse>(
                ['images', sessionName, parentId,  pageSize],
                ({ pageParam = _page }) => fetchImagesPage(sessionName, parentId, pageParam, pageSize),
                {
                    getNextPageParam: (lastPage, _allPages) => {
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