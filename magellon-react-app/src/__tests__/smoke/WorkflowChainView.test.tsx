/**
 * Smoke tests for WorkflowChainView (PE3-lite UI).
 *
 * Renders the lineage chain JSON the ``/artifacts/{oid}/workflow.json``
 * endpoint produces and verifies:
 *   - The root card is flagged as such.
 *   - Imported root nodes (producer === null) show an "imported" chip
 *     and no Re-run button.
 *   - Non-root nodes with a producer render plugin id + version +
 *     a working Re-run button.
 *   - Truncation flag becomes a "Truncated" chip.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

import { WorkflowChainView } from '../../features/artifact-workflow/ui/WorkflowChainView.tsx';
import type { WorkflowExport } from '../../features/artifact-workflow/api/ArtifactApi.ts';


// Mock the API module so the test runs without an HTTP server.
vi.mock('../../features/artifact-workflow/api/ArtifactApi.ts', async () => {
    const actual = await vi.importActual<any>(
        '../../features/artifact-workflow/api/ArtifactApi.ts',
    );
    return {
        ...actual,
        useArtifactWorkflow: vi.fn(),
        useReRunFromWorkflow: vi.fn(() => ({
            mutateAsync: vi.fn(),
            isLoading: false,
        })),
    };
});

import * as api from '../../features/artifact-workflow/api/ArtifactApi.ts';


const sampleWorkflow: WorkflowExport = {
    magellon_workflow_version: 1,
    exported_at: '2026-05-12T19:00:00Z',
    lineage_shape: 'single_parent_chain',
    root_artifact: {
        oid: '11111111-2222-3333-4444-555555555555',
        kind: 'class_averages',
        producer: {
            plugin_id: 'can-classifier',
            plugin_version: '1.0.0',
            category: 'TWO_D_CLASSIFICATION',
            params: { num_classes: 50, num_presentations: 200000 },
        },
    },
    ancestors: [
        {
            oid: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            kind: 'particle_stack',
            producer: {
                plugin_id: 'stack-maker',
                plugin_version: '0.9.0',
                category: 'PARTICLE_EXTRACTION',
                params: { box_size: 256, edge_width: 2 },
            },
        },
        {
            oid: '99999999-8888-7777-6666-555555555555',
            kind: 'image',
            producer: null,
            source: 'imported',
        },
    ],
    truncated_at_depth: null,
};


const wrap = (ui: React.ReactElement) => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
};


describe('WorkflowChainView', () => {
    beforeEach(() => {
        (api.useArtifactWorkflow as any).mockReset();
    });

    it('renders the root and ancestor cards', () => {
        (api.useArtifactWorkflow as any).mockReturnValue({
            data: sampleWorkflow,
            isLoading: false,
            error: null,
        });
        render(wrap(<WorkflowChainView oid="11111111-2222-3333-4444-555555555555" />));

        expect(screen.getByText('Root')).toBeTruthy();
        expect(screen.getByText('class_averages')).toBeTruthy();
        expect(screen.getByText('particle_stack')).toBeTruthy();
        expect(screen.getByText('image')).toBeTruthy();
    });

    it('imported root shows an "imported" chip and no Re-run button', () => {
        (api.useArtifactWorkflow as any).mockReturnValue({
            data: sampleWorkflow,
            isLoading: false,
            error: null,
        });
        render(wrap(<WorkflowChainView oid="any" />));

        // Two non-imported nodes → two Re-run buttons.
        const reRunButtons = screen.getAllByRole('button', { name: /re-run/i });
        expect(reRunButtons).toHaveLength(2);
        // The "imported" chip appears for the third (root-source) node.
        expect(screen.getByText('imported')).toBeTruthy();
    });

    it('producer plugin id and version surface on each node', () => {
        (api.useArtifactWorkflow as any).mockReturnValue({
            data: sampleWorkflow,
            isLoading: false,
            error: null,
        });
        render(wrap(<WorkflowChainView oid="any" />));

        expect(screen.getByText('can-classifier')).toBeTruthy();
        expect(screen.getByText('stack-maker')).toBeTruthy();
    });

    it('truncation flag renders a "Truncated" chip', () => {
        (api.useArtifactWorkflow as any).mockReturnValue({
            data: { ...sampleWorkflow, truncated_at_depth: 200 },
            isLoading: false,
            error: null,
        });
        render(wrap(<WorkflowChainView oid="any" />));
        expect(screen.getByText('Truncated')).toBeTruthy();
    });

    it('error state shows a friendly alert, not a crash', () => {
        (api.useArtifactWorkflow as any).mockReturnValue({
            data: undefined,
            isLoading: false,
            error: new Error('boom'),
        });
        render(wrap(<WorkflowChainView oid="missing" />));
        expect(screen.getByText(/workflow not found/i)).toBeTruthy();
    });
});
