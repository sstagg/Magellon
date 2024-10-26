// EditControls.jsx
import React from 'react';
import { Box, Button } from '@mui/material';

const EditControls = ({ isEditing, onEdit, onRestore, onSend, hasChanges, onSave, onCancel }) => {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
      {isEditing ? (
        <Box>
          <Button variant="contained" color="primary" onClick={onSave}>
            Save
          </Button>
          <Button variant="outlined" color="secondary" onClick={onCancel} sx={{ ml: 1 }}>
            Cancel
          </Button>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Button variant="contained" color="secondary" onClick={onEdit}>
            Edit
          </Button>
          <Button variant="contained" color="secondary" onClick={onRestore} sx={{ ml: 1 }}>
            Restore
          </Button>
          <Button 
            variant="contained" 
            color="secondary" 
            onClick={onSend} 
            disabled={!hasChanges}
            sx={{ ml: 1 }}
          >
            Send
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default EditControls;
