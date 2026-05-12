/**
 * PM7d — "Update available" chip on plugin cards.
 *
 * Phase 9: the chip is now a click target. When ``manifestPluginId``
 * is passed, clicking opens the UpgradeDialog with the available
 * version pre-selected.
 *
 * Severity drives the color so the operator can scan the grid for
 * major-bumps:
 *   patch → info  (blue)
 *   minor → warning (amber)
 *   major → error (red — likely breaking)
 */
import React, { useState } from 'react';
import { Chip, Tooltip } from '@mui/material';
import type { UpdateInfo } from '../api/PluginApi.ts';
import { UpgradeDialog } from '../../plugin-installer/ui/UpgradeDialog.tsx';

function chipColorFor(
    severity: UpdateInfo['severity'],
): 'info' | 'warning' | 'error' {
    if (severity === 'major') return 'error';
    if (severity === 'minor') return 'warning';
    return 'info';
}

interface PluginUpdateChipProps {
    update: UpdateInfo | undefined;
    /** Optional — passing this turns the chip into an upgrade trigger.
     *  Distinct from ``plugin_id`` (the runtime ID announced on the bus);
     *  the admin endpoints key on ``manifest_plugin_id``. */
    manifestPluginId?: string | null;
}

export const PluginUpdateChip: React.FC<PluginUpdateChipProps> = ({
    update, manifestPluginId,
}) => {
    const [open, setOpen] = useState(false);
    if (!update) return null;
    const clickable = !!manifestPluginId;
    const tooltip =
        `${update.severity} update available — ` +
        `${update.current_version} → ${update.latest_version}` +
        (clickable ? ' (click to upgrade)' : '');
    return (
        <>
            <Tooltip title={tooltip}>
                <Chip
                    size="small"
                    color={chipColorFor(update.severity)}
                    label={`Update: ${update.latest_version}`}
                    onClick={clickable ? () => setOpen(true) : undefined}
                    clickable={clickable}
                    data-testid="plugin-update-chip"
                    data-severity={update.severity}
                />
            </Tooltip>
            {clickable && (
                <UpgradeDialog
                    open={open}
                    onClose={() => setOpen(false)}
                    pluginId={manifestPluginId!}
                    suggestedVersion={update.latest_version}
                />
            )}
        </>
    );
};
