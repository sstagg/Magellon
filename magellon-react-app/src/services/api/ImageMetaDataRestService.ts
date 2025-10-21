import { settings } from "../../core/settings.ts";
import { useQuery } from "react-query";
import getAxiosClient from '../../core/AxiosClient';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

// Function to fetch image metadata from the server
export async function fetchImageMetaData(imageId: string) {
    try {
        const response = await apiClient.get(`${BASE_URL}/images/${imageId}/metadata`);
        return response.data;
    } catch (error: any) {
        if (error.response?.status === 401) {
            throw new Error('Please login to view image metadata');
        } else if (error.response?.status === 403) {
            throw new Error('You do not have permission to view image metadata');
        }
        throw new Error(error.response?.data?.detail || error.response?.data || 'Failed to fetch image metadata');
    }
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