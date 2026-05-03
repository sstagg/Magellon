/**
 * Tests for the PM7a PluginConditions chip cluster.
 *
 * Pins the contract PluginBrowser depends on:
 *
 *  - One chip per Condition row, color-coded by status (True=success,
 *    False=error, Unknown=default).
 *  - Empty-state alert appears when Installed=True && Live=False — the
 *    "installed but not announcing" failure mode the operator most
 *    needs to see (PM7a §10.1 acceptance).
 *  - Empty input → renders nothing (no chip cluster on a plugin we
 *    haven't fetched status for yet).
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { PluginConditions } from '../../features/plugin-runner/ui/PluginConditions.tsx';
import type { Condition } from '../../features/plugin-runner/api/PluginApi.ts';


describe('PluginConditions', () => {
    it('renders one chip per condition with the type as label', () => {
        const conditions: Condition[] = [
            { type: 'Installed', status: 'True', reason: 'Catalogued' },
            { type: 'Enabled', status: 'True', reason: 'DefaultTrue' },
            { type: 'Live', status: 'True', reason: 'Heartbeat' },
            { type: 'Healthy', status: 'True', reason: 'RecentSuccess' },
            { type: 'Default', status: 'False', reason: 'NotDefault' },
        ];
        render(<PluginConditions conditions={conditions} />);

        expect(screen.getByText('Installed')).toBeTruthy();
        expect(screen.getByText('Enabled')).toBeTruthy();
        expect(screen.getByText('Live')).toBeTruthy();
        expect(screen.getByText('Healthy')).toBeTruthy();
        expect(screen.getByText('Default')).toBeTruthy();
    });

    it('renders empty-state alert when installed but not announcing', () => {
        const conditions: Condition[] = [
            { type: 'Installed', status: 'True', reason: 'Catalogued' },
            { type: 'Enabled', status: 'True', reason: 'DefaultTrue' },
            { type: 'Live', status: 'False', reason: 'NoHeartbeat' },
            { type: 'Healthy', status: 'Unknown', reason: 'NotLive' },
            { type: 'Default', status: 'False', reason: 'NotDefault' },
        ];
        render(<PluginConditions conditions={conditions} />);
        expect(
            screen.getByText(/installed but not announcing/i),
        ).toBeTruthy();
    });

    it('does not render the offline alert when the plugin is live', () => {
        const conditions: Condition[] = [
            { type: 'Installed', status: 'True', reason: 'Catalogued' },
            { type: 'Live', status: 'True', reason: 'Heartbeat' },
        ];
        render(<PluginConditions conditions={conditions} />);
        expect(
            screen.queryByText(/installed but not announcing/i),
        ).toBeNull();
    });

    it('renders nothing for an empty / undefined condition set', () => {
        const { container } = render(<PluginConditions conditions={undefined} />);
        expect(container.textContent).toBe('');
    });

    it('orders chips canonically regardless of backend emit order', () => {
        // Backend emits Default first, but the cluster should render
        // Installed → Enabled → Live → Healthy → Default. Pinned because
        // an out-of-order chip cluster looks broken to the operator.
        const conditions: Condition[] = [
            { type: 'Default', status: 'False' },
            { type: 'Healthy', status: 'True' },
            { type: 'Installed', status: 'True' },
            { type: 'Live', status: 'True' },
            { type: 'Enabled', status: 'True' },
        ];
        render(<PluginConditions conditions={conditions} />);
        const cluster = screen.getByTestId('plugin-conditions');
        const labels = Array.from(cluster.querySelectorAll('.MuiChip-label')).map(
            (n) => n.textContent,
        );
        expect(labels).toEqual([
            'Installed',
            'Enabled',
            'Live',
            'Healthy',
            'Default',
        ]);
    });
});
