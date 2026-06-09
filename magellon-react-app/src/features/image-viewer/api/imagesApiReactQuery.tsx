// api/imageApi.js

import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { toApiError } from '../../../shared/api/apiError.ts';
import {settings} from '../../../shared/config/settings.ts'

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
const BASE_URL = `${settings.ConfigData.SERVER_WEB_API_URL }/images`;

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
                parentId,
                page,
                pageSize,
            },
        });

        return response.data;
    } catch (error) {
        // Handle 401/403 errors with better messages
        const err = toApiError(error);
        if (err.status === 401) {
            throw new Error('Please login to view images');
        } else if (err.status === 403) {
            throw new Error('You do not have permission to view images');
        }
        throw new Error(err.detail || 'Failed to load images');
    }
};