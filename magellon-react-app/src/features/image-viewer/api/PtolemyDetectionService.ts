import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export type PtolemyDetectionMode = 'square' | 'hole';

export interface PtolemyDispatchResponse {
    job_id: string;
    task_id: string;
    queue_name: string;
    image_path: string;
    category: string;
    status: string;
}

export interface PtolemyDispatchRequest {
    image_path: string;
    image_id?: string;
    session_name?: string;
}

const ROUTES: Record<PtolemyDetectionMode, string> = {
    square: '/image/ptolemy/square/dispatch',
    hole: '/image/ptolemy/hole/dispatch',
};

export function dispatchPtolemyDetection(
    mode: PtolemyDetectionMode,
    request: PtolemyDispatchRequest,
) {
    return apiClient.post<PtolemyDispatchResponse>(ROUTES[mode], request);
}
