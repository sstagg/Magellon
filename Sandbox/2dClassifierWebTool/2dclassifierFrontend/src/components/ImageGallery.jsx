import React, { useState } from 'react';
import { Button, Tooltip, TextField, Box } from '@mui/material'; // Import Material-UI components
import RestoreIcon from '@mui/icons-material/Restore';
import SaveAsIcon from '@mui/icons-material/SaveAs';
import CancelIcon from '@mui/icons-material/Cancel';
import EditNoteIcon from '@mui/icons-material/EditNote';

const ImageGallery = ({ items }) => {
  const BackendURL = "http://localhost:8001";

  const [isEditing, setIsEditing] = useState(false); // State to track if editing mode is enabled
  const [editableItems, setEditableItems] = useState(items); // Cloned state for editable items
  const [savedItems, setSavedItems] = useState(items); // State to keep track of the last saved items

  const handleEdit = () => {
    setIsEditing(true); // Enable edit mode
  };

  const handleSave = () => {
    setSavedItems([...editableItems]); // Update saved items with the current editable items
    setIsEditing(false); // Exit edit mode
  };

  const handleCancel = () => {
    setEditableItems([...savedItems]); // Revert to the last saved items
    setIsEditing(false); // Exit edit mode
  };

  const handleChange = (index, event) => {
    const updatedItems = [...editableItems];
    updatedItems[index] = { ...updatedItems[index], value: event.target.value }; // Update the value in the editable state
    setEditableItems(updatedItems);
  };

  const handleLoadOriginalValues = () => {
    setEditableItems([...items]); // Revert to the original values
    setSavedItems([...items]); // Update saved items with the original values
  };

  return (
    <div>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mb: 2 }}>
        <Tooltip title="Restore">
          <Button variant="contained" color="secondary" onClick={handleLoadOriginalValues}>
            <RestoreIcon />
          </Button>
        </Tooltip>
        {isEditing ? (
          <>
            <Tooltip title="Save">
              <Button variant="contained" color="primary" onClick={handleSave}>
                <SaveAsIcon />
              </Button>
            </Tooltip>
            <Tooltip title="Cancel">
              <Button variant="outlined" color="secondary" onClick={handleCancel}>
                <CancelIcon />
              </Button>
            </Tooltip>
          </>
        ) : (
          <Tooltip title="Edit">
            <Button variant="contained" color="primary" onClick={handleEdit}>
              <EditNoteIcon />
            </Button>
          </Tooltip>
        )}
      </Box>

      <div className="gallery" style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
        {editableItems.map((item, index) => (
          <div key={index} className="gallery-item" style={{ position: 'relative', width: '200px' }}>
            
              <TextField
                type="number"
                value={item.value}
                onChange={(event) => handleChange(index, event)}
                variant="outlined"
                size="small"
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '70px', // Reduce the width
                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                    padding: '1px 2px', // Decrease padding
                    fontSize: '0.2rem', // Reduce font size
                    '& .MuiOutlinedInput-input': {
                      padding: '2px 4px', // Smaller padding inside the input
                    },
                    '& .MuiOutlinedInput-root': {
                      minHeight: '12px', // Decrease the minimum height of the input field
                      borderRadius: '12px'
                    },
                  }}                disabled={!isEditing}
              />
    
            <img
              src={`${BackendURL}${item.image}`}
              alt={`Image ${index}`}
              style={{ width: '100%', height: 'auto' }}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ImageGallery;
