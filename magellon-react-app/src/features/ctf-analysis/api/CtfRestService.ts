import {settings} from "../../../shared/config/settings.ts";
import {useQuery} from "@tanstack/react-query";
import {AxiosError} from "axios";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";

const api = getAxiosClient(settings.ConfigData.SERVER_WEB_API_URL);

export async function fetchImageCtfInfo(img_name: string) {
    try {
        const response = await api.get('/ctf-info', {
            params: {image_name_or_oid: img_name},
        });
        return response.data;
    } catch (error) {
        // 404 means no CTF data for this image — not an error.
        if (error instanceof AxiosError && error.response?.status === 404) {
            return null;
        }
        throw error;
    }
}

export function useFetchImageCtfInfo(img_name: string, enabled: boolean) {
    return useQuery({
        queryKey: ['image_ctf_info', img_name],
        queryFn: () => fetchImageCtfInfo(img_name),
        enabled,
        retry: (failureCount, error) => {
            if (error instanceof Error && error.message.includes('404')) return false;
            return failureCount < 2;
        },
    });
}
