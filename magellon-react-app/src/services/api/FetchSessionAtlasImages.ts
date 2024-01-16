import { useQuery } from 'react-query';

export function FetchSessionAtlasImages(sessionName: string) {
    return fetch(`http://127.0.0.1:8000/web/atlases?session_name=${sessionName}`).then((response) =>
        response.json()
    );
}


export function useAtlasImages(sessionName: string) {
    return useQuery(['atlasImages', sessionName], () => FetchSessionAtlasImages(sessionName));
}