import React from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    TextField,
    FormControlLabel,
    Checkbox,
    MenuItem,
    Typography,
    Tooltip,
    InputAdornment,
} from '@mui/material';
import { ChevronDown } from 'lucide-react';
import type { JsonSchema } from '../api/PluginApi.ts';

export interface SchemaFormProps {
    schema: JsonSchema;
    value: Record<string, any>;
    onChange: (next: Record<string, any>) => void;
    disabled?: boolean;
}

/**
 * Renders a Pydantic-derived JSON schema as MUI form fields.
 *
 * If any property declares ui_group, fields are grouped into accordions
 * ordered by the minimum ui_order in each group. Otherwise falls back
 * to a flat list. Respects ui_widget:"hidden" / ui_hidden.
 */
export const SchemaForm: React.FC<SchemaFormProps> = ({ schema, value, onChange, disabled }) => {
    if (!schema?.properties) {
        return (
            <Typography variant="body2" color="text.secondary">
                Plugin does not expose an input schema.
            </Typography>
        );
    }

    const required: string[] = schema.required ?? [];
    const properties: Record<string, any> = schema.properties;
    const defs: Record<string, any> = schema.$defs ?? schema.definitions ?? {};

    const set = (key: string, next: any) => onChange({ ...value, [key]: next });

    const resolve = (prop: any): any => {
        if (prop?.$ref && typeof prop.$ref === 'string') {
            const name = prop.$ref.split('/').pop();
            if (name && defs[name]) return { ...defs[name], ...prop };
        }
        if (Array.isArray(prop?.anyOf)) {
            const nonNull = prop.anyOf.filter((v: any) => v?.type !== 'null');
            if (nonNull.length === 1) {
                const inner = nonNull[0];
                const resolvedInner = inner?.$ref ? resolve(inner) : inner;
                return { ...resolvedInner, ...prop, anyOf: undefined, type: resolvedInner.type };
            }
        }
        return prop;
    };

    type Entry = { key: string; prop: any; order: number };
    const visibleEntries: Entry[] = Object.entries(properties)
        .map(([key, raw]) => {
            const prop = resolve(raw);
            return { key, prop, order: typeof prop.ui_order === 'number' ? prop.ui_order : 1e6 };
        })
        .filter(({ prop }) => !(prop.ui_widget === 'hidden' || prop.ui_hidden === true));

    const hasGroups = visibleEntries.some((e) => typeof e.prop.ui_group === 'string' && e.prop.ui_group);

    if (!hasGroups) {
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {visibleEntries
                    .sort((a, b) => a.order - b.order)
                    .map(({ key, prop }) => renderField(key, prop, value, set, required, disabled))}
            </Box>
        );
    }

    const groupMap = new Map<string, Entry[]>();
    for (const entry of visibleEntries) {
        const group = entry.prop.ui_group || 'General';
        if (!groupMap.has(group)) groupMap.set(group, []);
        groupMap.get(group)!.push(entry);
    }

    const orderedGroups = Array.from(groupMap.entries())
        .map(([name, items]) => ({
            name,
            items: items.sort((a, b) => a.order - b.order),
            minOrder: Math.min(...items.map((i) => i.order)),
        }))
        .sort((a, b) => a.minOrder - b.minOrder);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {orderedGroups.map(({ name, items }) => {
                const defaultOpen = !/advanced/i.test(name);
                return (
                    <Accordion
                        key={name}
                        disableGutters
                        defaultExpanded={defaultOpen}
                        elevation={0}
                        sx={{
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: 1,
                            '&:before': { display: 'none' },
                            overflow: 'hidden',
                        }}
                    >
                        <AccordionSummary
                            expandIcon={<ChevronDown size={16} />}
                            sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 1 } }}
                        >
                            <Typography variant="subtitle2">{name}</Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                {items.length} field{items.length === 1 ? '' : 's'}
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 0 }}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                {items.map(({ key, prop }) =>
                                    renderField(key, prop, value, set, required, disabled),
                                )}
                            </Box>
                        </AccordionDetails>
                    </Accordion>
                );
            })}
        </Box>
    );
};

function renderField(
    key: string,
    prop: any,
    value: Record<string, any>,
    set: (k: string, v: any) => void,
    required: string[],
    disabled?: boolean,
): React.ReactNode {
    const isRequired = required.includes(key);
    const label = prop.title ?? humanize(key);
    const help = prop.ui_help ?? prop.description ?? '';
    const unit = prop.ui_unit ?? prop.units;
    const current = value[key];

    if (Array.isArray(prop.enum)) {
        return (
            <TextField
                key={key}
                select
                label={label}
                required={isRequired}
                helperText={help}
                disabled={disabled}
                value={current ?? prop.default ?? ''}
                onChange={(e) => set(key, e.target.value)}
                size="small"
                fullWidth
            >
                {prop.enum.map((opt: any) => (
                    <MenuItem key={String(opt)} value={opt}>{String(opt)}</MenuItem>
                ))}
            </TextField>
        );
    }

    if (prop.type === 'boolean') {
        return (
            <FormControlLabel
                key={key}
                control={
                    <Checkbox
                        checked={!!(current ?? prop.default ?? false)}
                        onChange={(e) => set(key, e.target.checked)}
                        disabled={disabled}
                    />
                }
                label={
                    <Tooltip title={help} placement="right">
                        <span>{label}{isRequired ? ' *' : ''}</span>
                    </Tooltip>
                }
            />
        );
    }

    if (prop.type === 'number' || prop.type === 'integer') {
        return (
            <TextField
                key={key}
                label={label}
                required={isRequired}
                helperText={help}
                disabled={disabled}
                type="number"
                value={current ?? prop.default ?? ''}
                onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return set(key, undefined);
                    const parsed = prop.type === 'integer' ? parseInt(raw, 10) : parseFloat(raw);
                    set(key, Number.isNaN(parsed) ? raw : parsed);
                }}
                size="small"
                fullWidth
                InputProps={unit ? {
                    endAdornment: <InputAdornment position="end">{unit}</InputAdornment>,
                } : undefined}
                inputProps={{
                    min: prop.minimum,
                    max: prop.maximum,
                    step: prop.ui_step ?? (prop.type === 'integer' ? 1 : 'any'),
                }}
            />
        );
    }

    if (prop.type === 'array') {
        const asText = Array.isArray(current) ? current.join(',') : (current ?? '');
        const itemType = prop.items?.type;
        const isPrimitiveArray =
            itemType === 'string' || itemType === 'number' || itemType === 'integer';
        if (isPrimitiveArray) {
            return (
                <TextField
                    key={key}
                    label={label}
                    required={isRequired}
                    helperText={help || 'Comma-separated values'}
                    disabled={disabled}
                    value={asText}
                    onChange={(e) => {
                        const parts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                        if (itemType === 'string') {
                            set(key, parts);
                        } else {
                            set(key, parts.map((p) => Number(p)).filter((n) => !Number.isNaN(n)));
                        }
                    }}
                    size="small"
                    fullWidth
                />
            );
        }
        return <JsonField key={key} label={label} help={help} value={current} onSet={(v) => set(key, v)} disabled={disabled} required={isRequired} />;
    }

    if (prop.type === 'object' || prop.type === undefined) {
        return <JsonField key={key} label={label} help={help} value={current} onSet={(v) => set(key, v)} disabled={disabled} required={isRequired} />;
    }

    return (
        <TextField
            key={key}
            label={label}
            required={isRequired}
            helperText={help}
            disabled={disabled}
            value={current ?? prop.default ?? ''}
            onChange={(e) => set(key, e.target.value)}
            size="small"
            fullWidth
        />
    );
}

interface JsonFieldProps {
    label: string;
    help?: string;
    value: any;
    onSet: (v: any) => void;
    disabled?: boolean;
    required?: boolean;
}

const JsonField: React.FC<JsonFieldProps> = ({ label, help, value, onSet, disabled, required }) => {
    const [text, setText] = React.useState(() =>
        value === undefined ? '' : JSON.stringify(value, null, 2),
    );
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        const incoming = value === undefined ? '' : JSON.stringify(value, null, 2);
        if (incoming !== text && document.activeElement?.getAttribute('data-json-field') !== label) {
            setText(incoming);
        }
    }, [value, label]);

    return (
        <TextField
            label={label}
            required={required}
            helperText={error ?? help ?? 'JSON value'}
            error={!!error}
            disabled={disabled}
            multiline
            minRows={3}
            value={text}
            onChange={(e) => {
                const next = e.target.value;
                setText(next);
                if (next.trim() === '') {
                    setError(null);
                    onSet(undefined);
                    return;
                }
                try {
                    onSet(JSON.parse(next));
                    setError(null);
                } catch {
                    setError('Invalid JSON');
                }
            }}
            inputProps={{ 'data-json-field': label, style: { fontFamily: 'monospace' } }}
            size="small"
            fullWidth
        />
    );
};

function humanize(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
