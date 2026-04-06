import {settings} from "../../../shared/config/settings.ts";
import {useQuery} from "react-query";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

export async function fetchImageCtfInfo(img_name: string) {
    const token = localStorage.getItem('access_token');

    const response = await fetch(`${BASE_URL}/ctf-info?image_name_or_oid=${encodeURIComponent(img_name)}`, {
        headers: {
            'Authorization': token ? `Bearer ${token}` : '',
            'Content-Type': 'application/json',
        },
    });

    // 404 means no CTF data for this image — not an error
    if (response.status === 404) {
        return null;
    }

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
}

export function useFetchImageCtfInfo(img_name: string, enabled: boolean) {
    return useQuery(
        ['image_ctf_info', img_name],
        () => fetchImageCtfInfo(img_name),
        {
            enabled,
            retry: (failureCount, error) => {
                // Don't retry on 404
                if (error instanceof Error && error.message.includes('404')) return false;
                return failureCount < 2;
            },
        }
    );
}
