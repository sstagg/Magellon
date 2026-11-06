import type ImageInfoDto from '../../../entities/image/types.ts';

/**
 * One filter over all of a session's images: conditions on a field
 * (resolution < 4, magnification ≠ 59000, name contains "ex"), combined in
 * groups with AND or OR, and a group can be negated with NOT.
 */
export type FilterField = 'name' | 'mag' | 'defocus' | 'resolution' | 'pixelSize' | 'children';
export type FilterOperator = 'eq' | 'ne' | 'lt' | 'le' | 'gt' | 'ge' | 'contains' | 'notContains' | 'startsWith' | 'empty' | 'notEmpty';

export interface FilterRule {
    kind: 'rule';
    id: string;
    field: FilterField;
    operator: FilterOperator;
    value: string;
}

export interface FilterGroup {
    kind: 'group';
    id: string;
    combinator: 'and' | 'or';
    not: boolean;
    rules: Array<FilterRule | FilterGroup>;
}

export type ImageFilter = FilterGroup;

export const FILTER_FIELDS: Record<FilterField, {
    label: string;
    unit: string;
    numeric: boolean;
    value: (image: ImageInfoDto) => number | string | null | undefined;
}> = {
    resolution: { label: 'CTF resolution', unit: 'Å', numeric: true, value: (image) => image.resolution },
    mag: { label: 'Magnification', unit: '×', numeric: true, value: (image) => image.mag },
    defocus: { label: 'Defocus', unit: 'μm', numeric: true, value: (image) => image.defocus },
    pixelSize: { label: 'Pixel size', unit: 'Å/pix', numeric: true, value: (image) => image.pixelSize },
    children: { label: 'Children', unit: '', numeric: true, value: (image) => image.children_count ?? 0 },
    name: { label: 'Name', unit: '', numeric: false, value: (image) => image.name },
};

/** applies: which fields it works on (numeric, text or both). */
export const OPERATORS: Record<FilterOperator, { label: string; applies: 'numeric' | 'text' | 'both'; needsValue: boolean }> = {
    eq: { label: '=', applies: 'both', needsValue: true },
    ne: { label: '≠', applies: 'both', needsValue: true },
    lt: { label: '<', applies: 'numeric', needsValue: true },
    le: { label: '≤', applies: 'numeric', needsValue: true },
    gt: { label: '>', applies: 'numeric', needsValue: true },
    ge: { label: '≥', applies: 'numeric', needsValue: true },
    contains: { label: 'contains', applies: 'text', needsValue: true },
    notContains: { label: 'does not contain', applies: 'text', needsValue: true },
    startsWith: { label: 'starts with', applies: 'text', needsValue: true },
    empty: { label: 'is empty', applies: 'both', needsValue: false },
    notEmpty: { label: 'is not empty', applies: 'both', needsValue: false },
};

export const operatorsFor = (field: FilterField): FilterOperator[] =>
    (Object.keys(OPERATORS) as FilterOperator[]).filter((operator) => {
        const applies = OPERATORS[operator].applies;
        return applies === 'both' || applies === (FILTER_FIELDS[field].numeric ? 'numeric' : 'text');
    });

let counter = 0;
const newId = () => `f${(counter++).toString(36)}`;

export const newRule = (field: FilterField = 'resolution'): FilterRule => ({
    kind: 'rule', id: newId(), field, operator: FILTER_FIELDS[field].numeric ? 'le' : 'contains', value: '',
});

export const newGroup = (rules: Array<FilterRule | FilterGroup> = [newRule()]): FilterGroup => ({
    kind: 'group', id: newId(), combinator: 'and', not: false, rules,
});

export const EMPTY_FILTER: ImageFilter = { kind: 'group', id: 'empty', combinator: 'and', not: false, rules: [] };

const isComplete = (rule: FilterRule): boolean =>
    !OPERATORS[rule.operator].needsValue ||
    (rule.value.trim() !== '' && (!FILTER_FIELDS[rule.field].numeric || Number.isFinite(Number(rule.value))));

/** The filter without unfinished conditions and empty groups; null if nothing is left. */
export const activeFilter = (group: FilterGroup): FilterGroup | null => {
    const rules = group.rules.flatMap((node): Array<FilterRule | FilterGroup> => {
        if (node.kind === 'rule') return isComplete(node) ? [node] : [];
        const active = activeFilter(node);
        return active ? [active] : [];
    });
    return rules.length > 0 ? { ...group, rules } : null;
};

const matchesRule = (image: ImageInfoDto, rule: FilterRule): boolean => {
    const field = FILTER_FIELDS[rule.field];
    const raw = field.value(image);
    const missing = raw == null || raw === '';
    if (rule.operator === 'empty') return missing;
    if (rule.operator === 'notEmpty') return !missing;
    // An image without the value isn't equal to anything, and matches nothing else.
    if (missing) return rule.operator === 'ne' || rule.operator === 'notContains';
    if (field.numeric) {
        const a = Number(raw);
        const b = Number(rule.value);
        switch (rule.operator) {
            case 'eq': return a === b;
            case 'ne': return a !== b;
            case 'lt': return a < b;
            case 'le': return a <= b;
            case 'gt': return a > b;
            case 'ge': return a >= b;
            default: return false;
        }
    }
    const a = String(raw).toLowerCase();
    const b = rule.value.trim().toLowerCase();
    switch (rule.operator) {
        case 'eq': return a === b;
        case 'ne': return a !== b;
        case 'contains': return a.includes(b);
        case 'notContains': return !a.includes(b);
        case 'startsWith': return a.startsWith(b);
        default: return false;
    }
};

const matchesGroup = (image: ImageInfoDto, group: FilterGroup): boolean => {
    const test = (node: FilterRule | FilterGroup) =>
        node.kind === 'rule' ? matchesRule(image, node) : matchesGroup(image, node);
    const result = group.combinator === 'and' ? group.rules.every(test) : group.rules.some(test);
    return group.not ? !result : result;
};

/** A test for one image, or null when the filter has no finished condition. */
export const makeImageMatcher = (filter: ImageFilter): ((image: ImageInfoDto) => boolean) | null => {
    const active = activeFilter(filter);
    return active ? (image) => matchesGroup(image, active) : null;
};

export const matchesImageFilter = (image: ImageInfoDto, filter: ImageFilter): boolean =>
    makeImageMatcher(filter)?.(image) ?? true;

export const countActiveFilters = (filter: ImageFilter): number => {
    const count = (group: FilterGroup): number =>
        group.rules.reduce((total, node) => total + (node.kind === 'rule' ? 1 : count(node)), 0);
    const active = activeFilter(filter);
    return active ? count(active) : 0;
};

/** The filter in words: "CTF resolution ≤ 4 Å AND NOT (Magnification = 59000 ×)". */
export const describeFilter = (filter: ImageFilter): string => {
    const rule = (r: FilterRule) => {
        const field = FILTER_FIELDS[r.field];
        const value = OPERATORS[r.operator].needsValue
            ? ` ${field.numeric ? r.value.trim() : `"${r.value.trim()}"`}${field.unit ? ` ${field.unit}` : ''}`
            : '';
        return `${field.label} ${OPERATORS[r.operator].label}${value}`;
    };
    const group = (g: FilterGroup, nested: boolean): string => {
        const text = g.rules
            .map((node) => (node.kind === 'rule' ? rule(node) : group(node, true)))
            .join(g.combinator === 'and' ? ' AND ' : ' OR ');
        const wrapped = (nested || g.not) && g.rules.length > 1 ? `(${text})` : text;
        return g.not ? `NOT ${wrapped}` : wrapped;
    };
    const active = activeFilter(filter);
    return active ? group(active, false) : '';
};

/**
 * The images that match and every image above them, so in the column and tree
 * layouts a matching exposure can still be reached through its grid, square and hole.
 */
export const matchesWithAncestors = (images: ImageInfoDto[], matches: (image: ImageInfoDto) => boolean): Set<string> => {
    const byId = new Map(images.map((image) => [image.oid, image]));
    const shown = new Set<string>();
    images.forEach((image) => {
        if (!matches(image)) return;
        let current: ImageInfoDto | undefined = image;
        while (current && !shown.has(current.oid)) {
            shown.add(current.oid);
            current = current.parent_id ? byId.get(current.parent_id) : undefined;
        }
    });
    return shown;
};
