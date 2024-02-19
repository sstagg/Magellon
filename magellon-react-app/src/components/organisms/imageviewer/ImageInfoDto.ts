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
}

export interface AtlasImageDto {
    oid: string;
    name?: string;
    meta?: string;
}
export interface SessionDto {
    oid: string;
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