import { useEffect } from 'react';
import { useAtlasImages } from '../../../../services/api/FetchSessionAtlasImages';
import { useImageViewerStore } from '../store/imageViewerStore';

interface UseAtlasDataOptions {
    sessionName?: string;
    enabled?: boolean;
}

/**
 * Custom hook to manage atlas image data fetching and synchronization with store
 */
export const useAtlasData = (options: UseAtlasDataOptions = {}) => {
    const { sessionName, enabled = true } = options;

    const {
        currentSession,
        currentAtlas,
        setAtlasImages,
        setCurrentAtlas
    } = useImageViewerStore();

    // Determine session name from options or store
    const effectiveSessionName = sessionName || currentSession?.name;

    // Fetch atlas images
    const {
        data: atlasImages,
        isLoading,
        isError,
        error
    } = useAtlasImages(effectiveSessionName, enabled && effectiveSessionName !== undefined);

    // Sync atlas images with store when they change
    useEffect(() => {
        if (atlasImages) {
            setAtlasImages(atlasImages);

            // Set first atlas as current if none selected
            if (!currentAtlas && atlasImages.length > 0) {
                setCurrentAtlas(atlasImages[0]);
            }
        }
    }, [atlasImages, currentAtlas, setAtlasImages, setCurrentAtlas]);

    return {
        atlasImages,
        isLoading,
        isError,
        error
    };
};
