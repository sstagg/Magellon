import React, { useState } from 'react';
import { Box, Button, ButtonGroup, Typography } from '@mui/material';

const ImageGallery = ({ items }) => {
  const BackendURL = "http://localhost:8001";
  const [isEditing, setIsEditing] = useState(false); 
  const [selectedValues, setSelectedValues] = useState(Array(items.length).fill(null)); 
  const [tempValues, setTempValues] = useState(Array(items.length).fill(null)); 

  const handleEditClick = () => {
    setTempValues([...selectedValues]); 
    setIsEditing(true);
  };

  const handleValueSelect = (index, value) => {
    const newValues = [...tempValues];
    newValues[index] = value;
    setTempValues(newValues);
  };

  const handleSave = () => {
    setSelectedValues([...tempValues]); 
    setIsEditing(false); 
  };

  const handleCancel = () => {
    setTempValues([...selectedValues]); 
    setIsEditing(false);
  };
  
  const handleRestoreClick=()=>{
    setSelectedValues(Array(items.length).fill(null))
    setTempValues(Array(items.length).fill(null))
  }
  return (
    <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      padding: 3,
      border: '1px solid #ddd',
      borderRadius: 2,
      maxWidth: '100%',
      margin: '0 auto',
      backgroundColor: '#f9f9f9',
    }}
  >

    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
      {isEditing ? (
        <Box>
          <Button variant="contained" color="primary" onClick={handleSave}>
            Save
          </Button>
          <Button variant="outlined" color="secondary" onClick={handleCancel} sx={{ ml: 1 }}>
            Cancel
          </Button>
        </Box>
      ) : (
        <Box>
          <Button variant="contained" color="secondary" onClick={handleEditClick}>
            Edit
          </Button>
          <Button variant="contained" color="secondary" onClick={handleRestoreClick} sx={{ ml: 1 }}>
            Restore
          </Button>
        </Box>
      )}
    </Box>
  
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 2,
      }}
    >
      {items.map((item, index) => (
        <Box
          key={index}
          sx={{
            textAlign: 'center',
            border: '1px solid #ddd',
            borderRadius: 2,
            padding: 2,
          }}
        >
          {/* Image */}
          <img
            src={`${BackendURL}${item.image}`}
            alt={`Image ${index}`}
            style={{
              width: '100%',
              height: '150px',
              objectFit: 'cover',
              borderRadius: '5px',
            }}
          />
  
          {isEditing && (
            <Box sx={{ width: '100%', margin: '10px auto', display: 'flex', justifyContent: 'center' }}>
              <ButtonGroup size="small" aria-label="small button group" sx={{ width: '100%', justifyContent: 'space-between' }}>
                {[1, 2, 3, 4, 5].map((num) => (
                  <Button
                    key={num}
                    variant={tempValues[index] === num ? 'contained' : 'outlined'}
                    onClick={() => handleValueSelect(index, num)}
                    sx={{ flex: 1 }}
                    style={{maxWidth: '25px', maxHeight: '25px', minWidth: '25px', minHeight: '25px'}}
                  >
                    {num}
                  </Button>
                ))}
              </ButtonGroup>
            </Box>
          )}
  
          {!isEditing && selectedValues[index] && (
            <Typography variant="subtitle1" sx={{ mt: 2 }}>
              Selected: {selectedValues[index]}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  </Box>
  
  );
};

export default ImageGallery;