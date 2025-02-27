// src/components/GalleryColumn.tsx
import React, { useCallback, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import InfiniteLoader from 'react-window-infinite-loader';
import AutoSizer from 'react-virtualized-auto-sizer';
import { CircularProgress, Paper, Typography, Box, Alert } from '@mui/material';
import { GalleryThumbnail } from './GalleryThumbnail';
import { useGalleryColumnData } from '../hooks/useGalleryColumnData';
import { useImageGalleryStore } from '../stores/useImageGalleryStore';
import ImageInfoDto from '../types/ImageInfoDto';

interface GalleryColumnProps {
  columnIndex: number;
  width?: number;
  height?: number;
  thumbnailSize?: 'small' | 'medium' | 'large';
}

export const GalleryColumn: React.FC<GalleryColumnProps> = ({
  columnIndex,
  width = 200,
  height = 600,
  thumbnailSize = 'medium',
}) => {
  // Get column data from store
  const { columns, selectImage, orientation } = useImageGalleryStore();
  const column = columns[columnIndex];
  
  if (!column) {
    return null;
  }
  
  // Fetch data for this column
  const { isLoading, error, fetchNextPage, isFetchingNextPage } = useGalleryColumnData({
    columnIndex,
    parentId: column.parentId,
    level: column.level,
  });
  
  // Flatten all pages of images from InfiniteData
  const allImages = useMemo(() => {
    if (!column.images) return [];
    
    return column.images.pages.flatMap(page => page.result);
  }, [column.images]);
  
  // Item count for InfiniteLoader
  const itemCount = column.hasMore
    ? allImages.length + 1 // Add 1 for loading more indicator
    : allImages.length;
  
  // Check if an item is loaded
  const isItemLoaded = useCallback(
    (index: number) => !column.hasMore || index < allImages.length,
    [column.hasMore, allImages.length]
  );
  
  // Load more items
  const loadMoreItems = useCallback(
    (startIndex: number, stopIndex: number) => {
      if (isFetchingNextPage) return Promise.resolve();
      return fetchNextPage().then(() => {});
    },
    [fetchNextPage, isFetchingNextPage]
  );
  
  // Handle image selection
  const handleImageClick = useCallback(
    (image: ImageInfoDto) => {
      selectImage(columnIndex, image.oid, (image.children_count || 0) > 0);
    },
    [columnIndex, selectImage]
  );
  
  // Render an individual item
  const renderItem = useCallback(
    ({ index, style }) => {
      // If we're rendering the loading indicator
      if (!isItemLoaded(index)) {
        return (
          <Box style={style} display="flex" justifyContent="center" alignItems="center">
            <CircularProgress size={24} />
          </Box>
        );
      }
      
      // Otherwise render the image
      const image = allImages[index];
      
      return (
        <div style={style}>
          <GalleryThumbnail
            key={image.oid}
            image={image}
            isSelected={column.selectedImageId === image.oid}
            onImageClick={handleImageClick}
            size={thumbnailSize}
            showDetails={true}
          />
        </div>
      );
    },
    [allImages, column.selectedImageId, handleImageClick, isItemLoaded, thumbnailSize]
  );
  
  // Size configuration based on orientation and thumbnail size
  const sizes = {
    small: { width: 130, height: 130 },
    medium: { width: 180, height: 180 },
    large: { width: 230, height: 230 },
  };
  
  const itemSize = sizes[thumbnailSize].height;
  
  if (isLoading && !allImages.length) {
    return (
      <Paper 
        elevation={2} 
        sx={{ 
          width, 
          height, 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" sx={{ mt: 2 }}>
          Loading {column.caption}...
        </Typography>
      </Paper>
    );
  }
  
  if (error) {
    return (
      <Paper 
        elevation={2} 
        sx={{ 
          width, 
          height, 
          p: 2,
        }}
      >
        <Alert severity="error">
          Error loading {column.caption}: {error.message}
        </Alert>
      </Paper>
    );
  }
  
  if (!column.images || allImages.length === 0) {
    return (
      <Paper 
        elevation={2} 
        sx={{ 
          width, 
          height, 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: 2,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {column.parentId ? 'No images available' : 'Select a parent image'}
        </Typography>
      </Paper>
    );
  }
  
  return (
    <Paper 
      elevation={2} 
      sx={{ 
        width, 
        height, 
        display: 'flex', 
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Typography variant="subtitle1" sx={{ p: 1, fontWeight: 'bold' }}>
        {column.caption} ({allImages.length})
      </Typography>
      
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        <AutoSizer>
          {({ width: autoWidth, height: autoHeight }) => (
            <InfiniteLoader
              isItemLoaded={isItemLoaded}
              itemCount={itemCount}
              loadMoreItems={loadMoreItems}
              threshold={5}
            >
              {({ onItemsRendered, ref }) => (
                <List
                  ref={ref}
                  width={autoWidth}
                  height={autoHeight}
                  itemCount={itemCount}
                  itemSize={itemSize}
                  onItemsRendered={onItemsRendered}
                >
                  {renderItem}
                </List>
              )}
            </InfiniteLoader>
          )}
        </AutoSizer>
      </Box>
    </Paper>
  );
};
