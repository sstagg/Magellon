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

export interface JobStatus {
    job_id: string;
    plugin_id: string;
    name: string;
    status: string;
    progress: number;
    started_at: string | null;
}

export interface PtolemyDetection {
    /** Vertex coordinates as [[y0,x0],[y1,x1],...] in MRC pixel space */
    vertices: number[][];
    /** Center as [y, x] in MRC pixel space */
    center: number[];
    area: number;
    score: number;
    brightness?: number;
}

export interface DetectionResult {
    category: string;
    detections: PtolemyDetection[];
    /** [height, width] of the source MRC image */
    image_shape?: number[];
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

export function getJobStatus(jobId: string) {
    return apiClient.get<JobStatus>(`/image/jobs/${jobId}`);
}

export function getImageDetections(imageId: string) {
    return apiClient.get<DetectionResult>(`/image/${imageId}/detections`);
}
