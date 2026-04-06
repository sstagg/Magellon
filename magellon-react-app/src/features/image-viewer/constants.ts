/**
 * Shared constants for the image-viewer feature.
 * Centralizes magic numbers and configuration values.
 */

/** Column layout */
export const COLUMN_HEIGHT_THRESHOLD = 700;
export const DEFAULT_PAGE_SIZE = 50;
export const TILE_WIDTH = 120;

/** Image display */
export const IMAGE_SIZE_DESKTOP = 1024;
export const IMAGE_SIZE_MOBILE = 300;

/** Particle picking defaults */
export const DEFAULT_PARTICLE_RADIUS = 15;
export const DEFAULT_BRUSH_SIZE = 30;
export const DEFAULT_PARTICLE_OPACITY = 0.8;

/** Grid gallery zoom breakpoints */
export const ZOOM_BREAKPOINTS = {
    SMALL: 25,
    MEDIUM: 50,
    LARGE: 75,
} as const;

/** Thumbnail size presets (width x height) */
export const THUMBNAIL_SIZES = {
    SMALL: { width: 120, height: 120 },
    MEDIUM: { width: 150, height: 150 },
    LARGE: { width: 200, height: 200 },
} as const;

/** Image processing defaults */
export const IMAGE_PROCESSING_DEFAULTS = {
    brightness: 50,
    contrast: 50,
    scale: 1,
} as const;
