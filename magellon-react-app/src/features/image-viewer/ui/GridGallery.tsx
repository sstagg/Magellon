import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Grid, Box, Typography, CircularProgress, Pagination, Button } from '@mui/material';
import type ImageInfoDto from '../../../entities/image/types.ts';
import { ImageThumbnail } from './ImageThumbnail.tsx';
import { useImageViewerStore } from '../model/imageViewerStore';
import ImageGridControls from './ImageGridControls';
import { useAllSessionImages } from '../api/usePagedImagesHook';
import { EMPTY_FILTER, countActiveFilters, makeImageMatcher } from '../lib/imageFilter';
import { openImagePath } from '../lib/imagePath';

interface FlatImageViewerProps {
  sessionName: string;
  onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
  title?: string;
  itemsPerPage?: number;
}

/**
 * All the images of a session, at any level, in a responsive grid: images that
 * have a parent or children come first, then the rest.
 */
export const GridGallery: React.FC<FlatImageViewerProps> = ({
                                                                           sessionName,
                                                                           onImageClick,
                                                                           title = 'Images',
                                                                           itemsPerPage = 20
                                                                         }) => {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(50); // Default zoom level
  const { currentImage, imageColumns, imageFilter: filter, setImageFilter } = useImageViewerStore();
  const { images: allImages, isLoading, isLoadingMore } = useAllSessionImages(sessionName);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filteredImages = useMemo(
    () => {
      const matches = makeImageMatcher(filter);
      return matches ? allImages.filter(matches) : allImages;
    },
    [allImages, filter]
  );

  // Calculate total pages
  const totalPages = Math.ceil(filteredImages.length / itemsPerPage);

  // Get current page's images
  const currentPageImages = filteredImages.slice(
      (page - 1) * itemsPerPage,
      page * itemsPerPage
  );

  // Reset to page 1 when filter changes
  useEffect(() => {
    setPage(1);
  }, [filter]);

  // Handle image click
  const handleImageClick = (image: ImageInfoDto) => {
    openImagePath(image, allImages, imageColumns.length, onImageClick);
  };

  // Handle page change
  const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    scrollRef.current?.scrollTo(0, 0);
  };

  // Clear all filters
  const handleClearFilters = () => {
    setImageFilter(EMPTY_FILTER);
  };

  // Map zoom level to thumbnail size
  const getThumbnailSize = (zoom: number): 'small' | 'medium' | 'large' => {
    if (zoom < 30) return 'small';
    if (zoom < 70) return 'medium';
    return 'large';
  };

  // Calculate grid size based on zoom level
  const getGridSize = (zoom: number) => {
    // Map zoom level (10-100) to grid sizes
    if (zoom < 25) return { xs: 4, sm: 3, md: 2, lg: 1 }; // Very small (many per row)
    if (zoom < 50) return { xs: 6, sm: 4, md: 3, lg: 2 }; // Small
    if (zoom < 75) return { xs: 12, sm: 6, md: 4, lg: 3 }; // Medium
    return { xs: 12, sm: 12, md: 6, lg: 4 }; // Large (few per row)
  };

  const gridSize = getGridSize(zoom);
  const thumbnailSize = getThumbnailSize(zoom);

  // Count active filters for badge
  const activeFilterCount = countActiveFilters(filter);

  if (isLoading) {
    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
          <CircularProgress />
        </Box>
    );
  }

  if (allImages.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>{title}</Typography>
        <Typography sx={{
          color: "text.secondary"
        }}>No images available</Typography>
      </Box>
    );
  }

  return (
    <Box ref={scrollRef} sx={{ p: 2, pb: 8, height: '100%', overflow: 'auto', boxSizing: 'border-box' }} data-testid="grid-gallery">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">{title}</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          Showing {currentPageImages.length} of {filteredImages.length} images
          {filteredImages.length !== allImages.length && ` (filtered from ${allImages.length})`}
          {isLoadingMore && ' (loading more...)'}
        </Typography>

        {activeFilterCount > 0 && (
            <Button
                size="small"
                color="primary"
                onClick={handleClearFilters}
            >
              Clear Filters
            </Button>
        )}
      </Box>
      <ImageGridControls
          zoom={zoom}
          onZoomChange={setZoom}
          filterCount={activeFilterCount}
          totalImages={filteredImages.length}
      />
      {currentPageImages.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography sx={{
              color: "text.secondary"
            }}>No images match the current filters</Typography>
            <Button onClick={handleClearFilters} sx={{ mt: 2 }}>Clear Filters</Button>
          </Box>
      ) : (
          <Grid container spacing={2}>
            {currentPageImages.map((image, index) => (
                <Grid
                  key={image.oid || index}
                  sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    aspectRatio: '1/1'
                  }}
                  size={{
                    xs: gridSize.xs,
                    sm: gridSize.sm,
                    md: gridSize.md,
                    lg: gridSize.lg
                  }}>
                  <ImageThumbnail
                      image={image}
                      onImageClick={handleImageClick}
                      level={0}
                      isSelected={currentImage?.oid === image.oid}
                      fixedHeight={true}
                      size={thumbnailSize}
                  />
                </Grid>
            ))}
          </Grid>
      )}
      {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <Pagination
                count={totalPages}
                page={page}
                onChange={handlePageChange}
                color="primary"
                size="medium"
                siblingCount={1}
                boundaryCount={1}
            />
          </Box>
      )}
    </Box>
  );
};

export default GridGallery;