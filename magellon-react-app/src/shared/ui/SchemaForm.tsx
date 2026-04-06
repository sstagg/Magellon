/**
 * Dynamic form renderer driven by a Pydantic JSON Schema with ui_* extensions.
 *
 * Reads the schema from  GET /plugins/pp/template-pick/schema/input
 * and renders grouped, ordered form controls automatically.
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
}

interface SchemaFormProps {
    schema: {
        properties?: Record<string, FieldSchema>;
        required?: string[];
        [key: string]: any;
    };
    values: Record<string, any>;
    onChange: (values: Record<string, any>) => void;
    /** Groups to expand by default (all expanded if not specified) */
    defaultExpanded?: string[];
    /** If true, hide groups marked ui_advanced unless user expands them */
    collapseAdvanced?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveType(field: FieldSchema): string {
    if (field.type) return field.type;
    // Handle anyOf (nullable types)
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

// ---------------------------------------------------------------------------
// Field renderers
// ---------------------------------------------------------------------------

const SliderField: React.FC<{
    field: FieldSchema;
    value: any;
    onChange: (v: any) => void;
}> = ({ field, value, onChange }) => {
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
            />
        </Box>
    );
};

const NumberField: React.FC<{
    field: FieldSchema;
    name: string;
    value: any;
    onChange: (v: any) => void;
}> = ({ field, name, value, onChange }) => {
    const unit = field.ui_unit || '';
    return (
        <Tooltip title={field.ui_help || ''} placement="left" arrow disableHoverListener={!field.ui_help}>
            <TextField
                size="small"
                label={`${field.title || name}${unit ? ` (${unit})` : ''}`}
                type="number"
                value={value ?? field.default ?? ''}
                onChange={(e) => {
                    const v = e.target.value;
                    onChange(v === '' ? null : parseFloat(v));
                }}
                placeholder={field.ui_placeholder}
                inputProps={{
                    step: field.ui_step ?? 1,
                    min: getMin(field),
                    max: getMax(field),
                }}
                fullWidth
                helperText={field.description}
            />
        </Tooltip>
    );
};

const SelectField: React.FC<{
    field: FieldSchema;
    name: string;
    value: any;
    onChange: (v: any) => void;
}> = ({ field, name, value, onChange }) => {
    const options = field.enum || field.ui_options || [];
    return (
        <TextField
            size="small"
            label={field.title || name}
            select
            value={value ?? field.default ?? ''}
            onChange={(e) => onChange(e.target.value)}
            fullWidth
            helperText={field.description}
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
}> = ({ field, value, onChange }) => {
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
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                sx={{
                    border: `2px dashed ${isDragOver ? theme.palette.primary.main : alpha(theme.palette.text.secondary, 0.3)}`,
                    borderRadius: 2, p: 1.5, textAlign: 'center',
                    backgroundColor: isDragOver ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                    transition: 'all 0.2s',
                }}
            >
                <CloudUploadIcon sx={{ fontSize: 28, color: isDragOver ? 'primary.main' : 'text.secondary', mb: 0.5 }} />
                <Typography variant="caption" color="text.secondary" display="block">
                    Drop {exts.join(' / ')} files here
                </Typography>
            </Box>
            <TextField
                size="small"
                placeholder={`/path/to/template${exts[0]}`}
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addPath(newPath); setNewPath(''); } }}
                fullWidth
                InputProps={{
                    endAdornment: (
                        <InputAdornment position="end">
                            <IconButton size="small" onClick={() => { addPath(newPath); setNewPath(''); }} disabled={!newPath.trim()}>
                                <AddIcon fontSize="small" />
                            </IconButton>
                        </InputAdornment>
                    ),
                    sx: { fontSize: '0.8rem' },
                }}
            />
            {paths.length > 0 && (
                <List dense sx={{ py: 0 }}>
                    {paths.map((p, i) => (
                        <ListItem key={i} sx={{ px: 1, py: 0.25, borderRadius: 1, '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.04) } }}>
                            <ListItemIcon sx={{ minWidth: 28 }}>
                                <FileIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                            </ListItemIcon>
                            <Tooltip title={p} placement="left">
                                <ListItemText primary={getFileName(p)} primaryTypographyProps={{ variant: 'caption', noWrap: true, fontFamily: 'monospace' }} />
                            </Tooltip>
                            <ListItemSecondaryAction>
                                <IconButton edge="end" size="small" onClick={() => onChange(paths.filter((_, j) => j !== i))}>
                                    <DeleteIcon sx={{ fontSize: 14 }} />
                                </IconButton>
                            </ListItemSecondaryAction>
                        </ListItem>
                    ))}
                </List>
            )}
            {paths.length === 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    {field.description || 'No files added.'}
                </Typography>
            )}
        </Stack>
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
}) => {
    const properties = schema.properties || {};

    // Build grouped, ordered field list
    const groups = useMemo(() => {
        const map = new Map<string, { name: string; fields: { key: string; field: FieldSchema }[]; isAdvanced: boolean }>();

        Object.entries(properties).forEach(([key, field]) => {
            if (field.ui_hidden || field.ui_widget === 'hidden') return;

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
    }, [properties]);

    const handleFieldChange = (key: string, value: any) => {
        onChange({ ...values, [key]: value });
    };

    const isExpanded = (groupName: string, isAdvanced: boolean) => {
        if (defaultExpanded) return defaultExpanded.includes(groupName);
        if (collapseAdvanced && isAdvanced) return false;
        return true;
    };

    const renderField = (key: string, field: FieldSchema) => {
        const widget = field.ui_widget || 'text';
        const val = values[key];

        switch (widget) {
            case 'slider':
                return <SliderField key={key} field={field} value={val} onChange={(v) => handleFieldChange(key, v)} />;

            case 'number':
                return <NumberField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} />;

            case 'toggle':
                return (
                    <FormControlLabel
                        key={key}
                        control={<Switch checked={!!val} onChange={(e) => handleFieldChange(key, e.target.checked)} />}
                        label={field.title || key}
                    />
                );

            case 'select':
                return <SelectField key={key} field={field} name={key} value={val} onChange={(v) => handleFieldChange(key, v)} />;

            case 'file_path':
                return (
                    <TextField
                        key={key}
                        size="small"
                        label={field.title || key}
                        value={val ?? ''}
                        onChange={(e) => handleFieldChange(key, e.target.value)}
                        fullWidth
                        helperText={field.description}
                    />
                );

            case 'file_path_list':
                return <FilePathListField key={key} field={field} value={val || []} onChange={(v) => handleFieldChange(key, v)} />;

            default:
                return (
                    <TextField
                        key={key}
                        size="small"
                        label={field.title || key}
                        value={val ?? field.default ?? ''}
                        onChange={(e) => handleFieldChange(key, e.target.value)}
                        fullWidth
                        helperText={field.description}
                    />
                );
        }
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
