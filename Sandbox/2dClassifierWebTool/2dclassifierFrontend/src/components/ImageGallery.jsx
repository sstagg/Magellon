import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import ImageItem from './ImageItem';
import EditControls from './EditControls';
import Notification from './Notification';
import axios from 'axios';
import { LabelAssign } from './LabelAssign';

const ImageGallery = ({ items, uuid, updateSelectedValue }) => {
  const BackendURL = process.env.REACT_APP_BACKEND_URL;
  const [savedUpdates, setSavedUpdates] = useState(items.map(() => null));
  const [tempUpdates, setTempUpdates] = useState(items.map(() => null));

  const [isEditing, setIsEditing] = useState(false);
  const [displayedItems, setDisplayedItems] = useState([...items]);
  const [isSorted, setIsSorted] = useState(false);

  const [notification, setNotification] = useState({ open: false, message: '', severity: 'success' });
  useEffect(() => {
    setSavedUpdates(items.map(() => null));
    setTempUpdates(items.map(() => null));
    setDisplayedItems([...items]);
    setIsSorted(false);
    setIsEditing(false);
  }, [items]);

  const handleEditClick = () => {
    setTempUpdates([...savedUpdates]);
    setIsEditing(true);
  };
  const handleValueEdit = (index, newValue) => {
    setTempUpdates((prev) => {
      const originalValue = items[index].value;
      const toStore = newValue === null || newValue === '' || newValue === originalValue ? null : newValue;
      return prev.map((val, i) => (i === index ? toStore : val));
    });
  };

  const handleSave = () => {
    setSavedUpdates([...tempUpdates]);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setTempUpdates([...savedUpdates]);
    setIsEditing(false);
  };

  const handleRestoreClick = () => {
    const reset = items.map(() => null);
    setSavedUpdates(reset);
    setTempUpdates(reset);
    setIsEditing(false);
  };

  const handleSortToggle = () => {
    if (!isSorted) {
      const sorted = [...displayedItems].sort((a, b) => {
        const idxA = items.indexOf(a);
        const idxB = items.indexOf(b);

        const valA = savedUpdates[idxA] ?? a.value ?? '';
        const valB = savedUpdates[idxB] ?? b.value ?? '';

        const numA = parseFloat(valA);
        const numB = parseFloat(valB);

        if (!isNaN(numA) && !isNaN(numB)) {
          return numA - numB;
        }
        return String(valA).localeCompare(String(valB), undefined, { numeric: true });
      });
      setDisplayedItems(sorted);
    } else {
      setDisplayedItems([...items]);
    }
    setIsSorted(!isSorted);
  };

  const handleSendUpdate = async () => {
    const payload = {
      uuid,
      selectedValue: updateSelectedValue,
      items: items.map((item, idx) => ({
        updated: savedUpdates[idx] !== null && savedUpdates[idx] !== '',
        oldValue: item.value,
        newValue: savedUpdates[idx],
      })),
    };

    try {
      await axios.post(`${BackendURL}/api/update`, payload, {
        headers: { 'Content-Type': 'application/json' },
      });
      setNotification({ open: true, message: 'Values updated successfully!', severity: 'success' });
    } catch (error) {
      console.error('Error updating values:', error);
      setNotification({ open: true, message: 'Failed to update values', severity: 'error' });
    }
  };

  const hasChanges = savedUpdates.some((val) => val !== null && val !== '');

  const getDownloadData = () =>
    items.map((item, idx) => {
      const upd = savedUpdates[idx];
      return {
        name: item.name || item.image || `item_${idx}`,
        value: item.value,
        image_number:item.image_number,
        ...(upd !== null && upd !== '' ? { updatedvalue: upd } : { updatedvalue: null }),
      };
    });

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const currentValues = isEditing ? tempUpdates : savedUpdates;

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
        {displayedItems.map((item, displayIdx) => {
          const originalIndex = items.indexOf(item);
          if (originalIndex === -1) return null;
          const selectedValue =
            currentValues[originalIndex] === null || currentValues[originalIndex] === ''
              ? null
              : currentValues[originalIndex];
          return (
            <ImageItem
              key={item.image || originalIndex}
              item={item}
              index={originalIndex}
              isEditing={isEditing}
              tempValue={currentValues[originalIndex]}
              onValueSelect={handleValueEdit}
              selectedValue={selectedValue}
            />
          );
        })}
      </Box>

      <Notification notification={notification} onClose={handleCloseNotification} />
    </Box>
  );
};

export default ImageGallery;
