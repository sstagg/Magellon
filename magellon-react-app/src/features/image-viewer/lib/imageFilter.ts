/**
 * One filter over all of a session's images: conditions on a field
 * (resolution < 4, magnification ≠ 59000, name contains "ex"), combined in
 * groups with AND or OR, and a group can be negated with NOT.
 *
 * Only the filter's shape lives here: the server applies it
 * (CoreService/services/image_filter.py), with the same fields and operators.
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

export const FILTER_FIELDS: Record<FilterField, { label: string; unit: string; numeric: boolean }> = {
    resolution: { label: 'CTF resolution', unit: 'Å', numeric: true },
    mag: { label: 'Magnification', unit: '×', numeric: true },
    defocus: { label: 'Defocus', unit: 'μm', numeric: true },
    pixelSize: { label: 'Pixel size', unit: 'Å/pix', numeric: true },
    children: { label: 'Children', unit: '', numeric: true },
    name: { label: 'Name', unit: '', numeric: false },
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

