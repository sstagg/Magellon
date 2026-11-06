import type ImageInfoDto from '../../../entities/image/types.ts';

/** The image and its ancestors, top level first, from a list of a session's images. */
export const imagePath = (image: ImageInfoDto, images: ImageInfoDto[]): ImageInfoDto[] => {
    const byId = new Map(images.map((item) => [item.oid, item]));
    const path = [image];
    let parent = image.parent_id ? byId.get(image.parent_id) : undefined;
    while (parent && !path.includes(parent)) {
        path.unshift(parent);
        parent = parent.parent_id ? byId.get(parent.parent_id) : undefined;
    }
    return path;
};

/** Open an image found in a whole-session layout, selecting its path in the columns too. */
export const openImagePath = (
    image: ImageInfoDto,
    images: ImageInfoDto[],
    columnCount: number,
    onImageClick: (image: ImageInfoDto, column: number) => void,
) => {
    imagePath(image, images).forEach((item, level) => {
        onImageClick({ ...item, level }, Math.min(level, columnCount - 1));
    });
};
