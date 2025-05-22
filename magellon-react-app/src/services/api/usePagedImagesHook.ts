import {useInfiniteQuery} from "react-query";
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import {PagedImageResponse} from "../../components/features/session_viewer/ImageInfoDto.ts";


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
        (level === 0 && sessionName !== '') || // First level needs session
        (level > 0 && parentId !== null)       // Other levels need parent
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
            // Add the onSuccess callback here
            onSuccess: (data) => {
                // This code will run after data has been successfully loaded
                console.log(`Data loaded successfully for level ${level}:`, data);
            },
            // Add onError callback for better error handling
            onError: (error) => {
                console.error(`Error loading data for level ${level}:`, error);
            },
            // Refetch when dependencies change
            refetchOnMount: true,
            refetchOnWindowFocus: false, // Disable refetch on window focus for better UX
        }
    );
}