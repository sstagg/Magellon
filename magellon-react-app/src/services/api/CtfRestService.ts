import {settings} from "../../core/settings.ts";
import {useQuery} from "react-query";


const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;

// export function fetchImageCtfInfo(img_name: string) {
//     return axios.get(`${BASE_URL}/ctf-info`, {
//         params: { img_name } // Automatically converts to query string
//     }).then(response => response.data); // Automatically parses JSON
// }

export function fetchImageCtfInfo(img_name: string) {
    return fetch(`${BASE_URL}/ctf-info?image_name_or_oid=${img_name}`).then((response) =>
        response.json()
    );
}


export function useFetchImageCtfInfo(img_name: string,enabled: boolean) {
    return useQuery(['image_ctf_info', img_name], () => fetchImageCtfInfo(img_name),{enabled:enabled});
}
