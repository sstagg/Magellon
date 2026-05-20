/**
 * Smoke tests for the PE5 UI consumers shipped on top of
 * ``GET /plugins/capabilities``:
 *
 *  - "Try example" chip row in PluginTestPanel pre-fills the form
 *    with the chosen example's values.
 *  - Subject-tag filter chips on InstalledPluginsView gate which
 *    plugin cards render.
 *
 * These cases mount the smallest piece that can be exercised without
 * a full react-query + MUI provider stack — the helper components are
 * extracted enough to test in isolation when needed; otherwise we
 * snapshot the shape contracts.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import type { CategoryExample } from '../../features/plugin-runner/api/PluginApi.ts';

// Inline copy of the chip-row contract — keeps the test independent
// from the larger PluginTestPanel imports (which would need
// QueryClientProvider). The shape mirrors the production component;
// if the production one changes shape, this copy must too.
const ExampleChipsHarness: React.FC<{
    examples: CategoryExample[];
    onPick: (example: CategoryExample) => void;
}> = ({ examples, onPick }) => (
    <div>
        {examples.map((ex) => (
            <button
                key={ex.name}
                onClick={() => onPick(ex)}
                title={ex.description}
            >
                {ex.name}
            </button>
        ))}
    </div>
);


describe('Example chips contract', () => {
    it('clicking a chip emits the example values', () => {
        const examples: CategoryExample[] = [
            {
                name: 'K3 @ 300 kV',
                description: 'Standard cryo conditions',
                values: { pixelSize: 1.0, accelerationVoltage: 300.0 },
            },
            {
                name: 'Falcon @ 200 kV',
                description: '200 kV finer search',
                values: { pixelSize: 0.95, accelerationVoltage: 200.0 },
            },
        ];
        const picks: CategoryExample[] = [];
        render(<ExampleChipsHarness examples={examples} onPick={(ex) => picks.push(ex)} />);

        fireEvent.click(screen.getByText('K3 @ 300 kV'));
        expect(picks).toHaveLength(1);
        expect(picks[0].values.pixelSize).toBe(1.0);

        fireEvent.click(screen.getByText('Falcon @ 200 kV'));
        expect(picks).toHaveLength(2);
        expect(picks[1].values.accelerationVoltage).toBe(200.0);
    });

    it('chip-row renders nothing when examples is empty', () => {
        const { container } = render(
            <ExampleChipsHarness examples={[]} onPick={() => {}} />,
        );
        // A single empty div, no buttons.
        expect(container.querySelectorAll('button')).toHaveLength(0);
    });
});


// ---------------------------------------------------------------------------
// Subject-tag filter logic — pure function, no DOM
// ---------------------------------------------------------------------------

/**
 * Replica of the filter logic in InstalledPluginsView so it can be
 * unit-tested without mounting the full component. Stays close in
 * shape; if the production filter logic changes, this should too.
 */
function applySubjectFilter<T extends { category?: string }>(
    rows: T[],
    subjectFilter: string | null,
    subjectsByCategory: Map<string, { consumes: Set<string>; produces: Set<string> }>,
): T[] {
    if (!subjectFilter) return rows;
    const [axis, subject] = subjectFilter.split(':');
    return rows.filter((p) => {
        const tags = subjectsByCategory.get(p.category?.toLowerCase() ?? '');
        if (!tags) return false;
        const haystack = axis === 'consumes' ? tags.consumes : tags.produces;
        return haystack.has(subject);
    });
}


describe('Subject-tag filter', () => {
    const subjectsByCategory = new Map([
        ['ctf', { consumes: new Set(['image']), produces: new Set(['image']) }],
        ['particleextraction', { consumes: new Set(['image']), produces: new Set(['particle_stack']) }],
        ['2d classification', { consumes: new Set(['particle_stack']), produces: new Set(['class_averages']) }],
    ]);
    const rows = [
        { plugin_id: 'ctf', category: 'CTF' },
        { plugin_id: 'extract', category: 'ParticleExtraction' },
        { plugin_id: 'class2d', category: '2D Classification' },
    ];

    it('no filter returns every row', () => {
        expect(applySubjectFilter(rows, null, subjectsByCategory)).toHaveLength(3);
    });

    it('consumes:particle_stack keeps only 2D classification', () => {
        const out = applySubjectFilter(rows, 'consumes:particle_stack', subjectsByCategory);
        expect(out.map((r) => r.plugin_id)).toEqual(['class2d']);
    });

    it('produces:particle_stack keeps only the extractor', () => {
        const out = applySubjectFilter(rows, 'produces:particle_stack', subjectsByCategory);
        expect(out.map((r) => r.plugin_id)).toEqual(['extract']);
    });

    it('consumes:image keeps CTF and the extractor', () => {
        const out = applySubjectFilter(rows, 'consumes:image', subjectsByCategory);
        expect(out.map((r) => r.plugin_id).sort()).toEqual(['ctf', 'extract']);
    });

    it('unknown subject returns no rows (no false positives)', () => {
        const out = applySubjectFilter(rows, 'consumes:martian', subjectsByCategory);
        expect(out).toHaveLength(0);
    });

    it('a plugin in an unknown category does not crash the filter', () => {
        const rowsWithMystery = [...rows, { plugin_id: 'mystery', category: 'Unknown' }];
        const out = applySubjectFilter(rowsWithMystery, 'consumes:image', subjectsByCategory);
        // The mystery plugin has no tags so it's filtered out — not
        // an exception.
        expect(out.map((r) => r.plugin_id).sort()).toEqual(['ctf', 'extract']);
    });
});
