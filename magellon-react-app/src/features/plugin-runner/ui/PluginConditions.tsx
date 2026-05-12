/**
 * Renders Conditions[] (PM2) as a chip cluster + an empty-state alert
 * for the "Installed but not announcing" failure mode (PM7a).
 *
 * Chip rules (refined for visual signal-to-noise):
 *   - True-and-good state — green filled chip.
 *   - False-and-bad     — red filled chip (only Installed/Healthy).
 *   - False-but-normal  — grey outlined chip (Enabled=False, Live=False).
 *     Red was alarming on rows that were just intentionally disabled
 *     or stopped — operators read five red chips as "something broken".
 *   - Default=False     — chip omitted; the Default star elsewhere on
 *     the card already conveys default state when True.
 *   - Unknown           — grey outlined.
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

/** Which conditions surface as red when False. The rest fall back to
 *  outlined grey so a normally-stopped or intentionally-disabled plugin
 *  doesn't render as a wall of red. */
const ALARMING_WHEN_FALSE = new Set<ConditionType>(['Installed', 'Healthy']);

interface ChipStyle {
    color: 'success' | 'error' | 'default';
    variant: 'filled' | 'outlined';
}

function chipStyleFor(type: ConditionType, status: ConditionStatus): ChipStyle {
    if (status === 'True') return { color: 'success', variant: 'filled' };
    if (status === 'False') {
        return ALARMING_WHEN_FALSE.has(type)
            ? { color: 'error', variant: 'filled' }
            : { color: 'default', variant: 'outlined' };
    }
    return { color: 'default', variant: 'outlined' };
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
    // emit order. Filter out Default=False since the green Default
    // chip on the card title row already covers True; False is just
    // "not default" which is the common case for sibling backends.
    const sorted = [...conditions]
        .filter((c) => !(c.type === 'Default' && c.status !== 'True'))
        .sort((a, b) => {
            const ai = ORDERED_TYPES.indexOf(a.type);
            const bi = ORDERED_TYPES.indexOf(b.type);
            return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
        });

    const installed = sorted.find((c) => c.type === 'Installed');
    const live = (conditions ?? []).find((c) => c.type === 'Live');
    const showOfflineHint =
        installed?.status === 'True' && live?.status === 'False';

    return (
        <Stack spacing={0.5} sx={{ mt: 1 }}>
            <Stack
                direction="row"
                spacing={0.5}
                useFlexGap
                sx={{ flexWrap: 'wrap' }}
                data-testid="plugin-conditions"
            >
                {sorted.map((c) => {
                    const tooltipParts = [c.reason, c.message].filter(Boolean);
                    const tooltipText =
                        tooltipParts.length > 0 ? tooltipParts.join(' — ') : c.type;
                    const style = chipStyleFor(c.type, c.status);
                    return (
                        <Tooltip key={c.type} title={tooltipText}>
                            <Chip
                                size="small"
                                color={style.color}
                                variant={style.variant}
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
