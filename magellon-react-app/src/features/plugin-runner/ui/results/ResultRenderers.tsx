import React from 'react';
import { Box, Typography } from '@mui/material';
import { CtfResultView } from './CtfResultView.tsx';
import { MotionCorResultView } from './MotionCorResultView.tsx';
import { TemplatePickerResultView } from './TemplatePickerResultView.tsx';

/**
 * Plugin-specific result renderers. The registry is keyed by `plugin_id`
 * (e.g. "ctf/ctffind"). Plugins without a custom renderer fall back to a
 * JSON dump so nothing is ever invisible.
 */

export type ResultRendererProps = { result: any };

const registry: Record<string, React.FC<ResultRendererProps>> = {
    'ctf/ctffind': CtfResultView,
    'motioncor/motioncor2': MotionCorResultView,
    'pp/template-picker': TemplatePickerResultView,
};

export const ResultRenderer: React.FC<{ pluginId: string; result: any }> = ({ pluginId, result }) => {
    const Renderer = registry[pluginId];
    if (!result) return null;
    if (Renderer) return <Renderer result={result} />;
    return <JsonFallback result={result} />;
};

const JsonFallback: React.FC<{ result: any }> = ({ result }) => (
    <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Result</Typography>
        <Box
            component="pre"
            sx={{
                fontFamily: 'monospace',
                fontSize: '0.75rem',
                p: 1.5,
                backgroundColor: 'action.hover',
                borderRadius: 1,
                maxHeight: 320,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
            }}
        >
            {JSON.stringify(result, null, 2)}
        </Box>
    </Box>
);
