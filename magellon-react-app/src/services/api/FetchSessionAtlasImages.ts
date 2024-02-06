import { useQuery } from 'react-query';
import {settings} from "../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;
export function FetchSessionAtlasImages(sessionName: string) {
    return fetch(`${BASE_URL}/atlases?session_name=${sessionName}`).then((response) =>
        response.json()
    );
}


export function useAtlasImages(sessionName: string) {
    return useQuery(['atlasImages', sessionName], () => FetchSessionAtlasImages(sessionName));
}