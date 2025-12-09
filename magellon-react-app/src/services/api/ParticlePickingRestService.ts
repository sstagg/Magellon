import {useMutation, useQuery} from "react-query";
import {settings} from "../../core/settings.ts";
import {ParticlePickingDto} from "../../domains/ParticlePickingDto.ts";
import getAxiosClient from '../../core/AxiosClient.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);


export async function FetchImageParticlePicking(img_name: string) {
    const response = await apiClient.get('/web/particle-pickings', {
        params: { img_name }
    });
    return response.data;
}


export function useImageParticlePickings(img_name: string,enabled: boolean) {
    return useQuery(['image_particle_picking', img_name], () => FetchImageParticlePicking(img_name),{enabled:enabled});
}



export const createParticlePickingEntity = async (metaName: string, imageName: string) => {
    const response = await apiClient.post('/web/particle-pickings', null, {
        params: { meta_name: metaName, image_name_or_oid: imageName }
    });
    return response.data;
};

export function useCreateParticlePickingMutation() {
    return useMutation((data: { metaName: string; imageName: string }) => createParticlePickingEntity(data.metaName, data.imageName));
}


async function updateParticlePicking(bodyReq: ParticlePickingDto) {
    const response = await apiClient.put('/web/particle-pickings', bodyReq);
    return response.data;
}

export function useUpdateParticlePicking() {
    return useMutation(updateParticlePicking);
}
