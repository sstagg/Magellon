import {useMutation, useQuery} from "react-query";
import {settings} from "../../core/settings.ts";
import getAxiosClient from '../../core/AxiosClient';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export async function FetchSessionNames() {
    try {
        const response = await apiClient.get(`${BASE_URL}/sessions`);
        return response.data;
    } catch (error: any) {
        if (error.response?.status === 401) {
            throw new Error('Please login to view sessions');
        } else if (error.response?.status === 403) {
            throw new Error('You do not have permission to view sessions');
        }
        throw new Error(error.response?.data?.detail || error.response?.data || 'Failed to load sessions');
    }
}

export function useSessionNames() {
    return useQuery(['sessionNames'], () => FetchSessionNames());
}



