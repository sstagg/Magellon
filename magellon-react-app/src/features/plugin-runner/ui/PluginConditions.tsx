/**
 * Renders Conditions[] (PM2) as a chip cluster + an empty-state alert
 * for the "Installed but not announcing" failure mode (PM7a).
 *
 * Each Condition becomes one Chip:
 *   status=True  → success (green)
 *   status=False → error  (red)
 *   status=Unknown → default (grey)
 *
 * Chip label shows the type (Installed, Enabled, Live, ...). Reason +
 * message land in the tooltip so the cluster stays compact.
 *
 * The empty-state alert matches PM7a §10.1: when the plugin is
 * cataloged but not on the bus, surface the actionable hint instead
 * of a sea of grey chips.
 */
import React from 'react';
import { Alert, Chip, Stack, Tooltip } from '@mui/material';
import type { Condition, ConditionStatus, ConditionType } from '../api/PluginApi.ts';

const ORDERED_TYPES: ConditionType[] = [
    'Installed',
    'Enabled',
    'Live',
    'Healthy',
    'Default',
    // 'Paused' joins post-PM4; render whatever the backend sends.
];

function chipColorFor(status: ConditionStatus): 'success' | 'error' | 'default' {
    if (status === 'True') return 'success';
    if (status === 'False') return 'error';
    return 'default';
}

interface PluginConditionsProps {
    conditions: Condition[] | undefined;
}

export const PluginConditions: React.FC<PluginConditionsProps> = ({ conditions }) => {
    if (!conditions || conditions.length === 0) {
        return null;
    }

    // Sort conditions by the canonical order so the chip cluster reads
    // top-to-bottom Installed → Enabled → ... regardless of backend
    // emit order.
    const sorted = [...conditions].sort((a, b) => {
        const ai = ORDERED_TYPES.indexOf(a.type);
        const bi = ORDERED_TYPES.indexOf(b.type);
        return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

    const installed = sorted.find((c) => c.type === 'Installed');
    const live = sorted.find((c) => c.type === 'Live');
    const showOfflineHint =
        installed?.status === 'True' && live?.status === 'False';

    return (
        <Stack spacing={0.5} sx={{ mt: 1 }}>
            <Stack
                direction="row"
                spacing={0.5}
                useFlexGap
                flexWrap="wrap"
                data-testid="plugin-conditions"
            >
                {sorted.map((c) => {
                    const tooltipParts = [c.reason, c.message].filter(Boolean);
                    const tooltipText =
                        tooltipParts.length > 0 ? tooltipParts.join(' — ') : c.type;
                    return (
                        <Tooltip key={c.type} title={tooltipText}>
                            <Chip
                                size="small"
                                color={chipColorFor(c.status)}
                                variant={c.status === 'Unknown' ? 'outlined' : 'filled'}
                                label={c.type}
                            />
                        </Tooltip>
                    );
                })}
            </Stack>
            {showOfflineHint && (
                <Alert severity="warning" sx={{ py: 0 }}>
                    Installed but not announcing — check the container logs.
                </Alert>
            )}
        </Stack>
    );
};
