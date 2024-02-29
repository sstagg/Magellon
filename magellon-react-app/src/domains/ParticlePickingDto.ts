
export interface ParticlePickingDto {
    oid: string;
    image_id: string;
    name?: string | null;
    data?: string | null;
    data_json?: any | null; // Assuming Json is a type alias for any
    status?: number | null;
    type?: number | null;
}