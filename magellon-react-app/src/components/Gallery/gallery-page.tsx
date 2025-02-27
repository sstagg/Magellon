// src/pages/GalleryPageView.tsx
import React, { useState } from 'react';
import { 
  Box, 
  Container, 
  Paper, 
  Divider, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem, 
  Stack,
  Typography,
  Grid,
  Card,
  CardContent,
  Switch,
  FormControlLabel,
  Slider
} from '@mui/material';
import { ImageGallery } from '../components/ImageGallery';
import '../styles/GalleryStyles.scss';
import { SoloImageViewerComponent } from '../components/imageviewer/SoloImageViewerComponent';
import { useImageGalleryStore } from '../stores/useImageGalleryStore';
import ImageInfoDto from '../types/ImageInfoDto';

export const GalleryPageView: React.FC = () => {
  const { columns } = useImageGalleryStore();
  const [thumbnailSize, setThumbnailSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [maxColumns, setMaxColumns] = useState<number>(4);
  const [showViewer, setShowViewer] = useState<boolean>(true);
  
  // Find the currently selected image (first non-null going backwards from the last column)
  const selectedImage = React.useMemo(() => {
    for (let i = columns.length - 1; i >= 0; i--) {
      const column = columns[i];
      if (column.selectedImageId && column.images) {
        // Find the selected image in the column's data
        for (const page of column.images.pages) {
          const foundImage = page.result.find(img => img.oid === column.selectedImageId);
          if (foundImage) return foundImage;
        }
      }
    }
    return null;
  }, [columns]);
  
  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Hierarchical Image Gallery
      </Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel id="thumbnail-size-label">Thumbnail Size</InputLabel>
              <Select
                labelId="thumbnail-size-label"
                id="thumbnail-size"
                value={thumbnailSize}
                label="Thumbnail Size"
                onChange={(e) => setThumbnailSize(e.target.value as 'small' | 'medium' | 'large')}
              >
                <MenuItem value="small">Small</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="large">Large</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Typography gutterBottom>Number of Columns</Typography>
            <Slider
              value={maxColumns}
              onChange={(_, value) => setMaxColumns(value as number)}
              step={1}
              marks
              min={1}
              max={6}
              valueLabelDisplay="auto"
            />
          </Grid>
          
          <Grid item xs={12} md={4}>
            <FormControlLabel
              control={
                <Switch 
                  checked={showViewer} 
                  onChange={(e) => setShowViewer(e.target.checked)} 
                />
              }
              label="Show Image Viewer"
            />
          </Grid>
        </Grid>
      </Paper>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={showViewer ? 7 : 12}>
          <Paper sx={{ p: 0, height: '80vh', overflow: 'hidden' }}>
            <ImageGallery 
              thumbnailSize={thumbnailSize}
              maxColumns={maxColumns}
              height="100%"
              width="100%"
            />
          </Paper>
        </Grid>
        
        {showViewer && (
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 2, height: '80vh', overflow: 'auto' }}>
              {selectedImage ? (
                <SoloImageViewerComponent selectedImage={selectedImage} />
              ) : (
                <Box 
                  display="flex" 
                  alignItems="center" 
                  justifyContent="center" 
                  height="100%"
                >
                  <Typography variant="subtitle1" color="text.secondary">
                    Select an image to view details
                  </Typography>
                </Box>
              )}
            </Paper>
          </Grid>
        )}
      </Grid>
      
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            How to Use
          </Typography>
          <Typography variant="body2" paragraph>
            1. Select a session from the dropdown at the top of the gallery.
          </Typography>
          <Typography variant="body2" paragraph>
            2. The first column will display the top-level images (typically atlases).
          </Typography>
          <Typography variant="body2" paragraph>
            3. Click on an image with a purple border (indicating it has children) to load its child images in the next column.
          </Typography>
          <Typography variant="body2" paragraph>
            4. Continue navigating through the hierarchy by selecting images in each column.
          </Typography>
          <Typography variant="body2">
            5. The image viewer on the right will display details of the currently selected image.
          </Typography>
        </CardContent>
      </Card>
    </Container>
  );
};
