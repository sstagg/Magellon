// UploadProgress.js
import React from 'react';
import { LinearProgress, CircularProgress, Box, Typography } from '@mui/material';

const UploadProgress = ({ loading, uploadProgress }) => {
  return (
    <>
      {loading && (
        <>
          {uploadProgress < 100 ? (
            <Box sx={{ width: '100%', mt: 2 }}>
              <LinearProgress variant="determinate" value={uploadProgress} />
              <Typography variant="body2" align="center">
                Uploading Files: {uploadProgress}%
              </Typography>
            </Box>
          ) : (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mt: 2,
              }}
            >
              <CircularProgress size={24} sx={{ mr: 2 }} />
              <Typography variant="body2">Processing files...</Typography>
            </Box>
          )}
        </>
      )}
    </>
  );
};

export default UploadProgress;
