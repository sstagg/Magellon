/**
 * Tests for the PM7c PluginReplicas drawer.
 *
 * Pins:
 *   - One row per replica returned by GET /plugins/{id}/replicas.
 *   - Status chip color tracks Healthy/Stale/Lost.
 *   - Empty array → "No replicas currently announcing." copy.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import React from 'react';
import { PluginReplicas } from '../../features/plugin-runner/ui/PluginReplicas.tsx';
import type { ReplicaInfo } from '../../features/plugin-runner/api/PluginApi.ts';

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

const THREE_REPLICAS: ReplicaInfo[] = [
    {
        instance_id: 'i-aaa',
        last_heartbeat_at: new Date(Date.now() - 5_000).toISOString(),
        in_flight_task_count: 0,
        status: 'Healthy',
    },
    {
        instance_id: 'i-bbb',
        last_heartbeat_at: new Date(Date.now() - 45_000).toISOString(),
        in_flight_task_count: 1,
        status: 'Lost',
    },
    {
        instance_id: 'i-ccc',
        last_heartbeat_at: new Date(Date.now() - 35_000).toISOString(),
        in_flight_task_count: 0,
        status: 'Stale',
    },
];

beforeEach(() => {
    getMock.mockReset();
});

describe('PluginReplicas', () => {
    it('renders one row per replica with the instance_id', async () => {
        getMock.mockResolvedValue({ data: THREE_REPLICAS });
        render(_withQuery(<PluginReplicas pluginId="ctf/ctffind4" />));

        expect(await screen.findByText('i-aaa')).toBeTruthy();
        expect(await screen.findByText('i-bbb')).toBeTruthy();
        expect(await screen.findByText('i-ccc')).toBeTruthy();
    });

    it('renders status chips for Healthy / Lost / Stale', async () => {
        getMock.mockResolvedValue({ data: THREE_REPLICAS });
        render(_withQuery(<PluginReplicas pluginId="ctf/ctffind4" />));

        expect(await screen.findByText('Healthy')).toBeTruthy();
        expect(await screen.findByText('Lost')).toBeTruthy();
        expect(await screen.findByText('Stale')).toBeTruthy();
    });

    it('shows no-replicas hint when the response is empty', async () => {
        getMock.mockResolvedValue({ data: [] });
        render(_withQuery(<PluginReplicas pluginId="ctf/ctffind4" />));
        expect(
            await screen.findByText(/no replicas currently announcing/i),
        ).toBeTruthy();
    });
});
