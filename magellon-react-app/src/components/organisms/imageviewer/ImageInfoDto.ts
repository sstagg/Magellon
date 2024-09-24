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


// Type for the Metadata DTO
export interface MetadataDto {
    oid: string;
    name: string;
    data: string;
    data_json?: Record<string, any>;  // Optional, as it may not always be present
}

// Type for the Category DTO
export interface CategoryDto {
    oid: string;
    name: string;
    parent?: string | null;           // Optional, and `null` if it's a top-level category
    metadata?: MetadataDto[];         // Optional, in case the category has no metadata
    children?: CategoryDto[];         // Optional, for categories with no subcategories
}

// The response type for the entire result, which is an array of top-level categories
export type ImageMetadataResponseDto = CategoryDto[];