/**
 * Authenticated Atlas Image Component
 * Renders an atlas image with authentication
 */

import React from 'react';
import { Skeleton } from '@mui/material';
import { useAuthenticatedImage } from '../../../../hooks/useAuthenticatedImage';

interface AuthenticatedAtlasImageProps {
  atlasName: string;
  sessionName: string;
  alt: string;
  style?: React.CSSProperties;
  onError?: () => void;
  baseUrl: string;
}

export const AuthenticatedAtlasImage: React.FC<AuthenticatedAtlasImageProps> = ({
  atlasName,
  sessionName,
  alt,
  style,
  onError,
  baseUrl
}) => {
  const apiUrl = `${baseUrl}/atlas-image?name=${atlasName}&sessionName=${sessionName}`;
  const { imageUrl, isLoading, error } = useAuthenticatedImage(apiUrl);

  // Handle error callback
  React.useEffect(() => {
    if (error && onError) {
      onError();
    }
  }, [error, onError]);

  if (isLoading) {
    return <Skeleton variant="rectangular" width="100%" height="100%" />;
  }

  if (error || !imageUrl) {
    return null; // Hide image on error (handled by onError callback)
  }

  return (
    <img
      src={imageUrl}
      alt={alt}
      style={style}
    />
  );
};
