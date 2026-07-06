import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import type { BrowseFileRequest } from '../../../../shared/ui/SchemaForm.tsx';
import { SchemaForm } from '../../../../shared/ui/SchemaForm.tsx';
import type { ParamSchema } from '../../model/particleSettingsTypes.ts';

interface PreviewTunePanelProps {
    scoreMapPng: string | null;
    schema: ParamSchema;
    values: Record<string, unknown>;
    onChange: (params: Record<string, unknown>) => void;
    onBrowseFile: (req: BrowseFileRequest) => void;
}

/** PREVIEW-state body: score map + tunable sliders. */
export const PreviewTunePanel: React.FC<PreviewTunePanelProps> = ({
    scoreMapPng,
    schema,
    values,
    onChange,
    onBrowseFile,
}) => {
    const theme = useTheme();
    return (
        <>
            {scoreMapPng && (
                <Box sx={{ mb: 1.5, borderRadius: 1, overflow: 'hidden', border: `1px solid ${theme.palette.divider}` }}>
                    <img src={`data:image/png;base64,${scoreMapPng}`} alt="Score map" style={{ width: '100%', display: 'block' }} />
                    <Typography
                        variant="caption"
                        sx={{
                            color: "text.secondary",
                            px: 1,
                            py: 0.25,
                            display: 'block',
                            fontSize: '0.65rem'
                        }}>
                        Correlation map — brighter = higher match
                    </Typography>
                </Box>
            )}
            <Typography
                variant="caption"
                sx={{
                    fontWeight: 600,
                    display: 'block',
                    mb: 0.5,
                    fontSize: '0.7rem'
                }}>
                Tune parameters:
            </Typography>
            <SchemaForm schema={schema} values={values} onChange={onChange}
                tunableOnly={true} defaultExpanded={['Auto-picking Settings', 'Advanced', 'Topaz']}
                onBrowseFile={onBrowseFile} />
        </>
    );
};
