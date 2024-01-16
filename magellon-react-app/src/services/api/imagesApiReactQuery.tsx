// api/imageApi.js

import axios from 'axios';
import {settings} from '../../core/settings.ts'

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL +'/images';
export const fetchImagesPage = async (
    sessionName: string,
    parentId: string | null,
    page: number,
    pageSize: number
) => {
    try {
        const response = await axios.get(BASE_URL, {
            params: {
                session_name: sessionName,
                parentId: parentId,
                page: page,
                pageSize: pageSize,
            },
        });

        return response.data;
    } catch (error) {
        throw new Error(error.response?.data || 'An error occurred');
    }
};