import { describe, expect, it } from 'vitest';
import { activeFilter, countActiveFilters, describeFilter, newGroup, newRule, type FilterGroup, type FilterRule } from './imageFilter.ts';
import { filterParam } from '../api/imagesApiReactQuery.tsx';

// Matching images happens on the server (CoreService/tests/test_image_filter.py);
// here only what the page does with the filter before sending it.
const rule = (field: FilterRule['field'], operator: FilterRule['operator'], value = ''): FilterRule =>
    ({ ...newRule(field), operator, value });
const group = (combinator: 'and' | 'or', rules: FilterGroup['rules'], not = false): FilterGroup =>
    ({ ...newGroup(rules), combinator, not });

describe('image filter', () => {
    it('leaves unfinished conditions and empty groups out', () => {
        const filter = group('and', [rule('resolution', 'le', ''), rule('mag', 'gt', 'abc'), group('or', [])]);
        expect(activeFilter(filter)).toBeNull();
        expect(filterParam(filter)).toBeUndefined();
        expect(countActiveFilters(group('and', [rule('resolution', 'le', '4'), rule('mag', 'gt', '')]))).toBe(1);
    });

    it('sends only the finished part, in the shape the server takes', () => {
        const sent = JSON.parse(filterParam(group('or', [rule('resolution', 'le', '4'), rule('mag', 'eq', '')], true))!);
        expect(sent).toMatchObject({ kind: 'group', combinator: 'or', not: true, rules: [{ kind: 'rule', field: 'resolution', operator: 'le', value: '4' }] });
        expect(sent.rules).toHaveLength(1);
    });

    it('describes itself', () => {
        const filter = group('and', [rule('resolution', 'le', '4'), group('or', [rule('mag', 'eq', '59000'), rule('name', 'contains', 'ex')], true)]);
        expect(describeFilter(filter)).toBe('CTF resolution ≤ 4 Å AND NOT (Magnification = 59000 × OR Name contains "ex")');
    });
});
