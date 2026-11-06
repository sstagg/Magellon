import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    MenuItem,
    Stack,
    Switch,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Typography,
} from '@mui/material';
import { Add, Close, DeleteOutlined, FilterList } from '@mui/icons-material';
import { useFilterSummary } from '../api/usePagedImagesHook.ts';
import type { FilterSummary } from '../api/imagesApiReactQuery.tsx';
import {
    FILTER_FIELDS, OPERATORS, activeFilter, describeFilter, newGroup, newRule, operatorsFor,
    type FilterField, type FilterGroup, type FilterRule, type ImageFilter,
} from '../lib/imageFilter.ts';

export type { ImageFilter };

interface ImageFilterDialogProps {
    open: boolean;
    onClose: () => void;
    onApplyFilter: (filter: ImageFilter) => void;
    currentFilter: ImageFilter;
    sessionName: string;
}

type Hints = Partial<Record<FilterField, string>>;

/** What the session's values look like, under each value box (from the server's summary). */
const valueHints = (fields: FilterSummary['fields'] | undefined): Hints => {
    const hints: Hints = {};
    if (!fields) return hints;
    (Object.keys(FILTER_FIELDS) as FilterField[]).forEach((field) => {
        const info = fields[field];
        if (!info || !FILTER_FIELDS[field].numeric) return;
        if (!info.count) hints[field] = 'No image in this session has it';
        else if (info.values) hints[field] = `Values: ${info.values.join(', ')}`;
        else hints[field] = `${info.min} to ${info.max} ${FILTER_FIELDS[field].unit} (${info.count} images)`;
    });
    return hints;
};

const RuleEditor: React.FC<{
    rule: FilterRule;
    hints: Hints;
    onChange: (rule: FilterRule) => void;
    onRemove: () => void;
}> = ({ rule, hints, onChange, onRemove }) => {
    const field = FILTER_FIELDS[rule.field];
    const changeField = (next: FilterField) => {
        const operator = operatorsFor(next).includes(rule.operator) ? rule.operator : newRule(next).operator;
        onChange({ ...rule, field: next, operator, value: FILTER_FIELDS[next].numeric === field.numeric ? rule.value : '' });
    };
    return (
        <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }} data-testid="filter-rule">
            <TextField select size="small" label="Field" value={rule.field} onChange={(e) => changeField(e.target.value as FilterField)} sx={{ width: 160, flexShrink: 0 }}>
                {(Object.keys(FILTER_FIELDS) as FilterField[]).map((key) => (
                    <MenuItem key={key} value={key}>{FILTER_FIELDS[key].label}</MenuItem>
                ))}
            </TextField>
            <TextField select size="small" label="Is" value={rule.operator} onChange={(e) => onChange({ ...rule, operator: e.target.value as FilterRule['operator'] })} sx={{ width: 150, flexShrink: 0 }}>
                {operatorsFor(rule.field).map((operator) => (
                    <MenuItem key={operator} value={operator}>{OPERATORS[operator].label}</MenuItem>
                ))}
            </TextField>
            {OPERATORS[rule.operator].needsValue && (
                <TextField
                    size="small"
                    label={field.unit ? `Value (${field.unit})` : 'Value'}
                    type={field.numeric ? 'number' : 'text'}
                    value={rule.value}
                    onChange={(e) => onChange({ ...rule, value: e.target.value })}
                    helperText={hints[rule.field]}
                    slotProps={{ htmlInput: { step: 'any' } }}
                    sx={{ flex: 1, minWidth: 120 }}
                />
            )}
            <Box sx={{ flex: OPERATORS[rule.operator].needsValue ? 0 : 1 }} />
            <IconButton aria-label="Remove condition" onClick={onRemove} size="small" sx={{ mt: 0.5 }}>
                <DeleteOutlined fontSize="small" />
            </IconButton>
        </Stack>
    );
};

const GroupEditor: React.FC<{
    group: FilterGroup;
    hints: Hints;
    depth: number;
    onChange: (group: FilterGroup) => void;
    onRemove?: () => void;
}> = ({ group, hints, depth, onChange, onRemove }) => {
    const replace = (index: number, node: FilterRule | FilterGroup) =>
        onChange({ ...group, rules: group.rules.map((current, i) => (i === index ? node : current)) });
    const remove = (index: number) => onChange({ ...group, rules: group.rules.filter((_, i) => i !== index) });
    const meaning = group.not
        ? (group.combinator === 'and' ? 'Not all of these' : 'None of these')
        : (group.combinator === 'and' ? 'All of these' : 'Any of these');
    return (
        <Box
            data-testid="filter-group"
            sx={depth > 0 ? { border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 } : undefined}
        >
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.5 }}>
                <ToggleButtonGroup
                    size="small"
                    exclusive
                    value={group.combinator}
                    onChange={(_, value) => value && onChange({ ...group, combinator: value })}
                >
                    <ToggleButton value="and" sx={{ px: 1.5, py: 0.25 }}>AND</ToggleButton>
                    <ToggleButton value="or" sx={{ px: 1.5, py: 0.25 }}>OR</ToggleButton>
                </ToggleButtonGroup>
                <FormControlLabel
                    control={<Switch size="small" checked={group.not} onChange={(e) => onChange({ ...group, not: e.target.checked })} />}
                    label="NOT"
                    sx={{ mr: 0 }}
                />
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{meaning} must match</Typography>
                <Box sx={{ flex: 1 }} />
                {onRemove && (
                    <IconButton aria-label="Remove group" onClick={onRemove} size="small">
                        <DeleteOutlined fontSize="small" />
                    </IconButton>
                )}
            </Stack>
            <Stack spacing={1.5}>
                {group.rules.map((node, index) =>
                    node.kind === 'rule' ? (
                        <RuleEditor key={node.id} rule={node} hints={hints} onChange={(next) => replace(index, next)} onRemove={() => remove(index)} />
                    ) : (
                        <GroupEditor key={node.id} group={node} hints={hints} depth={depth + 1} onChange={(next) => replace(index, next)} onRemove={() => remove(index)} />
                    )
                )}
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button size="small" startIcon={<Add />} onClick={() => onChange({ ...group, rules: [...group.rules, newRule()] })}>
                    Condition
                </Button>
                {depth < 2 && (
                    <Button size="small" startIcon={<Add />} onClick={() => onChange({ ...group, rules: [...group.rules, newGroup([newRule(), newRule('mag')])] })}>
                        Group
                    </Button>
                )}
            </Stack>
        </Box>
    );
};

/** One filter for all the session's images, built from conditions joined by AND, OR and NOT. */
export const ImageFilterDialog: React.FC<ImageFilterDialogProps> = ({ open, onClose, onApplyFilter, currentFilter, sessionName }) => {
    const [draft, setDraft] = useState<FilterGroup>(() => newGroup());

    useEffect(() => {
        if (open) setDraft(currentFilter.rules.length > 0 ? currentFilter : newGroup());
    }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

    // The server counts the matches, checked as you pause typing.
    const { data: summary, isFetching, isError } = useFilterSummary(sessionName, draft, open);
    const hints = useMemo(() => valueHints(summary?.fields), [summary]);
    const hasConditions = activeFilter(draft) !== null;
    const summaryText = describeFilter(draft);

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
                <FilterList sx={{ mr: 1 }} />
                Filter Images
                <Button onClick={onClose} size="small" color="inherit" startIcon={<Close />} sx={{ ml: 'auto' }}>
                    Close
                </Button>
            </DialogTitle>
            <Divider />
            <DialogContent>
                <GroupEditor group={draft} hints={hints} depth={0} onChange={setDraft} />
                <Alert severity={isError ? 'error' : hasConditions && summary?.matching === 0 ? 'warning' : 'info'} icon={false} sx={{ mt: 2 }} data-testid="filter-preview">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {isError ? 'Could not count the matching images'
                            : summary ? `${summary.matching} of ${summary.total} images match` : 'Counting...'}
                        {isFetching && summary && ' (updating...)'}
                    </Typography>
                    {summaryText && <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>{summaryText}</Typography>}
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>
                        The columns and tree also keep the grids, squares and holes above a matching image.
                    </Typography>
                </Alert>
            </DialogContent>
            <Divider />
            <DialogActions>
                <Button onClick={() => setDraft(newGroup())} color="inherit">Reset All</Button>
                <Button
                    onClick={() => {
                        onApplyFilter(draft);
                        onClose();
                    }}
                    variant="contained"
                >
                    Apply Filters
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ImageFilterDialog;
