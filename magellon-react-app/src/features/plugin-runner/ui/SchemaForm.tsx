import React from 'react';
import {
    Box,
    TextField,
    FormControlLabel,
    Checkbox,
    MenuItem,
    Typography,
    Tooltip,
    InputAdornment,
} from '@mui/material';
import type { JsonSchema } from '../api/PluginApi.ts';

export interface SchemaFormProps {
    schema: JsonSchema;
    value: Record<string, any>;
    onChange: (next: Record<string, any>) => void;
    disabled?: boolean;
}

/**
 * Renders a flat Pydantic-derived JSON schema as MUI form fields.
 *
 * Covers the common cases: string, number/integer, boolean, enum, and simple
 * arrays of primitives (entered as comma-separated). Nested objects and
 * complex $ref chains are rendered as raw JSON textareas — good enough for
 * plugins with simple inputs, and degrades gracefully for the rest.
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
        return prop;
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {Object.entries(properties).map(([key, rawProp]) => {
                const prop = resolve(rawProp);
                const isRequired = required.includes(key);
                const label = prop.title ?? humanize(key);
                const help = prop.description ?? '';
                const current = value[key];

                // Enum → Select
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

                // Boolean → Checkbox
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

                // Number / integer → numeric TextField
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
                            InputProps={prop.units ? {
                                endAdornment: <InputAdornment position="end">{prop.units}</InputAdornment>,
                            } : undefined}
                            inputProps={{
                                min: prop.minimum,
                                max: prop.maximum,
                                step: prop.type === 'integer' ? 1 : 'any',
                            }}
                        />
                    );
                }

                // Array of primitives → comma-separated input
                if (prop.type === 'array') {
                    const asText = Array.isArray(current)
                        ? current.join(',')
                        : (current ?? '');
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
                    // Complex array → JSON textarea
                    return <JsonField key={key} label={label} help={help} value={current} onSet={(v) => set(key, v)} disabled={disabled} required={isRequired} />;
                }

                // Object / unknown → JSON textarea
                if (prop.type === 'object' || prop.type === undefined) {
                    return <JsonField key={key} label={label} help={help} value={current} onSet={(v) => set(key, v)} disabled={disabled} required={isRequired} />;
                }

                // Default: string TextField
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
            })}
        </Box>
    );
};

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
        value === undefined ? '' : JSON.stringify(value, null, 2)
    );
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        // Keep text in sync if parent resets the value.
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
                } catch (err: any) {
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
