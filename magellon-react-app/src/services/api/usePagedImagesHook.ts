import {useInfiniteQuery} from "react-query";
import {fetchImagesPage} from "./imagesApiReactQuery.tsx";
import {PagedImageResponse} from "../../components/features/session_viewer/ImageInfoDto.ts";


interface PagedImagesOptions {
    // idName: string;
    sessionName: string;
    parentId: string | null;
    pageSize: number;
    level: number;
    enabled: boolean;
}

export function usePagedImages({ sessionName, parentId, pageSize,level }: PagedImagesOptions) {
    // console.log("requested by: "  + parentId);
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
            enabled:false, //
            // Add the onSuccess callback here
            onSuccess: (data) => {
                // This code will run after data has been successfully loaded
               // console.log('Data loaded successfully:', data);

            },
        }
    );
}