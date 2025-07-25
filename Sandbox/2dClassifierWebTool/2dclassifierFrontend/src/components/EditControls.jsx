import React from 'react';
import { Box, Button } from '@mui/material';

const EditControls = ({
  isEditing,
  onEdit,
  onRestore,
  onSend,
  hasChanges,
  onSave,
  onCancel,
  data,
  onSortToggle,
  isSorted,
}) => {
  const downloadFile = () => {
    const fileData = JSON.stringify(data, null, 2); // pretty print
    const blob = new Blob([fileData], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = 'data.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

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
          {/* <Button variant="contained" color="secondary" onClick={onSortToggle}>
            {isSorted ? 'Unsort' : 'Sort'}
          </Button> */}
          <Button variant="contained" color="secondary" onClick={downloadFile} sx={{ ml: 1 }}>
            Download
          </Button>
          <Button variant="contained" color="secondary" onClick={onEdit} sx={{ ml: 1 }}>
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
