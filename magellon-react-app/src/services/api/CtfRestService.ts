import {settings} from "../../core/settings.ts";
import {useQuery} from "react-query";


const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;

export function fetchImageCtfInfo(img_name: string) {
    const token = localStorage.getItem('access_token');

    return fetch(`${BASE_URL}/ctf-info?image_name_or_oid=${encodeURIComponent(img_name)}`, {
        headers: {
            'Authorization': token ? `Bearer ${token}` : '',
            'Content-Type': 'application/json',
        },
    }).then((response) => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    });
}


export function useFetchImageCtfInfo(img_name: string,enabled: boolean) {
    return useQuery(['image_ctf_info', img_name], () => fetchImageCtfInfo(img_name),{enabled:enabled});
}
