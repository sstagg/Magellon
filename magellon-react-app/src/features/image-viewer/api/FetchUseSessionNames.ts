import {useQuery} from "@tanstack/react-query";
import {settings} from "../../../shared/config/settings.ts";
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { toApiError } from '../../../shared/api/apiError.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export async function FetchSessionNames() {
    try {
        const response = await apiClient.get(`${BASE_URL}/sessions`);
        return response.data;
    } catch (error) {
        const err = toApiError(error);
        if (err.status === 401) {
            throw new Error('Please login to view sessions');
        } else if (err.status === 403) {
            throw new Error('You do not have permission to view sessions');
        }
        throw new Error(err.detail || 'Failed to load sessions');
    }
}

export function useSessionNames() {
    return useQuery({ queryKey: ['sessionNames'], queryFn: () => FetchSessionNames() });
}



