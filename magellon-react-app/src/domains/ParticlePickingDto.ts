
export interface ParticlePickingDto {
    oid: string;
    image_id: string | null;
    name?: string | null;
    data?: string | null;
    temp?: string | null;
    data_json?: any | null; // Assuming Json is a type alias for any
    status?: number | null;
    type?: number | null;
}