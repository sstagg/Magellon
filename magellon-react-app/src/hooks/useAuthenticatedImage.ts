/**
 * Custom hook for loading images with authentication
 *
 * This hook fetches images with the Authorization header and creates
 * a blob URL that can be used in <img> src attributes.
 */

import { useState, useEffect } from 'react';
import axios from 'axios';

interface UseAuthenticatedImageResult {
  imageUrl: string | null;
  isLoading: boolean;
  error: Error | null;
}

export const useAuthenticatedImage = (url: string | null): UseAuthenticatedImageResult => {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // Cleanup function to revoke old blob URLs
    let objectUrl: string | null = null;

    const fetchImage = async () => {
      if (!url) {
        setImageUrl(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // Get token from localStorage
        const token = localStorage.getItem('access_token');

        // Fetch the image with authentication
        const response = await axios.get(url, {
          headers: {
            Authorization: token ? `Bearer ${token}` : '',
          },
          responseType: 'blob', // Important: get response as blob
        });

        // Create a blob URL from the response
        objectUrl = URL.createObjectURL(response.data);
        setImageUrl(objectUrl);
        setIsLoading(false);
      } catch (err) {
        console.error('Failed to load authenticated image:', err);
        setError(err instanceof Error ? err : new Error('Failed to load image'));
        setIsLoading(false);
        setImageUrl(null);
      }
    };

    fetchImage();

    // Cleanup: revoke the blob URL when component unmounts or URL changes
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [url]);

  return { imageUrl, isLoading, error };
};

/**
 * Utility function to create an authenticated image URL synchronously
 * Use this when you need to fetch the image imperatively
 */
export const fetchAuthenticatedImage = async (url: string): Promise<string> => {
  const token = localStorage.getItem('access_token');

  const response = await axios.get(url, {
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
    },
    responseType: 'blob',
  });

  return URL.createObjectURL(response.data);
};
