// FileUpload.js
import React, { useState, useRef } from 'react';
import {
  Button,
  Typography,
  CircularProgress,
  LinearProgress,
  Box,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Snackbar,
  Alert,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import ImageGallery from './ImageGallery';

const FileUpload = () => {
  const BackendURL = 'http://localhost:8001';
  const [files, setFiles] = useState([]);
  const [selectedValue, setSelectedValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'success',
  });
  const [data, setData] = useState([]); 

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    setFiles(e.target.files);
    setUploadProgress(0);
  };

  const handleValueChange = (e) => {
    setSelectedValue(e.target.value);
  };

  const handleUpload = async () => {
    setData([])
    if (files.length === 0 || !selectedValue) {
      setNotification({
        open: true,
        message: 'Please select files and choose a value.',
        severity: 'warning',
      });
      return;
    }
    
    const formData = new FormData();
    const uniqueId = uuidv4();
    formData.append('uuid', uniqueId);
    formData.append('selectedValue', selectedValue);

    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    setLoading(true);
    try {
      const response = await axios.post(`${BackendURL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress(percentCompleted);
        },
      });

      const combinedData = response.data.imageFilepaths.map((path, index) => ({
        image: path,
        value: response.data.extractedValues[index],
      }));

      setData(combinedData);
      setNotification({
        open: true,
        message: 'Files uploaded and processed successfully!',
        severity: 'success',
      });
      setFiles([]);
      setSelectedValue('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Error uploading files:', error);
      setNotification({
        open: true,
        message: 'Failed to upload files',
        severity: 'error',
      });
    } finally {
      setLoading(false);
      setUploadProgress(0);
    }
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  return (
    <>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          padding: 3,
          border: '1px solid #ddd',
          borderRadius: 2,
          maxWidth: 500,
          margin: '20px auto',
          backgroundColor: '#f9f9f9',
          boxShadow: 3,
        }}
      >
        {/* Notification Snackbar */}
        <Snackbar
          open={notification.open}
          autoHideDuration={5000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert
            onClose={handleCloseNotification}
            severity={notification.severity}
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
        <FormControl fullWidth size="small">
          <InputLabel>Select a Value</InputLabel>
          <Select
            value={selectedValue}
            onChange={handleValueChange}
            disabled={loading}
            label="Select a Value"
          >
            <MenuItem value="cryo">CryoSparc 2Davg</MenuItem>
            <MenuItem value="relion">Relion 2Davg</MenuItem>
          </Select>
        </FormControl>

        <Button
          variant="outlined"
          component="label"
          fullWidth
          startIcon={<CloudUploadIcon />}
          disabled={loading}
        >
          Select Files
          <input
            type="file"
            multiple
            hidden
            onChange={handleFileChange}
            ref={fileInputRef}
          />
        </Button>

        {files.length > 0 && (
          <Typography variant="body2" color="textSecondary">
            {files.length} {files.length === 1 ? 'file' : 'files'} selected
          </Typography>
        )}

        <Button
          onClick={handleUpload}
          variant="contained"
          color="primary"
          fullWidth
          disabled={loading || files.length === 0 || !selectedValue}
        >
          {loading ? 'Uploading...' : 'Upload Files'}
        </Button>

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
      </Box>

      {data.length > 0 && <ImageGallery items={data} />}
    </>
  );
};

export  {FileUpload};
