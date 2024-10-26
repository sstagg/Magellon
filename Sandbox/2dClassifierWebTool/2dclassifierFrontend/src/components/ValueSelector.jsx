// ValueSelector.js
import React from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';

const ValueSelector = ({ selectedValue, onValueChange, loading }) => {
  return (
    <FormControl fullWidth size="small">
      <InputLabel>Select a Value</InputLabel>
      <Select
        value={selectedValue}
        onChange={onValueChange}
        disabled={loading}
        label="Select a Value"
      >
        <MenuItem value="cryo">CryoSparc 2Davg</MenuItem>
        <MenuItem value="relion">Relion 2Davg</MenuItem>
      </Select>
    </FormControl>
  );
};

export default ValueSelector;
