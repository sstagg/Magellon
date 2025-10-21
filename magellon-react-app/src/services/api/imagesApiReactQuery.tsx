// api/imageApi.js

import getAxiosClient from '../../core/AxiosClient';
import {settings} from '../../core/settings.ts'

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL +'/images';

export const fetchImagesPage = async (
    sessionName: string,
    parentId: string | null,
    page: number,
    pageSize: number
) => {
    try {
        const response = await apiClient.get(BASE_URL, {
            params: {
                session_name: sessionName,
                parentId: parentId,
                page: page,
                pageSize: pageSize,
            },
        });

        return response.data;
    } catch (error: any) {
        // Handle 401/403 errors with better messages
        if (error.response?.status === 401) {
            throw new Error('Please login to view images');
        } else if (error.response?.status === 403) {
            throw new Error('You do not have permission to view images');
        }
        throw new Error(error.response?.data?.detail || error.response?.data || 'Failed to load images');
    }
};