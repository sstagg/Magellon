import {useMutation} from "react-query";
import {settings} from "../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;


export const createParticlePickingEntity = async (metaName: string, imageName: string) => {
    const response = await fetch(`${BASE_URL}/create_ppmd/?meta_name=${metaName}&image_name_or_oid=${imageName}`, {
        method: 'POST',
        // Add headers if necessary
    });

    if (!response.ok) {
        throw new Error('Failed to create entity');
    }

    return response.json();
};
export function useCreateParticlePickingMutation() {
    return useMutation((data: { metaName: string; imageName: string }) => createParticlePickingEntity(data.metaName, data.imageName));
}