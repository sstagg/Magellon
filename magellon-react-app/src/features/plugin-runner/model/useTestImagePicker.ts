import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { imagePixelSizeFor, templatePixelSizeFor } from './pluginPresets.ts';

interface UseTestImagePickerArgs {
    pluginId: string;
    /** Schema key that holds the single test-image path, if any. */
    imagePathField: string | null;
    /** Schema key that holds the template-path list, if any. */
    templatePathsField: string | null;
    setValues: Dispatch<SetStateAction<Record<string, unknown>>>;
}

/**
 * Test-image / template picking state for the plugin runner: dialog
 * visibility, the picked path(s) mirrored into the form values, and
 * the "last directory" memory that seeds each picker dialog.
 */
export const useTestImagePicker = ({
    pluginId,
    imagePathField,
    templatePathsField,
    setValues,
}: UseTestImagePickerArgs) => {
    const [imagePickerOpen, setImagePickerOpen] = useState(false);
    const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
    const [pickedPath, setPickedPath] = useState<string | null>(null);
    const [lastImageDir, setLastImageDir] = useState<string | null>(null);
    const [lastTemplateDir, setLastTemplateDir] = useState<string | null>(null);

    const handlePickImage = (path: string) => {
        setPickedPath(path);
        setValues((prev) => {
            const next = { ...prev };
            if (imagePathField) next[imagePathField] = path;
            const apix = imagePixelSizeFor(pluginId, path);
            if (apix != null) next['image_pixel_size'] = apix;
            return next;
        });
    };

    const handlePickTemplates = (paths: string[]) => {
        if (!templatePathsField) return;
        setValues((prev) => {
            const replaced = Array.from(new Set(paths));
            const next: Record<string, unknown> = { ...prev, [templatePathsField]: replaced };
            const apix = templatePixelSizeFor(pluginId, paths);
            if (apix != null) next['template_pixel_size'] = apix;
            return next;
        });
    };

    return {
        imagePickerOpen,
        setImagePickerOpen,
        templatePickerOpen,
        setTemplatePickerOpen,
        pickedPath,
        setPickedPath,
        setLastImageDir,
        setLastTemplateDir,
        imagePickerInitialPath: lastImageDir ?? parentDir(pickedPath) ?? undefined,
        templatePickerInitialPath: lastTemplateDir ?? parentDir(pickedPath) ?? undefined,
        handlePickImage,
        handlePickTemplates,
    };
};

function parentDir(path: string | null | undefined): string | null {
    if (!path) return null;
    const norm = path.replace(/\\/g, '/');
    const idx = norm.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = norm.slice(0, idx);
    if (/^[A-Za-z]:$/.test(parent)) return `${parent  }/`;
    return parent || '/';
}
