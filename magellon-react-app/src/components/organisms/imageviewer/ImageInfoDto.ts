// import { UUID } from 'uuid';
interface ImageInfoDto {
    oid: string;
    name?: string;
    defocus?: number;
    dose?: number;
    mag: number;
    pixelSize?: number;
    parent_id?: string;
    session_id?: string;
    children_count?: number;
    selected?: boolean;
    level?: number;
    //ctf?: ImageCtfInfo;
}
export interface ImageCtfInfo {
    defocus1: number | null;               // Defocus 1 value in μm, can be a number or null
    defocus2: number | null;               // Defocus 2 value in μm, can be a number or null
    angleAstigmatism: number | null;       // Angle astigmatism in degrees, can be a number or null
    resolution: number | null;              // Resolution 50% value in Å, can be a number or null
}
export interface AtlasImageDto {
    oid: string;
    name?: string;
    meta?: string;
}
export interface SessionDto {
    Oid: string;
    name?: string;
}
export interface PagedImageResponse {
    total_count: number;
    page: number;
    pageSize: number;
    next_page: number | null;
    result:  ImageInfoDto[]; // Replace with the actual type for `images_as_dict`
}
export default ImageInfoDto;


