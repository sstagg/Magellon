import React, { createContext, useContext } from 'react';
import ImageInfoDto from '../../../entities/image/types.ts';
import { SelectChangeEvent } from '@mui/material';
import { useImageNavigation } from './useImageNavigation.ts';

interface ImageNavigationContextType {
    handleImageClick: (image: ImageInfoDto, columnIndex: number) => void;
    handleSessionSelect: (event: SelectChangeEvent) => void;
    navigateUp: () => void;
    resetNavigation: () => void;
}

const ImageNavigationCtx = createContext<ImageNavigationContextType | null>(null);

export const ImageNavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const navigation = useImageNavigation();
    return (
        <ImageNavigationCtx.Provider value={navigation}>
            {children}
        </ImageNavigationCtx.Provider>
    );
};

export const useImageNavigationContext = (): ImageNavigationContextType => {
    const ctx = useContext(ImageNavigationCtx);
    if (!ctx) {
        throw new Error('useImageNavigationContext must be used within ImageNavigationProvider');
    }
    return ctx;
};
