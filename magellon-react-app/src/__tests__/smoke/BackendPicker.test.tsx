/**
 * Tests for the BackendPicker component (X.1 backend pinning UI).
 *
 * Pins the contract the rest of the runner depends on:
 *
 *  - Hidden when the category has fewer than 2 live backends
 *    (single-impl categories see no UI noise; the existing
 *    category-default routing is unchanged).
 *  - Renders one option per backend plus an "Auto" sentinel when
 *    >= 2 backends exist.
 *  - Picking a backend calls onChange with that backend_id.
 *  - Picking "Auto" calls onChange(null).
 *  - Surfaces the operator-pinned default with a badge.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import React from 'react';
import { BackendPicker } from '../../features/plugin-runner/ui/BackendPicker.tsx';
import type { CapabilitiesResponse } from '../../features/plugin-runner/api/PluginApi.ts';

// Mock the axios client at the module level so the hook fetches
// our canned response instead of hitting the network. ``vi.mock`` is
// hoisted above this file's top-level declarations, so the mock factory
// can't close over a regular ``const``; use ``vi.hoisted`` to defeat
// the hoist trap.
const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));
vi.mock('../../shared/api/AxiosClient.ts', () => ({
    default: () => ({ get: getMock }),
}));
vi.mock('../../shared/config/settings.ts', () => ({
    settings: { ConfigData: { SERVER_API_URL: 'http://test' } },
}));

function _withQuery(ui: React.ReactNode) {
    const qc = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const TWO_BACKENDS_RESPONSE: CapabilitiesResponse = {
    sdk_version: '2.0.0',
    categories: [
        {
            code: 2,
            name: 'CTF',
            description: 'Contrast Transfer Function',
            default_backend: 'ctf-ctffind4',
            backends: [
                {
                    backend_id: 'ctffind4',
                    plugin_id: 'ctf/ctf-ctffind4',
                    name: 'ctf-ctffind4',
                    version: '0.4.1',
                    schema_version: '1',
                    capabilities: ['cpu_intensive'],
                    isolation: 'container',
                    default_transport: 'rmq',
                    live_replicas: 1,
                    enabled: true,
                    is_default_for_category: true,
                },
                {
                    backend_id: 'gctf',
                    plugin_id: 'ctf/ctf-gctf',
                    name: 'ctf-gctf',
                    version: '1.0.0',
                    schema_version: '1',
                    capabilities: ['gpu_required'],
                    isolation: 'container',
                    default_transport: 'rmq',
                    live_replicas: 1,
                    enabled: true,
                    is_default_for_category: false,
                },
            ],
        },
    ],
};

const ONE_BACKEND_RESPONSE: CapabilitiesResponse = {
    sdk_version: '2.0.0',
    categories: [
        {
            code: 2,
            name: 'CTF',
            description: 'Contrast Transfer Function',
            default_backend: 'ctf-only',
            backends: [
                {
                    backend_id: 'only',
                    plugin_id: 'ctf/ctf-only',
                    name: 'ctf-only',
                    version: '0.1.0',
                    schema_version: '1',
                    capabilities: [],
                    isolation: 'container',
                    default_transport: 'rmq',
                    live_replicas: 1,
                    enabled: true,
                    is_default_for_category: true,
                },
            ],
        },
    ],
};

beforeEach(() => {
    getMock.mockReset();
});

describe('BackendPicker', () => {
    it('renders nothing when category has fewer than 2 backends', async () => {
        getMock.mockResolvedValue({ data: ONE_BACKEND_RESPONSE });
        const onChange = vi.fn();
        const { container } = render(_withQuery(
            <BackendPicker category="CTF" value={null} onChange={onChange} />,
        ));
        // The hook is in flight on first render — let it resolve.
        await screen.findByText(/.*/, undefined, { timeout: 1000 }).catch(() => {});
        // Even after the response, no Backend label is rendered.
        expect(container.textContent).not.toContain('Backend');
        // Single-backend categories: no picker means no spurious noise.
    });

    it('renders nothing when capabilities request fails', async () => {
        getMock.mockRejectedValue(new Error('boom'));
        const onChange = vi.fn();
        const { container } = render(_withQuery(
            <BackendPicker category="CTF" value={null} onChange={onChange} />,
        ));
        await new Promise((r) => setTimeout(r, 50));
        expect(container.textContent).not.toContain('Backend');
    });

    it('shows the picker + default badge when 2+ backends exist', async () => {
        getMock.mockResolvedValue({ data: TWO_BACKENDS_RESPONSE });
        const onChange = vi.fn();
        render(_withQuery(
            <BackendPicker category="CTF" value={null} onChange={onChange} />,
        ));

        // Backend label appears.
        await screen.findByText(/^Backend$/, { exact: false });
        // Default badge surfaces the operator-pinned backend.
        expect(await screen.findByText(/default: ctffind4/i)).toBeTruthy();
        // The "Auto" sentinel is the current value (MUI's renderValue
        // collapses to "Auto (use category default)" when the
        // ``__auto__`` option is selected).
        expect(screen.getByText(/Auto.*category default/i)).toBeTruthy();
    });

    it('calls onChange with backend_id when a specific backend is picked', async () => {
        getMock.mockResolvedValue({ data: TWO_BACKENDS_RESPONSE });
        const onChange = vi.fn();
        render(_withQuery(
            <BackendPicker category="CTF" value={null} onChange={onChange} />,
        ));

        // Open the select. MUI renders the dropdown trigger as an
        // element with role=combobox.
        await screen.findByText(/^Backend$/, { exact: false });
        const trigger = screen.getByRole('combobox');
        fireEvent.mouseDown(trigger);

        // Pick the gctf option from the popup.
        const gctfOption = await screen.findByRole('option', { name: /gctf/i });
        fireEvent.click(gctfOption);
        expect(onChange).toHaveBeenCalledWith('gctf');
    });

    it('calls onChange(null) when "Auto" is picked while a backend is pinned', async () => {
        getMock.mockResolvedValue({ data: TWO_BACKENDS_RESPONSE });
        const onChange = vi.fn();
        render(_withQuery(
            <BackendPicker category="CTF" value="gctf" onChange={onChange} />,
        ));
        await screen.findByText(/^Backend$/, { exact: false });
        const trigger = screen.getByRole('combobox');
        fireEvent.mouseDown(trigger);

        const autoOption = await screen.findByRole('option', { name: /^Auto/i });
        fireEvent.click(autoOption);
        expect(onChange).toHaveBeenCalledWith(null);
    });

    it('surfaces the no-silent-fallback warning when a backend is pinned', async () => {
        getMock.mockResolvedValue({ data: TWO_BACKENDS_RESPONSE });
        const onChange = vi.fn();
        render(_withQuery(
            <BackendPicker category="CTF" value="gctf" onChange={onChange} />,
        ));
        // The hint copy makes clear that pinning is binding — this is
        // the part of the X.1 contract operators most need to internalize.
        expect(await screen.findByText(/no silent fallback/i)).toBeTruthy();
    });

    it('matches category name case-insensitively', async () => {
        getMock.mockResolvedValue({ data: TWO_BACKENDS_RESPONSE });
        const onChange = vi.fn();
        // Plugin's category prop arrives as "ctf" (lowercased on the
        // PluginSummary); capabilities serves "CTF". The picker must
        // match across that case difference or it'd never appear.
        render(_withQuery(
            <BackendPicker category="ctf" value={null} onChange={onChange} />,
        ));
        await screen.findByText(/^Backend$/, { exact: false });
    });
});
