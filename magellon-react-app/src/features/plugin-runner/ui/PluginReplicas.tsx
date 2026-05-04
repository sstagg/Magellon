/**
 * PM7c — per-replica health drilldown.
 *
 * Renders one row per `(plugin_id, instance_id)` from
 * `GET /plugins/{id}/replicas`. The endpoint exists today thanks to
 * PM5; the registry has always been replica-keyed, so one HTTP call
 * yields the full replica fan-out.
 *
 * Status chip:
 *   Healthy → success
 *   Stale   → warning
 *   Lost    → error
 *
 * "Force-stop replica" is a PM7c-deferred future hook (post-P9
 * docker-kill); the row layout reserves space for it but the button
 * is omitted until the verb exists.
 */
import React from 'react';
import {
    Box,
    Chip,
    CircularProgress,
    Stack,
    Typography,
} from '@mui/material';
import type { ReplicaInfo, ReplicaStatus } from '../api/PluginApi.ts';
import { usePluginReplicas } from '../api/PluginApi.ts';

function chipColorFor(status: ReplicaStatus): 'success' | 'warning' | 'error' {
    if (status === 'Healthy') return 'success';
    if (status === 'Stale') return 'warning';
    return 'error';
}

function relativeTimeFrom(iso: string | null | undefined): string {
    if (!iso) return '—';
    const t = new Date(iso).getTime();
    const ageMs = Date.now() - t;
    if (ageMs < 60_000) return `${Math.round(ageMs / 1000)}s ago`;
    if (ageMs < 3_600_000) return `${Math.round(ageMs / 60_000)}m ago`;
    return `${Math.round(ageMs / 3_600_000)}h ago`;
}

interface PluginReplicasProps {
    pluginId: string;
}

export const PluginReplicas: React.FC<PluginReplicasProps> = ({ pluginId }) => {
    const { data, isLoading, error } = usePluginReplicas(pluginId);

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="caption" color="text.secondary">
                    Loading replicas…
                </Typography>
            </Box>
        );
    }
    if (error) {
        return (
            <Typography variant="caption" color="error">
                Failed to load replicas.
            </Typography>
        );
    }
    if (!data || data.length === 0) {
        return (
            <Typography variant="caption" color="text.secondary">
                No replicas currently announcing.
            </Typography>
        );
    }

    return (
        <Stack spacing={0.5} data-testid="plugin-replicas">
            {data.map((replica: ReplicaInfo) => (
                <Stack
                    key={replica.instance_id}
                    direction="row"
                    spacing={1}
                    sx={{
                        alignItems: 'center',
                        px: 1,
                        py: 0.5,
                        borderRadius: 1,
                        bgcolor: 'action.hover',
                    }}
                >
                    <Chip
                        size="small"
                        color={chipColorFor(replica.status)}
                        label={replica.status}
                    />
                    <Typography variant="body2" sx={{ flex: 1, fontFamily: 'monospace' }}>
                        {replica.instance_id}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        last beat: {relativeTimeFrom(replica.last_heartbeat_at)}
                    </Typography>
                </Stack>
            ))}
        </Stack>
    );
};
