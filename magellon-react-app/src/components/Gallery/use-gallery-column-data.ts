// src/hooks/useGalleryColumnData.ts
import { useEffect } from 'react';
import { useInfiniteQuery } from 'react-query';
import { fetchImagesPage } from '../services/api/imagesApiReactQuery';
import { useImageGalleryStore } from '../stores/useImageGalleryStore';

interface GalleryColumnDataProps {
  columnIndex: number;
  parentId: string | null;
  level: number;
  pageSize?: number;
}

export const useGalleryColumnData = ({
  columnIndex,
  parentId,
  level,
  pageSize = 50
}: GalleryColumnDataProps) => {
  const { 
    sessionName, 
    updateColumnImages, 
    updateColumnLoading, 
    updateColumnError 
  } = useImageGalleryStore();

  const {
    data,
    error,
    isLoading,
    isSuccess,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    refetch
  } = useInfiniteQuery(
    ['gallery-images', sessionName, parentId, level, pageSize],
    ({ pageParam = 1 }) => fetchImagesPage(sessionName, parentId, pageParam, pageSize),
    {
      getNextPageParam: (lastPage) => lastPage.next_page || undefined,
      enabled: !!sessionName && (parentId !== null || level === 0),
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 2,
    }
  );

  // Update the store when data changes
  useEffect(() => {
    if (isSuccess && data) {
      updateColumnImages(columnIndex, data);
    }
  }, [data, isSuccess, columnIndex, updateColumnImages]);

  // Update loading state
  useEffect(() => {
    updateColumnLoading(columnIndex, isLoading);
  }, [isLoading, columnIndex, updateColumnLoading]);

  // Update error state
  useEffect(() => {
    if (error) {
      updateColumnError(columnIndex, error as Error);
    }
  }, [error, columnIndex, updateColumnError]);

  return {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch
  };
};
