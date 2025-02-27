// src/components/GalleryGridView.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { 
  Box, 
  Breadcrumbs, 
  Link, 
  Typography, 
  CircularProgress, 
  ImageList, 
  Alert,
  Button
} from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useImageGalleryStore } from '../stores/useImageGalleryStore';
import { GalleryThumbnail } from './GalleryThumbnail';
import { useInfiniteQuery } from 'react-query';
import { fetchImagesPage } from '../services/api/imagesApiReactQuery';
import ImageInfoDto from '../types/ImageInfoDto';
import { match } from 'match-sorter';

interface GalleryGridViewProps {
  thumbnailSize?: 'small' | 'medium' | 'large';
  onImageSelect?: (image: ImageInfoDto) => void;
  searchTerm?: string;
}

interface BreadcrumbItem {
  id: string;
  label: string;
}

export const GalleryGridView: React.FC<GalleryGridViewProps> = ({
  thumbnailSize = 'medium',
  onImageSelect,
  searchTerm = '',
}) => {
  const { sessionName } = useImageGalleryStore();
  const [currentPath, setCurrentPath] = useState<BreadcrumbItem[]>([]);
  const [currentParentId, setCurrentParentId] = useState<string | null>(null);
  const [currentLevel, setCurrentLevel] = useState<number>(0);
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery(
    ['gallery-grid', sessionName, currentParentId, currentLevel],
    ({ pageParam = 1 }) => fetchImagesPage(sessionName, currentParentId, pageParam, 50),
    {
      getNextPageParam: (lastPage) => lastPage.next_page || undefined,
      enabled: !!sessionName,
    }
  );

  // Reset path when session changes
  useEffect(() => {
    setCurrentPath([]);
    setCurrentParentId(null);
    setCurrentLevel(0);
    setSelectedImageId(null);
  }, [sessionName]);

  // Flatten all images from all pages
  const allImages = React.useMemo(() => {
    if (!data) return [];
    return data.pages.flatMap(page => page.result);
  }, [data]);

  // Filter images by search term if needed
  const filteredImages = React.useMemo(() => {
    if (!searchTerm || !allImages.length) return allImages;
    
    return match(allImages, searchTerm, { keys: ['name'] });
  }, [allImages, searchTerm]);
  
  // Handle image click
  const handleImageClick = useCallback((image: ImageInfoDto) => {
    setSelectedImageId(image.oid);
    
    if (onImageSelect) {
      onImageSelect(image);
    }
    
    // If image has children, navigate to it
    if ((image.children_count || 0) > 0) {
      setCurrentPath((prev) => [
        ...prev, 
        { 
          id: image.oid, 
          label: image.name || `Level ${currentLevel + 1}`
        }
      ]);
      setCurrentParentId(image.oid);
      setCurrentLevel((prev) => prev + 1);
    }
  }, [currentLevel, onImageSelect]);
  
  // Handle breadcrumb navigation
  const handleBreadcrumbClick = useCallback((index: number) => {
    // If clicking the current path, do nothing
    if (index === currentPath.length - 1) return;
    
    // If clicking the root (index -1), reset to initial state
    if (index === -1) {
      setCurrentPath([]);
      setCurrentParentId(null);
      setCurrentLevel(0);
      return;
    }
    
    // Otherwise, navigate to the selected breadcrumb
    const newPath = currentPath.slice(0, index + 1);
    setCurrentPath(newPath);
    setCurrentParentId(newPath[newPath.length - 1]?.id || null);
    setCurrentLevel(index + 1);
  }, [currentPath]);
  
  // Handle "go back" action
  const handleGoBack = useCallback(() => {
    if (currentPath.length === 0) return;
    
    const newPath = currentPath.slice(0, -1);
    setCurrentPath(newPath);
    setCurrentParentId(newPath[newPath.length - 1]?.id || null);
    setCurrentLevel((prev) => prev - 1);
  }, [currentPath]);
  
  // Calculate grid columns based on thumbnail size
  const gridCols = {
    small: { xs: 2, sm: 3, md: 4, lg: 6, xl: 8 },
    medium: { xs: 1, sm: 2, md: 3, lg: 4, xl: 6 },
    large: { xs: 1, sm: 2, md: 2, lg: 3, xl: 4 },
  }[thumbnailSize];
  
  if (!sessionName) {
    return (
      <Box p={3} textAlign="center">
        <Typography variant="subtitle1">
          Please select a session to view images
        </Typography>
      </Box>
    );
  }
  
  return (
    <Box sx={{ width: '100%', height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Breadcrumb Navigation */}
      <Box sx={{ p: 1, backgroundColor: 'background.paper' }}>
        <Breadcrumbs 
          separator={<NavigateNextIcon fontSize="small" />}
          aria-label="gallery navigation"
        >
          <Link
            component="button"
            variant="body2"
            onClick={() => handleBreadcrumbClick(-1)}
            color={currentPath.length === 0 ? 'primary' : 'inherit'}
            underline="hover"
          >
            Root
          </Link>
          
          {currentPath.map((item, index) => (
            <Link
              key={item.id}
              component="button"
              variant="body2"
              onClick={() => handleBreadcrumbClick(index)}
              color={index === currentPath.length - 1 ? 'primary' : 'inherit'}
              underline="hover"
            >
              {item.label}
            </Link>
          ))}
        </Breadcrumbs>
        
        {currentPath.length > 0 && (
          <Button 
            startIcon={<ArrowBackIcon />}
            onClick={handleGoBack}
            size="small"
            sx={{ mt: 1 }}
          >
            Go Back
          </Button>
        )}
      </Box>
      
      {/* Main Content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {isLoading && !allImages.length ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : isError ? (
          <Alert severity="error">
            Error loading images: {error?.message || 'Unknown error'}
          </Alert>
        ) : filteredImages.length === 0 ? (
          <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ p: 4 }}>
            {searchTerm ? 'No matching images found' : 'No images available at this level'}
          </Typography>
        ) : (
          <>
            <ImageList
              cols={{ xs: gridCols.xs, sm: gridCols.sm, md: gridCols.md, lg: gridCols.lg, xl: gridCols.xl }}
              gap={16}
            >
              {filteredImages.map((image) => (
                <GalleryThumbnail
                  key={image.oid}
                  image={image}
                  isSelected={image.oid === selectedImageId}
                  onImageClick={handleImageClick}
                  size={thumbnailSize}
                  showDetails
                />
              ))}
            </ImageList>
            
            {hasNextPage && (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                <Button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  variant="outlined"
                >
                  {isFetchingNextPage ? 'Loading more...' : 'Load More'}
                </Button>
              </Box>
            )}
          </>
        )}
      </Box>
    </Box>
  );
};
