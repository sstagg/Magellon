// FileSelector.js
import React, { useRef } from 'react';
import { Button, Typography } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

const FileSelector = ({ files, onFileChange, loading,consentChecked }) => {
  const fileInputRef = useRef(null);

  return (
    <>
      <Button
        variant="outlined"
        component="label"
        fullWidth
        startIcon={<CloudUploadIcon />}
        disabled={loading || !consentChecked}
      >
        Select Files
        <input
          type="file"
          multiple
          hidden
          onChange={onFileChange}
          ref={fileInputRef}
        />
      </Button>

      {files.length > 0 && (
        <Typography variant="body2" color="textSecondary">
          {files.length} {files.length === 1 ? 'file' : 'files'} selected
        </Typography>
      )}
    </>
  );
};

export default FileSelector;
