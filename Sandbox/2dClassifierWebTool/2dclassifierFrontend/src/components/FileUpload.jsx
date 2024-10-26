// FileUpload.js
import React, { useState } from 'react';
import { Button, Box } from '@mui/material';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import Notification from './Notification';
import FileSelector from './FileSelector';
import ValueSelector from './ValueSelector';
import UploadProgress from './UploadProgress';
import ImageGallery from './ImageGallery';

const FileUpload = () => {
  const BackendURL = process.env.REACT_APP_BACKEND_URL;

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
  const [uuid, setUuid] = useState();

  const handleFileChange = (e) => {
    setFiles(e.target.files);
    setUploadProgress(0);
    setUuid(null);
  };

  const handleValueChange = (e) => {
    setSelectedValue(e.target.value);
  };

  const handleUpload = async () => {
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
      setUuid(uniqueId);

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
        <Notification notification={notification} onClose={handleCloseNotification} />
        <ValueSelector selectedValue={selectedValue} onValueChange={handleValueChange} loading={loading} />
        <FileSelector files={files} onFileChange={handleFileChange} loading={loading} />
        <Button
          onClick={handleUpload}
          variant="contained"
          color="primary"
          fullWidth
          disabled={loading || files.length === 0 || !selectedValue}
        >
          {loading ? 'Uploading...' : 'Upload Files'}
        </Button>
        <UploadProgress loading={loading} uploadProgress={uploadProgress} />
      </Box>

      {data.length > 0 && <ImageGallery items={data} uuid={uuid} />}
    </>
  );
};

export {FileUpload};
