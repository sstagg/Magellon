import type ImageInfoDto from '../../../entities/image/types.ts';
import { fetchImagePath } from '../api/imagesApiReactQuery.tsx';

type OnImageClick = (image: ImageInfoDto, column: number) => void;

/** Open an image whose ancestors are known, top level first, selecting them in the columns. */
export const openPath = (path: ImageInfoDto[], columnCount: number, onImageClick: OnImageClick) => {
    path.forEach((item, level) => onImageClick({ ...item, level }, Math.min(level, columnCount - 1)));
};

/** Open an image from a whole-session layout; its ancestors come from the server. */
export const openImageWithAncestors = async (image: ImageInfoDto, columnCount: number, onImageClick: OnImageClick) => {
    if (!image.parent_id) {
        openPath([image], columnCount, onImageClick);
        return;
    }
    try {
        const path = await fetchImagePath(image.oid);
        openPath(path.length > 0 ? path : [image], columnCount, onImageClick);
    } catch {
        openPath([image], columnCount, onImageClick);
    }
};
