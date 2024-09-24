import { settings } from "../../core/settings.ts";
import { useQuery } from "react-query";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

// Function to fetch image metadata from the server
export function fetchImageMetaData(imageId: string) {
    return fetch(`${BASE_URL}/images/${imageId}/metadata`)
        .then((response) => {
            if (!response.ok) {
                throw new Error("Failed to fetch image metadata");
            }
            return response.json();
        });
}

// Hook to use the fetchImageMetaData function with react-query
export function useFetchImageMetaData(imageId: string | undefined, enabled: boolean = false) {
    return useQuery(
        ['image_metadata', imageId],
        () => fetchImageMetaData(imageId as string),
        {
            enabled: !!imageId && enabled, // Only run query if `imageId` is defined and `enabled` is true
            staleTime: 5 * 60 * 1000,     // Data is fresh for 5 minutes
            retry: 1,                     // Retry once on failure
        }
    );
}