/**
 * Dynamic form renderer driven by a Pydantic JSON Schema.
 *
 * Two rendering paths share the same component:
 *
 *   1. **Widget-driven** — fields annotated with ``ui_widget`` use the
 *      explicit MUI widget set (slider / number / toggle / select /
 *      file_path / file_path_list / hidden). Particle picking + most
 *      Magellon-side schemas use this path.
 *
 *   2. **Type-driven fallback** — when ``ui_widget`` is absent, the
 *      renderer infers controls from JSON-Schema ``type`` (boolean →
 *      Checkbox, integer/number → numeric TextField, array of
 *      primitives → comma-separated TextField, array/object → JSON
 *      editor, enum → Select). This means a stock Pydantic
 *      ``model_json_schema()`` from any plugin renders without
 *      schema authors having to add ``ui_*`` decorations first.
 *
 * Pydantic-specific shapes handled transparently:
 *   - ``$ref`` / ``$defs`` / ``definitions`` for nested model refs
 *   - ``anyOf`` with a single non-null branch (Pydantic's ``Optional[T]``)
 *
 * Supported ui_widget values:
 *   slider, number, text, toggle, select,
 *   file_path, file_path_list, hidden
 */

import React, { useState, useCallback, useMemo } from 'react';
import {
    Box,
    Typography,
    Slider,
    TextField,
    FormControlLabel,
    Switch,
    Checkbox,
    Select,
    MenuItem,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Stack,
    Chip,
    IconButton,
    Tooltip,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    ListItemSecondaryAction,
    InputAdornment,
    alpha,
    useTheme,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
    Add as AddIcon,
    Delete as DeleteIcon,
    CloudUpload as CloudUploadIcon,
    InsertDriveFile as FileIcon,
    FolderOpen as FolderOpenIcon,
} from '@mui/icons-material';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FieldSchema {
    title?: string;
    description?: string;
    type?: string;
    default?: any;
    minimum?: number;
    maximum?: number;
    exclusiveMinimum?: number;
    exclusiveMaximum?: number;
    enum?: any[];
    items?: any;
    anyOf?: any[];
    $ref?: string;
    units?: string;
    // UI extensions — rendering
    ui_widget?: string;
    ui_group?: string;
    ui_order?: number;
    ui_marks?: { value: number; label: string }[];
    ui_step?: number;
    ui_unit?: string;
    ui_advanced?: boolean;
    ui_placeholder?: string;
    ui_help?: string;
    ui_depends_on?: Record<string, any>;
    ui_required_message?: string;
    ui_hidden?: boolean;
    ui_file_ext?: string[];
    ui_options?: any[];
    ui_tunable?: boolean;
}

/** Callback signature for the GPFS file picker bridge. */
export interface BrowseFileRequest {
    /** Schema property key (e.g. ``image_path``). */
    fieldKey: string;
    /** Field title from the schema, for the dialog header. */
    fieldTitle: string;
    /** Current value, if any. Useful for seeding the picker's path. */
    current: string | string[] | null;
    /** ``true`` when the field is an array of paths (file_path_list). */
    multiple: boolean;
    /** Optional allowed extensions, e.g. ``['.mrc', '.tif']``. */
    allowedExts?: string[];
    /** Caller invokes this with the picked path(s) to update the form. */
    onPick: (picked: string | string[]) => void;
}

interface SchemaFormProps {
    schema: {
        properties?: Record<string, FieldSchema>;
        required?: string[];
        $defs?: Record<string, any>;
        definitions?: Record<string, any>;
        [key: string]: any;
    };
    values: Record<string, any>;
    onChange: (values: Record<string, any>) => void;
    /** Groups to expand by default (all expanded if not specified) */
    defaultExpanded?: string[];
    /** If true, hide groups marked ui_advanced unless user expands them */
    collapseAdvanced?: boolean;
    /** If set, only show fields where ui_tunable matches this value */
    tunableOnly?: boolean;
    /** Disable every field in the form */
    disabled?: boolean;
    /** Per-field validation errors keyed by property name */
    errors?: Record<string, string>;
    /**
     * Bridge to a GPFS file picker. When provided, file-path fields
     * render a "Browse" button that calls this; the consumer pops a
     * dialog and invokes ``onPick(...)`` with the chosen path(s).
     *
     * Without this prop, file-path fields are still editable as text —
     * the picker is purely additive.
     */
    onBrowseFile?: (request: BrowseFileRequest) => void;
}

// Heuristic: when ui_widget is unset, these are common patterns for
// "input file" fields across Magellon plugins. Output paths (e.g.
// ``output_path``, ``target_path``) are intentionally excluded —
// authors should mark those with ``ui_widget: 'output'`` or similar
// once a need arises. Until then the user types/edits them as plain text.
const FILE_PATH_FIELD_NAMES = new Set([
    'image_path', 'image_paths',
    'template_path', 'template_paths',
    'input_path', 'input_paths',
    'source_path', 'source_paths',
    'frame_path', 'frame_paths',
    'gain_path', 'defects_path',
    'mrcs_path', 'star_path',
]);

function looksLikeFilePathField(key: string, field: FieldSchema): 'single' | 'list' | null {
    if (!FILE_PATH_FIELD_NAMES.has(key)) return null;
    if (key.endsWith('_paths')) return 'list';
    if (field.type === 'array' && field.items?.type === 'string') return 'list';
    return 'single';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveType(field: FieldSchema): string {
    if (field.type) return field.type;
    if (field.anyOf) {
        const nonNull = field.anyOf.find((t: any) => t.type !== 'null');
        return nonNull?.type || 'string';
    }
    return 'string';
}

function getMin(field: FieldSchema): number | undefined {
    if (field.minimum !== undefined) return field.minimum;
    if (field.exclusiveMinimum !== undefined) return field.exclusiveMinimum;
    return undefined;
}

function getMax(field: FieldSchema): number | undefined {
    if (field.maximum !== undefined) return field.maximum;
    if (field.exclusiveMaximum !== undefined) return field.exclusiveMaximum;
    return undefined;
}

function getFileName(path: string): string {
    return path.replace(/\\/g, '/').split('/').pop() || path;
}

function humanize(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Resolve ``$ref`` and collapse ``Optional[T]``/``Union[T, None]``.
 *
 * Pydantic's ``model_json_schema()`` emits nested models as
 * ``{"$ref": "#/$defs/Foo"}`` and nullable fields as
 * ``{"anyOf": [{"$ref": ...}, {"type": "null"}]}``. We dereference
 * both so downstream renderers see a flat field shape with a usable
 * ``type``.
 */
function resolveField(field: FieldSchema, defs: Record<string, any>): FieldSchema {
    if (field?.$ref && typeof field.$ref === 'string') {
        const name = field.$ref.split('/').pop();
        if (name && defs[name]) {
            return resolveField({ ...defs[name], ...field, $ref: undefined }, defs);
        }
    }
    if (Array.isArray(field?.anyOf)) {
        const nonNull = field.anyOf.filter((v: any) => v?.type !== 'null');
        if (nonNull.length === 1) {
            const inner = resolveField(nonNull[0], defs);
            return { ...inner, ...field, anyOf: undefined, type: inner.type ?? field.type };
        }
    }
    return field;
}

// ---------------------------------------------------------------------------
// Field renderers (widget-driven)
// ---------------------------------------------------------------------------

const SliderField: React.FC<{
    field: FieldSchema;
    value: any;
    onChange: (v: any) => void;
    disabled?: boolean;
}> = ({ field, value, onChange, disabled }) => {
    const min = getMin(field) ?? 0;
    const max = getMax(field) ?? 1;
    const step = field.ui_step ?? (max - min) / 20;
    const label = field.title || '';
    const unit = field.ui_unit ? ` (${field.ui_unit})` : '';

    return (
        <Box>
            <Tooltip title={field.ui_help || ''} placement="left" arrow disableHoverListener={!field.ui_help}>
                <Typography variant="body2" gutterBottom>
                    {label}{unit}
                </Typography>
            </Tooltip>
            <Slider
                value={value ?? field.default ?? min}
                onChange={(_, v) => onChange(v as number)}
                min={min}
                max={max}
                step={step}
                valueLabelDisplay="auto"
                marks={field.ui_marks}
                disabled={disabled}
            />
        </Box>
    );
};

const NumberField: React.FC<{
    field: FieldSchema;
    name: string;
    value: any;
    onChange: (v: any) => void;
    disabled?: boolean;
    error?: string;
    required?: boolean;
}> = ({ field, name, value, onChange, disabled, error, required }) => {
    const unit = field.ui_unit || field.units || '';
    const help = error || field.description || field.ui_help;
    const isInt = field.type === 'integer';
    return (
        <Tooltip title={field.ui_help || ''} placement="left" arrow disableHoverListener={!field.ui_help}>
            <TextField
                size="small"
                label={`${field.title || humanize(name)}${unit ? ` (${unit})` : ''}`}
                type="number"
                value={value ?? field.default ?? ''}
                onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return onChange(null);
                    const parsed = isInt ? parseInt(raw, 10) : parseFloat(raw);
                    onChange(Number.isNaN(parsed) ? raw : parsed);
                }}
                placeholder={field.ui_placeholder}
                fullWidth
                helperText={help}
                error={!!error}
                disabled={disabled}
                required={required}
                slotProps={{
                    htmlInput: {
                        step: field.ui_step ?? (isInt ? 1 : 'any'),
                        min: getMin(field),
                        max: getMax(field),
                    },
                }}
            />
        </Tooltip>
    );
};

const SelectField: React.FC<{
    field: FieldSchema;
    name: string;
    value: any;
    onChange: (v: any) => void;
    disabled?: boolean;
    error?: string;
    required?: boolean;
}> = ({ field, name, value, onChange, disabled, error, required }) => {
    const options = field.enum || field.ui_options || [];
    return (
        <TextField
            size="small"
            label={field.title || humanize(name)}
            select
            value={value ?? field.default ?? ''}
            onChange={(e) => onChange(e.target.value)}
            fullWidth
            helperText={error || field.description}
            error={!!error}
            disabled={disabled}
            required={required}
        >
            {options.map((opt: any) => (
                <MenuItem key={String(opt)} value={opt}>
                    {String(opt)}
                </MenuItem>
            ))}
        </TextField>
    );
};

const FilePathListField: React.FC<{
    field: FieldSchema;
    value: string[];
    onChange: (v: string[]) => void;
    disabled?: boolean;
    /** Optional GPFS-browse trigger rendered next to the manual-add box. */
    browseButton?: React.ReactNode;
}> = ({ field, value, onChange, disabled, browseButton }) => {
    const theme = useTheme();
    const [newPath, setNewPath] = useState('');
    const [isDragOver, setIsDragOver] = useState(false);
    const paths = value || [];
    const exts = field.ui_file_ext || ['.mrc'];

    const addPath = useCallback((p: string) => {
        const trimmed = p.trim();
        if (trimmed && !paths.includes(trimmed)) {
            onChange([...paths, trimmed]);
        }
    }, [paths, onChange]);

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        if (disabled) return;
        const files = e.dataTransfer.files;
        const newPaths: string[] = [];
        for (let i = 0; i < files.length; i++) {
            const name = files[i].name;
            if (exts.some(ext => name.endsWith(ext))) {
                newPaths.push(name);
            }
        }
        if (newPaths.length) onChange([...paths, ...newPaths.filter(p => !paths.includes(p))]);
        const text = e.dataTransfer.getData('text/plain');
        if (text) text.split('\n').forEach(l => addPath(l));
    };

    return (
        <Stack spacing={1.5}>
            <Box
                onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                sx={{
                    border: `2px dashed ${isDragOver ? theme.palette.primary.main : alpha(theme.palette.text.secondary, 0.3)}`,
                    borderRadius: 2, p: 1.5, textAlign: 'center',
                    backgroundColor: isDragOver ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                    transition: 'all 0.2s',
                    opacity: disabled ? 0.5 : 1,
                }}
            >
                <CloudUploadIcon sx={{ fontSize: 28, color: isDragOver ? 'primary.main' : 'text.secondary', mb: 0.5 }} />
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        display: "block"
                    }}>
                    Drop {exts.join(' / ')} files here
                </Typography>
            </Box>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <TextField
                    size="small"
                    placeholder={`/path/to/template${exts[0]}`}
                    value={newPath}
                    onChange={(e) => setNewPath(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addPath(newPath); setNewPath(''); } }}
                    fullWidth
                    disabled={disabled}
                    slotProps={{
                        input: {
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton size="small" onClick={() => { addPath(newPath); setNewPath(''); }} disabled={disabled || !newPath.trim()}>
                                        <AddIcon fontSize="small" />
                                    </IconButton>
                                </InputAdornment>
                            ),
                            sx: { fontSize: '0.8rem' },
                        }
                    }}
                />
                {browseButton}
            </Stack>
            {paths.length > 0 && (
                <List dense sx={{ py: 0 }}>
                    {paths.map((p, i) => (
                        <ListItem key={i} sx={{ px: 1, py: 0.25, borderRadius: 1, '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.04) } }}>
                            <ListItemIcon sx={{ minWidth: 28 }}>
                                <FileIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                            </ListItemIcon>
                            <Tooltip title={p} placement="left">
                                <ListItemText primary={getFileName(p)} slotProps={{
                                    primary: { variant: 'caption', noWrap: true, sx: { fontFamily: 'monospace' } }
                                }} />
                            </Tooltip>
                            <ListItemSecondaryAction>
                                <IconButton edge="end" size="small" onClick={() => onChange(paths.filter((_, j) => j !== i))} disabled={disabled}>
                                    <DeleteIcon sx={{ fontSize: 14 }} />
                                </IconButton>
                            </ListItemSecondaryAction>
                        </ListItem>
                    ))}
                </List>
            )}
            {paths.length === 0 && (
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        fontStyle: 'italic'
                    }}>
                    {field.description || 'No files added.'}
                </Typography>
            )}
        </Stack>
    );
};

// ---------------------------------------------------------------------------
// JSON fallback for object / mixed-array values
// ---------------------------------------------------------------------------

const JsonField: React.FC<{
    label: string;
    help?: string;
    value: any;
    onChange: (v: any) => void;
    disabled?: boolean;
    required?: boolean;
    error?: string;
}> = ({ label, help, value, onChange, disabled, required, error: externalError }) => {
    const [text, setText] = useState(() =>
        value === undefined ? '' : JSON.stringify(value, null, 2),
    );
    const [parseError, setParseError] = useState<string | null>(null);
    const error = parseError ?? externalError ?? null;

    React.useEffect(() => {
        const incoming = value === undefined ? '' : JSON.stringify(value, null, 2);
        if (incoming !== text && document.activeElement?.getAttribute('data-json-field') !== label) {
            setText(incoming);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
                    setParseError(null);
                    onChange(undefined);
                    return;
                }
                try {
                    onChange(JSON.parse(next));
                    setParseError(null);
                } catch {
                    setParseError('Invalid JSON');
                }
            }}
            size="small"
            fullWidth
            slotProps={{
                htmlInput: { 'data-json-field': label, style: { fontFamily: 'monospace' } } as any,
            }}
        />
    );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const SchemaForm: React.FC<SchemaFormProps> = ({
    schema,
    values,
    onChange,
    defaultExpanded,
    collapseAdvanced = true,
    tunableOnly,
    disabled,
    errors,
    onBrowseFile,
}) => {
    if (!schema?.properties) {
        return (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Plugin does not expose an input schema.
            </Typography>
        );
    }

    const properties = schema.properties || {};
    const defs = schema.$defs ?? schema.definitions ?? {};
    const required: string[] = schema.required ?? [];

    // Build grouped, ordered field list. $ref / anyOf are resolved
    // up-front so the rest of the renderer treats every field as a
    // flat shape with usable ``type``.
    const groups = useMemo(() => {
        const map = new Map<string, { name: string; fields: { key: string; field: FieldSchema }[]; isAdvanced: boolean }>();

        Object.entries(properties).forEach(([key, raw]) => {
            const field = resolveField(raw as FieldSchema, defs);
            if (field.ui_hidden || field.ui_widget === 'hidden') return;
            if (tunableOnly !== undefined && !!field.ui_tunable !== tunableOnly) return;

            const groupName = field.ui_group || 'General';
            if (!map.has(groupName)) {
                map.set(groupName, { name: groupName, fields: [], isAdvanced: false });
            }
            map.get(groupName)!.fields.push({ key, field });
            if (field.ui_advanced) map.get(groupName)!.isAdvanced = true;
        });

        // Sort fields within each group
        map.forEach((group) => {
            group.fields.sort((a, b) => (a.field.ui_order ?? 99) - (b.field.ui_order ?? 99));
        });

        return Array.from(map.values());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [properties, tunableOnly]);

    const handleFieldChange = (key: string, value: any) => {
        onChange({ ...values, [key]: value });
    };

    const isExpanded = (groupName: string, isAdvanced: boolean) => {
        if (defaultExpanded) return defaultExpanded.includes(groupName);
        if (collapseAdvanced && isAdvanced) return false;
        return true;
    };

    const browseButton = (
        kind: 'single' | 'list',
        key: string,
        field: FieldSchema,
        currentValue: any,
    ) => {
        if (!onBrowseFile) return null;
        const handleClick = () => {
            onBrowseFile({
                fieldKey: key,
                fieldTitle: field.title || humanize(key),
                current: currentValue ?? null,
                multiple: kind === 'list',
                allowedExts: field.ui_file_ext,
                onPick: (picked) => handleFieldChange(key, picked),
            });
        };
        return (
            <Tooltip title={`Browse GPFS for ${field.title || humanize(key)}`} placement="top">
                <span>
                    <IconButton
                        size="small"
                        onClick={handleClick}
                        disabled={disabled}
                        aria-label={`browse ${key}`}
                    >
                        <FolderOpenIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </span>
            </Tooltip>
        );
    };

    const renderField = (key: string, field: FieldSchema) => {
        let widget = field.ui_widget;
        const val = values[key];
        const fieldError = errors?.[key];
        const isRequired = required.includes(key);

        // Heuristic: when the schema doesn't declare ui_widget AND the
        // field name matches a well-known input-path pattern (image_path,
        // template_paths, etc.), treat it as a file_path / file_path_list
        // so the GPFS picker shows up. Output paths aren't whitelisted —
        // see FILE_PATH_FIELD_NAMES.
        if (!widget) {
            const guess = looksLikeFilePathField(key, field);
            if (guess === 'single') widget = 'file_path';
            else if (guess === 'list') widget = 'file_path_list';
        }

        // Widget-driven path
        if (widget) {
            switch (widget) {
                case 'slider':
                    return <SliderField key={key} field={field} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} />;
                case 'number':
                    return <NumberField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} error={fieldError} required={isRequired} />;
                case 'toggle':
                    return (
                        <FormControlLabel
                            key={key}
                            control={<Switch checked={!!val} onChange={(e) => handleFieldChange(key, e.target.checked)} disabled={disabled} />}
                            label={field.title || humanize(key)}
                        />
                    );
                case 'select':
                    return <SelectField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} error={fieldError} required={isRequired} />;
                case 'file_path':
                    return (
                        <TextField
                            key={key}
                            size="small"
                            label={field.title || humanize(key)}
                            value={val ?? ''}
                            onChange={(e) => handleFieldChange(key, e.target.value)}
                            fullWidth
                            helperText={fieldError || field.description}
                            error={!!fieldError}
                            disabled={disabled}
                            required={isRequired}
                            slotProps={{
                                input: onBrowseFile
                                    ? {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                {browseButton('single', key, field, val)}
                                            </InputAdornment>
                                        ),
                                    }
                                    : undefined,
                            }}
                        />
                    );
                case 'file_path_list':
                    return (
                        <FilePathListField
                            key={key}
                            field={field}
                            value={val || []}
                            onChange={(v) => handleFieldChange(key, v)}
                            disabled={disabled}
                            browseButton={browseButton('list', key, field, val)}
                        />
                    );
            }
        }

        // Type-driven fallback — for bare Pydantic schemas without
        // ui_* decorations. Mirrors the old plugin-runner SchemaForm.
        const label = field.title || humanize(key);
        const help = fieldError || field.description || field.ui_help;
        const type = resolveType(field);

        if (Array.isArray(field.enum)) {
            return <SelectField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} error={fieldError} required={isRequired} />;
        }

        if (type === 'boolean') {
            return (
                <Box key={key}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={!!(val ?? field.default ?? false)}
                                onChange={(e) => handleFieldChange(key, e.target.checked)}
                                disabled={disabled}
                            />
                        }
                        label={
                            <Tooltip title={field.ui_help || field.description || ''} placement="right">
                                <span>{label}{isRequired ? ' *' : ''}</span>
                            </Tooltip>
                        }
                    />
                    {fieldError && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', ml: 4, mt: -0.5 }}>
                            {fieldError}
                        </Typography>
                    )}
                </Box>
            );
        }

        if (type === 'number' || type === 'integer') {
            return <NumberField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} error={fieldError} required={isRequired} />;
        }

        if (type === 'array') {
            const itemType = field.items?.type;
            const isPrimitiveArray = itemType === 'string' || itemType === 'number' || itemType === 'integer';
            if (isPrimitiveArray) {
                const asText = Array.isArray(val) ? val.join(',') : (val ?? '');
                return (
                    <TextField
                        key={key}
                        label={label}
                        required={isRequired}
                        helperText={fieldError || help || 'Comma-separated values'}
                        error={!!fieldError}
                        disabled={disabled}
                        value={asText}
                        onChange={(e) => {
                            const parts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                            if (itemType === 'string') {
                                handleFieldChange(key, parts);
                            } else {
                                handleFieldChange(key, parts.map((p) => Number(p)).filter((n) => !Number.isNaN(n)));
                            }
                        }}
                        size="small"
                        fullWidth
                    />
                );
            }
            return <JsonField key={key} label={label} help={help} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} required={isRequired} error={fieldError} />;
        }

        if (type === 'object') {
            return <JsonField key={key} label={label} help={help} value={val} onChange={(v) => handleFieldChange(key, v)} disabled={disabled} required={isRequired} error={fieldError} />;
        }

        // Default: text
        return (
            <TextField
                key={key}
                size="small"
                label={label}
                value={val ?? field.default ?? ''}
                onChange={(e) => handleFieldChange(key, e.target.value)}
                fullWidth
                helperText={help}
                error={!!fieldError}
                disabled={disabled}
                required={isRequired}
            />
        );
    };

    return (
        <Box>
            {groups.map((group) => (
                <Accordion key={group.name} defaultExpanded={isExpanded(group.name, group.isAdvanced)}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>{group.name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Stack spacing={2.5}>
                            {group.fields
                                .filter(({ field }) => {
                                    // ui_depends_on: only show when condition met
                                    if (!field.ui_depends_on) return true;
                                    return Object.entries(field.ui_depends_on).every(
                                        ([depKey, depVal]) => values[depKey] === depVal
                                    );
                                })
                                .map(({ key, field }) => renderField(key, field))}
                        </Stack>
                    </AccordionDetails>
                </Accordion>
            ))}
        </Box>
    );
};
