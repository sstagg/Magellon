// FileUpload.js
import React, { useState, useRef } from 'react';
import {
  Button,
  Typography,
  CircularProgress,
  Box,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Snackbar,
  Alert,
} from '@mui/material';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import ImageGallery from './ImageGallery';

const FileUpload = () => {
  const BackendURL = "http://localhost:8001";
  const [files, setFiles] = useState([]);
  const [selectedValue, setSelectedValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'success' });
  const [data, setData] = useState([]); // Single state for images and values

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    setFiles(e.target.files);
    setUploadSuccess(false);
  };

  const handleValueChange = (e) => {
    setSelectedValue(e.target.value);
  };

  const handleUpload = async () => {
    if (files.length === 0 || !selectedValue) {
      setNotification({ open: true, message: 'Please select files and choose a value.', severity: 'warning' });
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
      });

      // Combine images and values into a single array of objects
      const combinedData = response.data.imageFilepaths.map((path, index) => ({
        image: path,
        value: response.data.extractedValues[index],
      }));

      setData(combinedData);
      setUploadSuccess(true);
      setNotification({ open: true, message: 'Files uploaded successfully!', severity: 'success' });
      setFiles([]);
      setSelectedValue('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Error uploading files:', error);
      setNotification({ open: true, message: 'Failed to upload files', severity: 'error' });
    } finally {
      setLoading(false);
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
          alignItems: 'center',
          gap: 2,
          padding: 3,
          border: '1px solid #ddd',
          borderRadius: 2,
          maxWidth: 500,
          margin: '0 auto',
          backgroundColor: '#f9f9f9',
          boxShadow: 5,
        }}
      >
        <Snackbar
          open={notification.open}
          autoHideDuration={5000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={handleCloseNotification} severity={notification.severity} sx={{ width: '100%' }}>
            {notification.message}
          </Alert>
        </Snackbar>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <input
            type="file"
            multiple
            onChange={handleFileChange}
            disabled={loading}
            ref={fileInputRef}
            style={{ flexGrow: 1 }}
          />

          <Button
            onClick={handleUpload}
            disableElevation
            variant="contained"
            size="small"
            color="primary"
            disabled={loading || files.length === 0 || !selectedValue}
            sx={{ whiteSpace: 'nowrap' }}
          >
            {loading ? 'Uploading...' : 'Upload Files'}
          </Button>
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
            <CircularProgress size={24} sx={{ mr: 2 }} />
            <Typography variant="body2">Uploading files...</Typography>
          </Box>
        )}

        <FormControl
          sx={{
            mb: 2,
            width: '200px',
          }}
          size="small"
        >
          <InputLabel sx={{ fontSize: '14px' }}>Select a Value</InputLabel>
          <Select
            value={selectedValue}
            onChange={handleValueChange}
            disabled={loading}
            label="Select a Value"
            sx={{ fontSize: '14px' }}
          >
            <MenuItem value="cryo">CryoSparc 2Davg</MenuItem>
            <MenuItem value="relion">Relion 2Davg</MenuItem>
          </Select>
        </FormControl>

        <Typography variant="body2" sx={{ mt: 1 }}>
          {files.length} {files.length === 1 ? 'file' : 'files'} selected
        </Typography>
      </Box>

      {/* {uploadSuccess && (
        <Typography variant="body2" color="success.main">
          Upload complete! You can now see your results.
        </Typography>
      )} */}
      {data.length > 0 && <ImageGallery items={data} />}
    </>
  );
};

export default FileUpload;
