import React from 'react';
import { Box, Typography } from '@mui/material';
import { CtfResultView } from './CtfResultView.tsx';
import { MotionCorResultView } from './MotionCorResultView.tsx';
import { TemplatePickerResultView } from './TemplatePickerResultView.tsx';

/**
 * Plugin-specific result renderers, keyed by category. Pre-fix this
 * was keyed by ``plugin_id`` ("pp/template-picker") which silently
 * 404'd into the JSON fallback after PI-5 — the broker picker
 * announces as ``particle_picking/Template Picker``. Categories are
 * stable across plugin renames; renderer registration is per category.
 *
 * Plugins without a custom renderer fall back to a JSON dump so
 * nothing is ever invisible.
 */

export type ResultRendererProps = { result: any };

const _byCategory: Record<string, React.FC<ResultRendererProps>> = {
    ctf: CtfResultView,
    motioncor: MotionCorResultView,
    particle_picking: TemplatePickerResultView,
};

function _normalizeCategoryKey(s: string | undefined | null): string {
    return (s ?? '').toLowerCase().replace(/[\s-]+/g, '_');
}

export const ResultRenderer: React.FC<{ pluginId: string; result: any }> = ({ pluginId, result }) => {
    if (!result) return null;
    // plugin_id is "<category>/<name>" — pull the category prefix.
    // Normalize so "Particle Picking" / "particle-picking" /
    // "particle_picking" all resolve to the same key.
    const [rawCategory] = (pluginId ?? '').split('/', 1);
    const Renderer = _byCategory[_normalizeCategoryKey(rawCategory)];
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
