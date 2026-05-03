/**
 * PM7d — "Update available" chip on plugin cards.
 *
 * Reads from the shared usePluginUpdates() result (one HTTP call for
 * the whole grid) and surfaces a chip on the card whose plugin_id
 * matches. Severity drives the color so the operator can scan the
 * grid for major-bumps:
 *   patch → info  (blue)
 *   minor → warning (amber)
 *   major → error (red — likely breaking)
 *
 * No "Upgrade" verb yet — that's the PM7d follow-up that wires up
 * the existing /install/archive endpoint with the catalog's
 * archive_url. The chip is the chip; the dialog is its own change.
 */
import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import type { UpdateInfo } from '../api/PluginApi.ts';

function chipColorFor(
    severity: UpdateInfo['severity'],
): 'info' | 'warning' | 'error' {
    if (severity === 'major') return 'error';
    if (severity === 'minor') return 'warning';
    return 'info';
}

interface PluginUpdateChipProps {
    update: UpdateInfo | undefined;
}

export const PluginUpdateChip: React.FC<PluginUpdateChipProps> = ({ update }) => {
    if (!update) return null;
    const tooltip =
        `${update.severity} update available — ` +
        `${update.current_version} → ${update.latest_version}`;
    return (
        <Tooltip title={tooltip}>
            <Chip
                size="small"
                color={chipColorFor(update.severity)}
                label={`Update: ${update.latest_version}`}
                data-testid="plugin-update-chip"
                data-severity={update.severity}
            />
        </Tooltip>
    );
};
