import { settings } from "../../../shared/config/settings.ts";
import { useQuery } from "@tanstack/react-query";
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { toApiError } from '../../../shared/api/apiError.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

// Function to fetch image metadata from the server
export async function fetchImageMetaData(imageId: string) {
    try {
        const response = await apiClient.get(`${BASE_URL}/images/${imageId}/metadata`);
        return response.data;
    } catch (error) {
        const err = toApiError(error);
        if (err.status === 401) {
            throw new Error('Please login to view image metadata');
        } else if (err.status === 403) {
            throw new Error('You do not have permission to view image metadata');
        }
        throw new Error(err.detail || 'Failed to fetch image metadata');
    }
}

// The MotionCor command behind an image's frame alignment results
export function useFetchFaoCommand(name: string | undefined, sessionName: string, enabled: boolean = false) {
    return useQuery({
        queryKey: ['fao_command', sessionName, name],
        queryFn: async (): Promise<string | null> => {
            const response = await apiClient.get(`${BASE_URL}/fao_command`, { params: { name, sessionName } });
            return response.data.command ?? null;
        },
        enabled: !!name && !!sessionName && enabled,
        staleTime: 60 * 1000,
        retry: 1,
    });
}

// Hook to use the fetchImageMetaData function with react-query
export function useFetchImageMetaData(imageId: string | undefined, enabled: boolean = false) {
    return useQuery({
        queryKey: ['image_metadata', imageId],
        queryFn: () => fetchImageMetaData(imageId as string),
        enabled: !!imageId && enabled,
        staleTime: 5 * 60 * 1000,
        retry: 1,
    });
}