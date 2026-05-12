/**
 * Smoke tests for the PE4 registry page.
 *
 * Mocks ``useRegistryIndex`` so the test runs without an HTTP server.
 * What we pin:
 *
 *  - Hub plugins surface in the Browse tab.
 *  - Update-inbox count + tab list filter to plugins with
 *    ``update_available``.
 *  - Local-only tab shows installed plugins absent from the hub.
 *  - Hub failure alert renders without crashing the page.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

import { PluginRegistryPage } from '../../pages/plugins/PluginRegistryPage.tsx';
import type { RegistryIndexResponse } from '../../features/plugin-registry/api/RegistryApi.ts';


vi.mock('../../features/plugin-registry/api/RegistryApi.ts', async () => {
    const actual = await vi.importActual<any>(
        '../../features/plugin-registry/api/RegistryApi.ts',
    );
    return { ...actual, useRegistryIndex: vi.fn() };
});

import * as api from '../../features/plugin-registry/api/RegistryApi.ts';


const sample: RegistryIndexResponse = {
    hub_url: 'https://magellon.org',
    hub_status: 'ok',
    plugins: [
        {
            plugin_id: 'fft-classical',
            display_name: 'Classical FFT',
            category: 'fft',
            is_verified: true,
            hub_versions: [{ version: '1.2.0' }],
            latest_hub_version: '1.2.0',
            installed_version: '1.1.0',
            install_method: 'uv',
            update_available: true,
            source: 'hub',
        },
        {
            plugin_id: 'ctf-ctffind',
            display_name: 'CTF (ctffind)',
            category: 'ctf',
            is_verified: false,
            hub_versions: [{ version: '4.1.0' }],
            latest_hub_version: '4.1.0',
            installed_version: '4.1.0',
            install_method: 'docker',
            update_available: false,
            source: 'hub',
        },
        {
            plugin_id: 'in-house-tool',
            display_name: 'in-house-tool',
            is_verified: false,
            hub_versions: [],
            latest_hub_version: null,
            installed_version: '0.1.0',
            install_method: 'uv',
            update_available: false,
            source: 'local-only',
        },
    ],
};


const wrap = (ui: React.ReactElement) => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return (
        <QueryClientProvider client={qc}>
            <MemoryRouter>{ui}</MemoryRouter>
        </QueryClientProvider>
    );
};


describe('PluginRegistryPage', () => {
    beforeEach(() => {
        (api.useRegistryIndex as any).mockReset();
    });

    it('Browse tab lists hub plugins with installed annotations', () => {
        (api.useRegistryIndex as any).mockReturnValue({
            data: sample,
            isLoading: false,
            error: null,
        });
        render(wrap(<PluginRegistryPage />));

        // Hub plugins surface in Browse (default tab).
        expect(screen.getByText('Classical FFT')).toBeTruthy();
        expect(screen.getByText('CTF (ctffind)')).toBeTruthy();
        // Local-only doesn't surface as a display_name in browse tab —
        // the local-only plugin_id is also "in-house-tool" so any
        // chip-as-plugin-id rendering would slip through; we check
        // that the *display_name* heading isn't there by uniqueness.
        const inHouseHeadings = screen.queryAllByRole('heading', { name: /in-house-tool/i });
        expect(inHouseHeadings).toHaveLength(0);
    });

    it('Update inbox tab filters to plugins with update_available', () => {
        (api.useRegistryIndex as any).mockReturnValue({
            data: sample,
            isLoading: false,
            error: null,
        });
        render(wrap(<PluginRegistryPage />));

        fireEvent.click(screen.getByText('Update inbox'));
        expect(screen.getByText('Classical FFT')).toBeTruthy();
        // The other hub plugin (CTF) is at latest — not shown here.
        expect(screen.queryByText('CTF (ctffind)')).toBeNull();
    });

    it('Local-only tab shows installed-but-not-on-hub plugins', () => {
        (api.useRegistryIndex as any).mockReturnValue({
            data: sample,
            isLoading: false,
            error: null,
        });
        render(wrap(<PluginRegistryPage />));

        fireEvent.click(screen.getByText('Local-only'));
        // Card heading + chip both display the id — accept any occurrence.
        expect(screen.getAllByText('in-house-tool').length).toBeGreaterThan(0);
        // Hub plugins don't show here.
        expect(screen.queryByText('Classical FFT')).toBeNull();
    });

    it('Hub unreachable renders a warning + falls back to local-only list', () => {
        (api.useRegistryIndex as any).mockReturnValue({
            data: {
                ...sample,
                hub_status: 'unreachable',
                hub_error: 'no route to hub',
                plugins: sample.plugins.filter((p) => p.source === 'local-only'),
            },
            isLoading: false,
            error: null,
        });
        render(wrap(<PluginRegistryPage />));

        expect(screen.getByText(/Hub status: unreachable/i)).toBeTruthy();
        // Local-only plugins are still listed when switching to that tab.
        fireEvent.click(screen.getByText('Local-only'));
        expect(screen.getAllByText('in-house-tool').length).toBeGreaterThan(0);
    });

    it('Loading state renders a spinner, not a crash', () => {
        (api.useRegistryIndex as any).mockReturnValue({
            data: undefined,
            isLoading: true,
            error: null,
        });
        const { container } = render(wrap(<PluginRegistryPage />));
        // MUI's CircularProgress renders as svg.
        expect(container.querySelector('svg')).toBeTruthy();
    });
});
