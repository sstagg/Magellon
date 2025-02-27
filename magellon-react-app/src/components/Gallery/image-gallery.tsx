// src/components/ImageGallery.tsx
import React, { useEffect } from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import ViewStreamIcon from '@mui/icons-material/ViewStream';
import { useImageGalleryStore, LayoutOrientation } from './image-gallery-store';
import { GalleryColumn } from './gallery-column';
import { useQuery } from 'react-query';
import { FetchSessionNames } from '../../services/api/FetchUseSessionNames';

interface ImageGalleryProps {
  thumbnailSize?: 'small' | 'medium' | 'large';
  maxColumns?: number;
  height?: number | string;
  width?: number | string;
}

export const ImageGallery: React.FC<ImageGalleryProps> = ({
  thumbnailSize = 'medium',
  maxColumns = 4,
  height = '80vh',
  width = '100%',
}) => {
  const { orientation, columns, setOrientation, setSessionName, sessionName } = useImageGalleryStore();
  
  // Fetch available sessions
  const { data: sessions, isLoading: isSessionsLoading } = useQuery('gallery-sessions', FetchSessionNames);
  
  // Handle orientation change
  const handleOrientationChange = (event: React.MouseEvent<HTMLElement>, newOrientation: LayoutOrientation | null) => {
    if (newOrientation !== null) {
      setOrientation(newOrientation);
    }
  };
  
  // Handle session change
  const handleSessionChange = (event: React.ChangeEvent<{ value: unknown }>) => {
    const value = event.target.value as string;
    setSessionName(value || null);
  };
  
  // Calculate sizes based on orientation and thumbnail size
  const columnSizeMap = {
    small: { width: 150, height: 600 },
    medium: { width: 200, height: 700 },
    large: { width: 250, height: 800 },
  };
  
  const columnWidth = columnSizeMap[thumbnailSize].width;
  const columnHeight = columnSizeMap[thumbnailSize].height;
  
  // Limit number of visible columns
  const visibleColumns = columns.slice(0, maxColumns);
  
  return (
    <Box sx={{ width, height, overflow: 'hidden' }}>
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Typography variant="h6">Image Gallery</Typography>
        
        <FormControl variant="outlined" size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="session-select-label">Session</InputLabel>
          <Select
            labelId="session-select-label"
            id="session-select"
            value={sessionName || ''}
            onChange={handleSessionChange}
            label="Session"
            disabled={isSessionsLoading}
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
        
        <ToggleButtonGroup
          value={orientation}
          exclusive
          onChange={handleOrientationChange}
          aria-label="gallery orientation"
          size="small"
        >
          <ToggleButton value="horizontal" aria-label="horizontal layout">
            <ViewColumnIcon />
          </ToggleButton>
          <ToggleButton value="vertical" aria-label="vertical layout">
            <ViewStreamIcon />
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      
      <Box
        sx={{
          display: 'flex',
          flexDirection: orientation === 'horizontal' ? 'row' : 'column',
          gap: 2,
          overflow: 'auto',
          height: 'calc(100% - 60px)',  // Account for the header
          width: '100%',
        }}
      >
        {visibleColumns.map((column, index) => (
          <GalleryColumn
            key={column.id}
            columnIndex={index}
            width={columnWidth}
            height={orientation === 'horizontal' ? columnHeight : 300}
            thumbnailSize={thumbnailSize}
          />
        ))}
      </Box>
    </Box>
  );
};
