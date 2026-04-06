import React, { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Drawer,
    CircularProgress,
    Divider,
    Chip,
    alpha,
    useTheme,
} from '@mui/material';
import { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import { settings } from '../../../shared/config/settings.ts';

export interface ParticleSettingsDrawerProps {
    open: boolean;
    onClose: () => void;
    /** Algorithm params — single dict driven by backend schema */
    pickerParams: Record<string, any>;
    onPickerParamsChange: (params: Record<string, any>) => void;
}

export const ParticleSettingsDrawer: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    onClose,
    pickerParams,
    onPickerParamsChange,
}) => {
    const theme = useTheme();
    const [schema, setSchema] = useState<any>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);

    // Fetch the input schema from the backend once
    useEffect(() => {
        if (!open || schema) return;

        setSchemaLoading(true);
        fetch(`${settings.ConfigData.SERVER_API_URL}/plugins/pp/template-pick/schema/input`)
            .then((res) => {
                if (!res.ok) throw new Error(`${res.status}`);
                return res.json();
            })
            .then((data) => {
                setSchema(data);
                setSchemaError(null);
            })
            .catch((err) => {
                setSchemaError(`Could not load picker settings from server: ${err.message}`);
            })
            .finally(() => setSchemaLoading(false));
    }, [open, schema]);

    return (
        <Drawer anchor="right" open={open} onClose={onClose}>
            <Box sx={{ width: 360, p: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Typography variant="h6">
                        Algorithm Settings
                    </Typography>
                    {schema && (
                        <Chip
                            label="template-picker"
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.7rem' }}
                        />
                    )}
                </Box>

                {schemaLoading && (
                    <Box sx={{ textAlign: 'center', py: 6 }}>
                        <CircularProgress size={28} />
                        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1.5 }}>
                            Loading settings from backend...
                        </Typography>
                    </Box>
                )}

                {schemaError && (
                    <Box sx={{
                        p: 2, borderRadius: 1, mb: 2,
                        backgroundColor: alpha(theme.palette.error.main, 0.08),
                    }}>
                        <Typography variant="caption" color="error">
                            {schemaError}
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                            Make sure the backend is running on {settings.ConfigData.SERVER_API_URL}
                        </Typography>
                    </Box>
                )}

                {schema && (
                    <SchemaForm
                        schema={schema}
                        values={pickerParams}
                        onChange={onPickerParamsChange}
                        defaultExpanded={['Templates', 'Auto-picking Settings']}
                        collapseAdvanced
                    />
                )}
            </Box>
        </Drawer>
    );
};
