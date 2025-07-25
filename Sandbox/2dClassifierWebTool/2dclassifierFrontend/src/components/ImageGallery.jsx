// ImageGallery.jsx
import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import ImageItem from './ImageItem';
import EditControls from './EditControls';
import Notification from './Notification';
import axios from 'axios';
import { LabelAssign } from './LabelAssign';

const ImageGallery = ({ items, uuid, updateSelectedValue }) => {
  const BackendURL = process.env.REACT_APP_BACKEND_URL;
  const [isEditing, setIsEditing] = useState(false);
  const [selectedValues, setSelectedValues] = useState(Array(items.length).fill(null));
  const [tempValues, setTempValues] = useState(Array(items.length).fill(null));
  const [updatedValues, setUpdatedValues] = useState([...items]);
  const [displayedItems, setDisplayedItems] = useState([...items]);
  const [isSorted, setIsSorted] = useState(false);
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'success',
  });
  const [hasChanges, setHasChanges] = useState(false);

  const handleEditClick = () => {
    setTempValues([...selectedValues]);
    setIsEditing(true);
  };

  const handleValueSelect = (index, value) => {
    const newValues = [...tempValues];
    const newItems = [...updatedValues];

    newValues[index] = newValues[index] === value ? null : value;

    const updatedItem = { ...newItems[index] };
    if (newValues[index] === null) {
      delete updatedItem.updatedvalue;
    } else {
      updatedItem.updatedvalue = newValues[index];
    }

    newItems[index] = updatedItem;

    setTempValues(newValues);
    setUpdatedValues(newItems);
  };

  const handleSave = () => {
    setSelectedValues([...tempValues]);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setTempValues([...selectedValues]);
    setIsEditing(false);
  };

  const handleRestoreClick = () => {
    setSelectedValues(Array(items.length).fill(null));
    setTempValues(Array(items.length).fill(null));
    setUpdatedValues([...items]);
  };

  const handleSendUpdate = async () => {
    const payload = {
      uuid,
      selectedValue: updateSelectedValue,
      items: items.map((item, index) => ({
        updated: tempValues[index] !== null,
        oldValue: item.value,
        newValue: tempValues[index],
      })),
    };

    try {
      await axios.post(`${BackendURL}/api/update`, payload, {
        headers: { 'Content-Type': 'application/json' },
      });
      setNotification({
        open: true,
        message: 'Values updated successfully!',
        severity: 'success',
      });
    } catch (error) {
      console.error('Error updating values:', error);
      setNotification({
        open: true,
        message: 'Failed to update values',
        severity: 'error',
      });
    }
  };

  const handleSortToggle = () => {
    if (!isSorted) {
      const sorted = [...displayedItems].sort((a, b) => {
        const valA = a.value || '';
        const valB = b.value || '';
        return valA.localeCompare(valB);
      });
      setDisplayedItems(sorted);
    } else {
      setDisplayedItems([...items]);
    }
    setIsSorted(!isSorted);
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const getDownloadData = () => {
    return items.map((originalItem) => {
      const match = updatedValues.find((u) => u.image === originalItem.image); // adjust key as needed
      return {
        ...originalItem,
        ...(match?.updatedvalue !== undefined && { updatedvalue: match.updatedvalue }),
      };
    });
  };

  useEffect(() => {
    setDisplayedItems([...items]);
  }, [items]);

  useEffect(() => {
    setHasChanges(selectedValues.some((val) => val !== null));
  }, [tempValues, selectedValues]);

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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <LabelAssign />
        <EditControls
          isEditing={isEditing}
          onEdit={handleEditClick}
          onRestore={handleRestoreClick}
          onSend={handleSendUpdate}
          hasChanges={hasChanges}
          onSave={handleSave}
          onCancel={handleCancel}
          data={getDownloadData()}
          onSortToggle={handleSortToggle}
          isSorted={isSorted}
        />
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 2,
        }}
      >
        {displayedItems.map((item, index) => (
          <ImageItem
            key={index}
            item={item}
            index={index}
            isEditing={isEditing}
            tempValue={tempValues[index]}
            onValueSelect={handleValueSelect}
            selectedValue={selectedValues[index]}
          />
        ))}
      </Box>

      <Notification notification={notification} onClose={handleCloseNotification} />
    </Box>
  );
};

export default ImageGallery;
