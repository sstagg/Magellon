/**
 * Tests for the PM7d PluginUpdateChip.
 *
 *   - Renders nothing when no update is available.
 *   - Renders a labeled chip with the latest_version when an update
 *     exists, color-coded by severity.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { PluginUpdateChip } from '../../features/plugin-runner/ui/PluginUpdateChip.tsx';

describe('PluginUpdateChip', () => {
    it('renders nothing when there is no update', () => {
        const { container } = render(<PluginUpdateChip update={undefined} />);
        expect(container.textContent).toBe('');
    });

    it('renders a chip with the latest_version on a patch update', () => {
        render(
            <PluginUpdateChip
                update={{
                    plugin_id: 'ctf/CTF Plugin',
                    current_version: '1.0.2',
                    latest_version: '1.0.5',
                    channel: 'stable',
                    severity: 'patch',
                }}
            />,
        );
        const chip = screen.getByTestId('plugin-update-chip');
        expect(chip.textContent).toContain('1.0.5');
        expect(chip.getAttribute('data-severity')).toBe('patch');
    });

    it('marks major updates as major severity (color = error)', () => {
        render(
            <PluginUpdateChip
                update={{
                    plugin_id: 'ctf/CTF Plugin',
                    current_version: '1.0.2',
                    latest_version: '2.0.0',
                    channel: 'stable',
                    severity: 'major',
                }}
            />,
        );
        const chip = screen.getByTestId('plugin-update-chip');
        expect(chip.getAttribute('data-severity')).toBe('major');
    });
});
