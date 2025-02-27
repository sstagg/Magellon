// src/examples/ExampleUsage.tsx
import React, { useState } from 'react';
import { 
  Box, 
  Container, 
  Grid, 
  Paper, 
  Tabs, 
  Tab, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem,
  TextField,
  IconButton,
  InputAdornment
} from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ImageGallery } from './ImageGallery';
import { GalleryGridView } from './GalleryGridView';
import { SoloImageViewerComponent } from './imageviewer/SoloImageViewerComponent';
import { useImageGalleryStore } from './useImageGalleryStore';
import { FetchSessionNames } from '../services/api/FetchUseSessionNames';
import { useQuery } from 'react-query';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import ImageInfoDto from '../types/ImageInfoDto';
import '../styles/GalleryStyles.scss';

// Create a new query client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

enum ViewMode {
  COLUMNS = 'columns',
  GRID = 'grid',
}

// Main component that uses our gallery
export const ImageGalleryExample: React.FC = () => {
  // State for the example
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.COLUMNS);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null);
  
  // Get session name from store
  const { sessionName, setSessionName } = useImageGalleryStore();
  
  // Fetch sessions
  const { data: sessions, isLoading } = useQuery('sessions', FetchSessionNames);
  
  // Handle session change
  const handleSessionChange = (event: React.ChangeEvent<{ value: unknown }>) => {
    setSessionName(event.target.value as string);
  };
  
  // Handle view mode change
  const handleViewModeChange = (event: React.SyntheticEvent, newValue: ViewMode) => {
    setViewMode(newValue);
  };
  
  // Handle search
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };
  
  // Clear search
  const handleClearSearch = () => {
    setSearchTerm('');
  };
  
  // Handle image selection (used in grid view)
  const handleImageSelect = (image: ImageInfoDto) => {
    setSelectedImage(image);
  };
  
  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* Header with controls */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <FormControl fullWidth>
            <InputLabel id="session-select-label">Select Session</InputLabel>
            <Select
              labelId="session-select-label"
              id="session-select"
              value={sessionName || ''}
              label="Select Session"
              onChange={handleSessionChange}
              disabled={isLoading}
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {sessions?.map((session) => (
                <MenuItem key={session.Oid} value={session.name}>
                  {session.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <TextField
            fullWidth
            placeholder="Search images..."
            value={searchTerm}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
              endAdornment: searchTerm && (
                <InputAdornment position="end">
                  <IconButton onClick={handleClearSearch} edge="end" size="small">
                    <ClearIcon />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Tabs
            value={viewMode}
            onChange={handleViewModeChange}
            aria-label="gallery view mode"
            variant="fullWidth"
          >
            <Tab 
              label="Column View" 
              value={ViewMode.COLUMNS} 
              id="gallery-tab-columns"
              aria-controls="gallery-tabpanel-columns"
            />
            <Tab 
              label="Grid View" 
              value={ViewMode.GRID} 
              id="gallery-tab-grid"
              aria-controls="gallery-tabpanel-grid"
            />
          </Tabs>
        </Grid>
      </Grid>
      
      {/* Main content */}
      <Grid container spacing={3}>
        {/* Left side: Gallery */}
        <Grid item xs={12} md={8}>
          <Paper 
            sx={{ 
              height: 'calc(100vh - 200px)', 
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Box
              role="tabpanel"
              hidden={viewMode !== ViewMode.COLUMNS}
              id="gallery-tabpanel-columns"
              aria-labelledby="gallery-tab-columns"
              sx={{ flex: 1 }}
            >
              {viewMode === ViewMode.COLUMNS && (
                <ImageGallery 
                  thumbnailSize="medium"
                  maxColumns={4}
                  height="100%"
                  width="100%"
                />
              )}
            </Box>
            
            <Box
              role="tabpanel"
              hidden={viewMode !== ViewMode.GRID}
              id="gallery-tabpanel-grid"
              aria-labelledby="gallery-tab-grid"
              sx={{ flex: 1 }}
            >
              {viewMode === ViewMode.GRID && (
                <GalleryGridView 
                  thumbnailSize="medium"
                  searchTerm={searchTerm}
                  onImageSelect={handleImageSelect}
                />
              )}
            </Box>
          </Paper>
        </Grid>
        
        {/* Right side: Image viewer */}
        <Grid item xs={12} md={4}>
          <Paper 
            sx={{ 
              height: 'calc(100vh - 200px)',
              overflow: 'auto',
              p: 2,
            }}
          >
            <SoloImageViewerComponent 
              selectedImage={
                viewMode === ViewMode.GRID 
                  ? selectedImage 
                  : getSelectedImageFromColumns(useImageGalleryStore.getState().columns)
              } 
            />
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

// Helper function to get the selected image from columns
function getSelectedImageFromColumns(columns) {
  // Find the deepest selected image
  for (let i = columns.length - 1; i >= 0; i--) {
    const column = columns[i];
    if (column.selectedImageId && column.images) {
      // Search through all pages
      for (const page of column.images.pages) {
        const image = page.result.find(img => img.oid === column.selectedImageId);
        if (image) return image;
      }
    }
  }
  return null;
}

// Wrap the example with the required providers
export const ImageGalleryExampleWithProviders: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <ImageGalleryExample />
  </QueryClientProvider>
);
