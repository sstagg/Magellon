import React, { useState, useEffect, useMemo } from 'react';
import { Grid, Box, Typography, CircularProgress, Pagination, Badge, Chip, Stack, Button } from '@mui/material';
import ImageInfoDto, { PagedImageResponse } from './ImageInfoDto';
import { ThumbImage } from './ThumbImage';
import { InfiniteData } from 'react-query';
import { useImageViewerStore } from './store/imageViewerStore';
import ImageGridControls from './ImageGridControls';
import ImageFilterDialog, { ImageFilter } from './ImageFilterDialog';
import { FilterList } from '@mui/icons-material';

interface FlatImageViewerProps {
  images: InfiniteData<PagedImageResponse> | null;
  onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
  title?: string;
  itemsPerPage?: number;
}

/**
 * FlatImageViewerComponent displays images in a responsive grid layout
 * without a hierarchical structure.
 */
export const FlatImageViewerComponent: React.FC<FlatImageViewerProps> = ({
                                                                           images,
                                                                           onImageClick,
                                                                           title = 'Images',
                                                                           itemsPerPage = 20
                                                                         }) => {
  const [page, setPage] = useState(1);
  const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null);
  const [zoom, setZoom] = useState(50); // Default zoom level
  const [showFilterDialog, setShowFilterDialog] = useState(false);
  const [filter, setFilter] = useState<ImageFilter>({});
  const { currentImage } = useImageViewerStore();

  // Set the local selected image when the store's current image changes
  useEffect(() => {
    if (currentImage) {
      setSelectedImage(currentImage);
    }
  }, [currentImage]);

  // Extract all images from the paginated data
  const allImages = images?.pages?.flatMap(page => page.result) || [];

  // Apply filters to images
  const filteredImages = useMemo(() => {
    return allImages.filter(image => {
      // Name filter
      if (filter.name && image.name && !image.name.toLowerCase().includes(filter.name.toLowerCase())) {
        return false;
      }

      // Defocus range filter
      if (filter.defocusMin !== undefined && (image.defocus === undefined || image.defocus < filter.defocusMin)) {
        return false;
      }

      if (filter.defocusMax !== undefined && (image.defocus === undefined || image.defocus > filter.defocusMax)) {
        return false;
      }

      // Magnification filter
      if (filter.magnification !== undefined && image.mag !== filter.magnification) {
        return false;
      }

      // Pixel size range filter
      if (filter.pixelSizeMin !== undefined && (image.pixelSize === undefined || image.pixelSize < filter.pixelSizeMin)) {
        return false;
      }

      if (filter.pixelSizeMax !== undefined && (image.pixelSize === undefined || image.pixelSize > filter.pixelSizeMax)) {
        return false;
      }

      // Has children filter
      if (filter.hasChildren !== undefined && ((image.children_count || 0) > 0) !== filter.hasChildren) {
        return false;
      }

      return true;
    });
  }, [allImages, filter]);

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
    setSelectedImage(image);
    onImageClick(image, 0); // Using column 0 as it's a flat view
  };

  // Handle page change
  const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    window.scrollTo(0, 0); // Scroll to top when page changes
  };

  // Open filter dialog
  const handleOpenFilter = () => {
    setShowFilterDialog(true);
  };

  // Close filter dialog
  const handleCloseFilter = () => {
    setShowFilterDialog(false);
  };

  // Apply filter
  const handleApplyFilter = (newFilter: ImageFilter) => {
    setFilter(newFilter);
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilter({});
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

  // Count active filters for badge
  const activeFilterCount = Object.values(filter).filter(val => val !== undefined).length;

  if (!images) {
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
          <Typography color="text.secondary">No images available</Typography>
        </Box>
    );
  }

  return (
      <Box sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">{title}</Typography>

          <Button
              variant="outlined"
              size="small"
              onClick={handleOpenFilter}
              startIcon={
                <Badge badgeContent={activeFilterCount} color="primary">
                  <FilterList />
                </Badge>
              }
          >
            Filter
          </Button>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Showing {currentPageImages.length} of {filteredImages.length} images
            {filteredImages.length !== allImages.length && ` (filtered from ${allImages.length})`}
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

        {/* Active filters display */}
        {activeFilterCount > 0 && (
            <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
              {filter.name && (
                  <Chip
                      label={`Name: ${filter.name}`}
                      onDelete={() => setFilter({...filter, name: undefined})}
                      size="small"
                      color="primary"
                      variant="outlined"
                  />
              )}
              {(filter.defocusMin !== undefined || filter.defocusMax !== undefined) && (
                  <Chip
                      label={`Defocus: ${filter.defocusMin?.toFixed(2) || 'min'} - ${filter.defocusMax?.toFixed(2) || 'max'} μm`}
                      onDelete={() => setFilter({...filter, defocusMin: undefined, defocusMax: undefined})}
                      size="small"
                      color="primary"
                      variant="outlined"
                  />
              )}
              {filter.magnification && (
                  <Chip
                      label={`Mag: ${filter.magnification}x`}
                      onDelete={() => setFilter({...filter, magnification: undefined})}
                      size="small"
                      color="primary"
                      variant="outlined"
                  />
              )}
              {(filter.pixelSizeMin !== undefined || filter.pixelSizeMax !== undefined) && (
                  <Chip
                      label={`Pixel Size: ${filter.pixelSizeMin?.toFixed(2) || 'min'} - ${filter.pixelSizeMax?.toFixed(2) || 'max'} Å`}
                      onDelete={() => setFilter({...filter, pixelSizeMin: undefined, pixelSizeMax: undefined})}
                      size="small"
                      color="primary"
                      variant="outlined"
                  />
              )}
              {filter.hasChildren !== undefined && (
                  <Chip
                      label={`Has Children: ${filter.hasChildren ? 'Yes' : 'No'}`}
                      onDelete={() => setFilter({...filter, hasChildren: undefined})}
                      size="small"
                      color="primary"
                      variant="outlined"
                  />
              )}
            </Stack>
        )}

        <ImageGridControls
            zoom={zoom}
            onZoomChange={setZoom}
            onFilterClick={handleOpenFilter}
            filterCount={activeFilterCount}
        />

        {currentPageImages.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">No images match the current filters</Typography>
              <Button onClick={handleClearFilters} sx={{ mt: 2 }}>Clear Filters</Button>
            </Box>
        ) : (
            <Grid container spacing={2}>
              {currentPageImages.map((image, index) => (
                  <Grid
                      item
                      xs={gridSize.xs}
                      sm={gridSize.sm}
                      md={gridSize.md}
                      lg={gridSize.lg}
                      key={image.oid || index}
                  >
                    <Box
                        onClick={() => handleImageClick(image)}
                        sx={{
                          height: '100%',
                          display: 'flex',
                          justifyContent: 'center'
                        }}
                    >
                      <ThumbImage
                          image={image}
                          onImageClick={handleImageClick}
                          level={0}
                          isSelected={selectedImage?.oid === image.oid}
                      />
                    </Box>
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
              />
            </Box>
        )}

        {/* Filter dialog */}
        <ImageFilterDialog
            open={showFilterDialog}
            onClose={handleCloseFilter}
            onApplyFilter={handleApplyFilter}
            currentFilter={filter}
            images={allImages}
        />
      </Box>
  );
};

export default FlatImageViewerComponent;