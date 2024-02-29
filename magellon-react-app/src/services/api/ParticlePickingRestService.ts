import {useMutation, useQuery} from "react-query";
import {settings} from "../../core/settings.ts";
import {FetchSessionAtlasImages} from "./FetchSessionAtlasImages.ts";
import {ParticlePickingDto} from "../../domains/ParticlePickingDto.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;


export function FetchImageParticlePicking(img_name: string) {
    return fetch(`${BASE_URL}/particle-pickings?img_name=${img_name}`).then((response) =>
        response.json()
    );
}


export function useImageParticlePickings(img_name: string,enabled: boolean) {
    return useQuery(['image_particle_picking', img_name], () => FetchImageParticlePicking(img_name),{enabled:enabled});
}



export const createParticlePickingEntity = async (metaName: string, imageName: string) => {
    const response = await fetch(`${BASE_URL}/particle-pickings?meta_name=${metaName}&image_name_or_oid=${imageName}`, {
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


async function updateParticlePicking(bodyReq: ParticlePickingDto) {
    const response = await fetch(`${BASE_URL}/particle-pickings`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(bodyReq),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail);
    }

    return response.json();
}

export function useUpdateParticlePicking() {
    return useMutation(updateParticlePicking);
}

