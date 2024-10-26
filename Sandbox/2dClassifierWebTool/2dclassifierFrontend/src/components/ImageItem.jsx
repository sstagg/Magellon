// ImageItem.jsx
import React from 'react';
import { Box, Button,ButtonGroup, Typography } from '@mui/material';

const ImageItem = ({ item, index, isEditing, tempValue, onValueSelect, selectedValue }) => {
  return (
    <Box
      sx={{
        textAlign: 'center',
        border: '1px solid #ddd',
        borderRadius: 2,
        padding: 2,
      }}
    >
      <Box sx={{ position: 'relative' }}>
        <Typography
          sx={{
            position: 'absolute',
            top: 5,
            right: 5,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            color: 'white',
            padding: '2px 6px',
            borderRadius: '3px',
            fontSize: '12px',
          }}
        >
          {item.value}
        </Typography>
        <img
          src={`${process.env.REACT_APP_BACKEND_URL}${item.image}`}
          alt={`Image ${index}`}
          style={{
            width: '100%',
            height: '150px',
            objectFit: 'cover',
            borderRadius: '5px',
          }}
        />
      </Box>

      {isEditing && (
        <Box sx={{ width: '100%', margin: '10px auto', display: 'flex', justifyContent: 'center' }}>
          <ButtonGroup size="small" aria-label="small button group" sx={{ width: '100%', justifyContent: 'space-between' }}>
            {[1, 2, 3, 4, 5].map((num) => (
              <Button
                key={num}
                variant={tempValue === num ? 'contained' : 'outlined'}
                onClick={() => onValueSelect(index, num)}
                sx={{ flex: 1 }}
                style={{ maxWidth: '25px', maxHeight: '25px', minWidth: '25px', minHeight: '25px' }}
              >
                {num}
              </Button>
            ))}
          </ButtonGroup>
        </Box>
      )}

      {!isEditing && selectedValue && (
        <Typography variant="subtitle1" sx={{ mt: 2 }}>
          Selected: {selectedValue}
        </Typography>
      )}
    </Box>
  );
};

export default ImageItem;
