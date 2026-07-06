/** A picker-backend preview result, as returned by /particle-picking/preview. */
export interface PreviewResult {
    preview_id?: string;
    num_particles?: number;
    particles?: Array<{ x: number; y: number }>;
    image_shape?: [number, number];
    image_binning?: number;
    target_pixel_size?: number;
}
