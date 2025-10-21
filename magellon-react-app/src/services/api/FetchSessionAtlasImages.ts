import {useQuery} from 'react-query';
import {settings} from "../../core/settings.ts";
import getAxiosClient from '../../core/AxiosClient';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export async function FetchSessionAtlasImages(sessionName: string) {
    try {
        const response = await apiClient.get(`${BASE_URL}/atlases`, {
            params: { session_name: sessionName }
        });
        return response.data;
    } catch (error: any) {
        if (error.response?.status === 401) {
            throw new Error('Please login to view atlas images');
        } else if (error.response?.status === 403) {
            throw new Error('You do not have permission to view atlas images');
        }
        throw new Error(error.response?.data?.detail || error.response?.data || 'Failed to load atlas images');
    }
}

export function useAtlasImages(sessionName: string, enabled: boolean) {
    return useQuery(['atlasImages', sessionName], () => FetchSessionAtlasImages(sessionName), {enabled: enabled});
}



