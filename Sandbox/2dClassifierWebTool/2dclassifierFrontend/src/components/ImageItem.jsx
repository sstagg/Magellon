import React from 'react';
import { Box, Button, ButtonGroup, Typography } from '@mui/material';

const ImageItem = ({ item, index, isEditing, tempValue, onValueSelect, selectedValue }) => {
  const handleButtonClick = (num) => {
    if (tempValue === num) {
      onValueSelect(index, null);
    } else {
      onValueSelect(index, num);
    }
  };

  return (
    <Box
  sx={{
    textAlign: 'center',
    border: '1px solid #ddd',
    borderRadius: 2,
    padding: 2,
    position: 'relative',
  }}
>
  {/* Serial Number - Top Left, above image */}
  <Typography
    sx={{
      position: 'absolute',
      top: 0,
      left: 0,
      transform: 'translate(-30%, -30%)',
      backgroundColor: '#e0f7fa',
      color: '#006064',
      padding: '4px 8px',
      borderRadius: '4px',
      fontSize: '10px',
      fontWeight: 'bold',
      zIndex: 2,
    }}
  >
    {item.image_number}
  </Typography>

  {/* Image + Value */}
  <Box sx={{ position: 'relative' }}>
    {/* Value - Top Right (on image) */}
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

  {/* Buttons and selected value */}
  {isEditing && (
    <Box
      sx={{
        width: '100%',
        margin: '10px auto',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <ButtonGroup
        size="small"
        aria-label="small button group"
        sx={{ width: '100%', justifyContent: 'space-between' }}
      >
        {[1, 2, 3, 4, 5].map((num) => (
          <Button
            key={num}
            variant={tempValue === num ? 'contained' : 'outlined'}
            onClick={() => handleButtonClick(num)}
            sx={{ flex: 1 }}
            style={{
              maxWidth: '25px',
              maxHeight: '25px',
              minWidth: '25px',
              minHeight: '25px',
            }}
          >
            {num}
          </Button>
        ))}
      </ButtonGroup>
    </Box>
  )}

  {!isEditing && selectedValue != null && selectedValue !== '' && (
    <Typography variant="subtitle1" sx={{ mt: 2 }}>
      Selected: {selectedValue}
    </Typography>
  )}
</Box>

  );
};

export default ImageItem;
