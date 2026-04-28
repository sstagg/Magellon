import {useInfiniteQuery} from "react-query";
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import {PagedImageResponse} from "../../../entities/image/types.ts";


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

    return useInfiniteQuery<PagedImageResponse>(
        ['images', sessionName, parentId, pageSize],
        ({ pageParam = 1 }) => fetchImagesPage(sessionName, parentId, pageParam, pageSize),
        {
            getNextPageParam: (lastPage, allPages) => {
                if (lastPage.next_page !== null) {
                    return lastPage.next_page; // Return the next page number
                }
                return undefined; // No more pages to fetch
            },
            retry: 3, // Number of retries on failure (optional)
            enabled: shouldEnable, // Auto-enable based on available data
            // Refetch when dependencies change
            refetchOnMount: true,
            refetchOnWindowFocus: false, // Disable refetch on window focus for better UX
        }
    );
}