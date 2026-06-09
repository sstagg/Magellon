
export interface ParticlePickingDto {
    oid: string;
    image_id: string | null;
    name?: string | null;
    data?: string | null;
    temp?: string | null;
    data_json?: unknown; // arbitrary JSON payload
    status?: number | null;
    type?: number | null;
}