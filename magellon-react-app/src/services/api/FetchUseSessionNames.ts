import {useQuery} from "react-query";
import {settings} from "../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;


export function FetchSessionNames() {
    return fetch(`${BASE_URL}/sessions`).then((response) =>
        response.json()
    );
}
export function useSessionNames() {
    return useQuery(['sessionNames'], () => FetchSessionNames());
}

