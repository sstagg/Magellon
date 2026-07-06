import React from 'react';
import { Chip, CircularProgress, FormControl, MenuItem, Select } from '@mui/material';
import type { BackendInfo } from '../../model/particleSettingsTypes.ts';

interface BackendSelectorProps {
    backends: BackendInfo[];
    selectedBackend: string;
    backendsLoading: boolean;
    onSelect: (backendId: string) => void;
}

/** Backend dropdown — shown in configure state. */
export const BackendSelector: React.FC<BackendSelectorProps> = ({
    backends,
    selectedBackend,
    backendsLoading,
    onSelect,
}) => (
    <FormControl fullWidth size="small" sx={{ mb: 0.75 }}>
        <Select
            value={selectedBackend}
            onChange={(e) => onSelect(e.target.value)}
            displayEmpty
            sx={{ fontSize: '0.75rem', height: 28 }}
        >
            {backends.length === 0 && (
                <MenuItem value="topaz-particle-picking" sx={{ fontSize: '0.75rem' }}>
                    topaz-particle-picking
                </MenuItem>
            )}
            {backends.map(b => (
                <MenuItem key={b.backend_id} value={b.backend_id} sx={{ fontSize: '0.75rem' }}>
                    {b.label}
                    {b.has_preview && <Chip label="preview" size="small" sx={{ ml: 1, fontSize: '0.6rem', height: 16 }} />}
                </MenuItem>
            ))}
            {backendsLoading && (
                <MenuItem disabled sx={{ fontSize: '0.75rem' }}>
                    <CircularProgress size={12} sx={{ mr: 1 }} /> Loading…
                </MenuItem>
            )}
        </Select>
    </FormControl>
);
