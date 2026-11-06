import { describe, expect, it } from 'vitest';
import type ImageInfoDto from '../../../entities/image/types.ts';
import {
    countActiveFilters, describeFilter, makeImageMatcher, matchesWithAncestors, newGroup, newRule,
    type FilterGroup, type FilterRule,
} from './imageFilter.ts';

const image = (oid: string, extra: Partial<ImageInfoDto> = {}): ImageInfoDto => ({ oid, name: oid, mag: 59000, ...extra });
const rule = (field: FilterRule['field'], operator: FilterRule['operator'], value = ''): FilterRule =>
    ({ ...newRule(field), operator, value });
const group = (combinator: 'and' | 'or', rules: FilterGroup['rules'], not = false): FilterGroup =>
    ({ ...newGroup(rules), combinator, not });
const names = (images: ImageInfoDto[], filter: FilterGroup) => images.filter(makeImageMatcher(filter)!).map((i) => i.oid);

const images = [
    image('good', { resolution: 3.2, defocus: -1.5 }),
    image('poor', { resolution: 8, defocus: -2 }),
    image('noctf', { mag: 1700 }),
];

describe('image filter', () => {
    it('compares numbers, and an image without the value matches only "not equal"', () => {
        expect(names(images, group('and', [rule('resolution', 'le', '4')]))).toEqual(['good']);
        expect(names(images, group('and', [rule('mag', 'ne', '59000')]))).toEqual(['noctf']);
        expect(names(images, group('and', [rule('resolution', 'ne', '8')]))).toEqual(['good', 'noctf']);
        expect(names(images, group('and', [rule('resolution', 'empty')]))).toEqual(['noctf']);
    });

    it('combines with AND, OR and NOT, in nested groups', () => {
        const either = group('or', [rule('resolution', 'lt', '4'), rule('mag', 'eq', '1700')]);
        expect(names(images, either)).toEqual(['good', 'noctf']);
        expect(names(images, group('and', [either], true))).toEqual(['poor']);
        expect(names(images, group('and', [rule('mag', 'eq', '59000'), group('or', [rule('defocus', 'gt', '-1.8')])]))).toEqual(['good']);
    });

    it('matches names as text, ignoring case', () => {
        expect(names(images, group('and', [rule('name', 'contains', 'OO')]))).toEqual(['good', 'poor']);
        expect(names(images, group('and', [rule('name', 'notContains', 'oo')]))).toEqual(['noctf']);
    });

    it('leaves unfinished conditions out', () => {
        const filter = group('and', [rule('resolution', 'le', ''), rule('mag', 'gt', 'abc')]);
        expect(makeImageMatcher(filter)).toBeNull();
        expect(countActiveFilters(filter)).toBe(0);
        expect(countActiveFilters(group('and', [rule('resolution', 'le', '4'), rule('mag', 'gt', '')]))).toBe(1);
    });

    it('describes itself', () => {
        const filter = group('and', [rule('resolution', 'le', '4'), group('or', [rule('mag', 'eq', '59000'), rule('name', 'contains', 'ex')], true)]);
        expect(describeFilter(filter)).toBe('CTF resolution ≤ 4 Å AND NOT (Magnification = 59000 × OR Name contains "ex")');
    });

    it('keeps the ancestors of a match', () => {
        const tree = [image('gr'), image('sq', { parent_id: 'gr' }), image('ex', { parent_id: 'sq', resolution: 3 }), image('other')];
        expect([...matchesWithAncestors(tree, (i) => i.resolution === 3)].sort()).toEqual(['ex', 'gr', 'sq']);
    });
});
