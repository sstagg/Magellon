/**
 * Tiny presentational chip — at-a-glance "how was this plugin deployed?".
 *
 * Distinct from InstallLocationChip which shows *where* (image_ref or
 * install_dir). This chip shows the *kind* (uv venv, Docker container,
 * broker-discovered ad-hoc, raw archive). They're complementary —
 * cards typically show both.
 */
import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import { Box, Container as ContainerIcon, Radio, Archive } from 'lucide-react';

import type { InstallMethod } from '../api/PluginApi.ts';

interface Props {
    method?: InstallMethod | null;
    /** Optional small variant for dense card headers. */
    size?: 'small' | 'medium';
}

const META: Record<
    InstallMethod,
    { label: string; tooltip: string; Icon: React.ComponentType<{ size?: number }>; color: 'default' | 'primary' | 'success' | 'info' | 'warning' }
> = {
    uv: {
        label: 'uv',
        tooltip: 'Installed as a Python venv via uv. Process supervised by the host.',
        Icon: Box,
        color: 'success',
    },
    docker: {
        label: 'docker',
        tooltip: 'Running inside a Docker container. Lifecycle managed by the Docker daemon.',
        Icon: ContainerIcon,
        color: 'primary',
    },
    discovered: {
        label: 'discovered',
        tooltip: 'Announced on the broker, not installed via the v1 pipeline. CoreService catalogued it from heartbeats.',
        Icon: Radio,
        color: 'info',
    },
    archive: {
        label: 'archive',
        tooltip: 'Legacy v0 archive install. Pre-v1 install pipeline format.',
        Icon: Archive,
        color: 'warning',
    },
};

export const DeploymentMethodChip: React.FC<Props> = ({ method, size = 'small' }) => {
    if (!method) return null;
    const meta = META[method];
    if (!meta) {
        return <Chip size={size} variant="outlined" label={method} />;
    }
    const { Icon, label, tooltip, color } = meta;
    return (
        <Tooltip title={tooltip} placement="top">
            <Chip
                size={size}
                variant="outlined"
                color={color}
                icon={<Icon size={12} />}
                label={label}
            />
        </Tooltip>
    );
};

export default DeploymentMethodChip;
