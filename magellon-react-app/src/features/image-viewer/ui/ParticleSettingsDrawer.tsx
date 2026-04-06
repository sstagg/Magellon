import React, { useEffect, useState, useMemo } from 'react';
import {
    Box,
    Typography,
    Drawer,
    CircularProgress,
    Chip,
    Button,
    Alert,
    AlertTitle,
    Collapse,
    Divider,
    Tooltip,
    alpha,
    useTheme,
} from '@mui/material';
import {
    Visibility as PreviewIcon,
    PlayArrow as RunIcon,
    ErrorOutline as ErrorIcon,
    CheckCircle as ValidIcon,
} from '@mui/icons-material';
import { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import { settings } from '../../../shared/config/settings.ts';

export interface ParticleSettingsDrawerProps {
    open: boolean;
    onClose: () => void;
    pickerParams: Record<string, any>;
    onPickerParamsChange: (params: Record<string, any>) => void;
    onPreview: () => void;
    onRun: () => void;
    isRunning: boolean;
    isPreviewing: boolean;
    /** Name of currently selected image — used for validation */
    imageName: string | null;
}

/** Validate pickerParams against schema requirements. Returns error strings. */
function validateParams(
    schema: any,
    params: Record<string, any>,
    imageName: string | null,
): string[] {
    if (!schema?.properties) return [];
    const errors: string[] = [];
    const required = new Set<string>(schema.required || []);

    // Check image is selected
    if (!imageName) {
        errors.push('No image selected — select a micrograph first.');
    }

    for (const [key, field] of Object.entries<any>(schema.properties)) {
        if (field.ui_hidden) continue;

        const value = params[key];
        const label = field.title || key;

        // Required check
        if (required.has(key)) {
            if (value === undefined || value === null || value === '') {
                const msg = field.ui_required_message || `${label} is required.`;
                errors.push(msg);
                continue;
            }
            // Array required + minItems
            if (Array.isArray(value) && field.minItems && value.length < field.minItems) {
                const msg = field.ui_required_message || `${label} needs at least ${field.minItems} item(s).`;
                errors.push(msg);
                continue;
            }
        }

        // Range checks for numbers
        if (value !== null && value !== undefined && typeof value === 'number') {
            if (field.minimum !== undefined && value < field.minimum) {
                errors.push(`${label} must be at least ${field.minimum}.`);
            }
            if (field.maximum !== undefined && value > field.maximum) {
                errors.push(`${label} must be at most ${field.maximum}.`);
            }
            if (field.exclusiveMinimum !== undefined && value <= field.exclusiveMinimum) {
                errors.push(`${label} must be greater than ${field.exclusiveMinimum}.`);
            }
        }
    }

    return errors;
}

export const ParticleSettingsDrawer: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    onClose,
    pickerParams,
    onPickerParamsChange,
    onPreview,
    onRun,
    isRunning,
    isPreviewing,
    imageName,
}) => {
    const theme = useTheme();
    const [schema, setSchema] = useState<any>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);
    const [showErrors, setShowErrors] = useState(false);

    // Fetch the input schema from the backend once
    useEffect(() => {
        if (!open || schema) return;

        setSchemaLoading(true);
        fetch(`${settings.ConfigData.SERVER_API_URL}/plugins/pp/template-pick/schema/input`)
            .then((res) => {
                if (!res.ok) throw new Error(`${res.status}`);
                return res.json();
            })
            .then((data) => {
                setSchema(data);
                setSchemaError(null);
            })
            .catch((err) => {
                setSchemaError(`Could not load picker settings from server: ${err.message}`);
            })
            .finally(() => setSchemaLoading(false));
    }, [open, schema]);

    // Validate current params against schema
    const validationErrors = useMemo(
        () => (schema ? validateParams(schema, pickerParams, imageName) : []),
        [schema, pickerParams, imageName],
    );

    const isValid = validationErrors.length === 0;
    const isBusy = isRunning || isPreviewing;

    const handlePreview = () => {
        if (!isValid) {
            setShowErrors(true);
            return;
        }
        setShowErrors(false);
        onPreview();
    };

    const handleRun = () => {
        if (!isValid) {
            setShowErrors(true);
            return;
        }
        setShowErrors(false);
        onRun();
    };

    return (
        <Drawer anchor="right" open={open} onClose={onClose}>
            <Box sx={{ width: 360, display: 'flex', flexDirection: 'column', height: '100%' }}>

                {/* ---- Toolbar ---- */}
                <Box sx={{
                    px: 2, py: 1.5,
                    borderBottom: `1px solid ${theme.palette.divider}`,
                    backgroundColor: alpha(theme.palette.primary.main, 0.03),
                }}>
                    {/* Title row */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
                        <Typography variant="subtitle1" fontWeight={600}>
                            Algorithm Settings
                        </Typography>
                        {schema && (
                            <Chip
                                label="template-picker"
                                size="small"
                                variant="outlined"
                                sx={{ fontSize: '0.65rem', height: 22 }}
                            />
                        )}
                    </Box>

                    {/* Action buttons */}
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title={!isValid ? 'Fix validation errors first' : 'Compute correlation maps and preview picks'}>
                            <span style={{ flex: 1 }}>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    fullWidth
                                    startIcon={isPreviewing ? <CircularProgress size={14} /> : <PreviewIcon />}
                                    onClick={handlePreview}
                                    disabled={isBusy}
                                    sx={{ textTransform: 'none' }}
                                >
                                    {isPreviewing ? 'Computing...' : 'Preview'}
                                </Button>
                            </span>
                        </Tooltip>
                        <Tooltip title={!isValid ? 'Fix validation errors first' : 'Run auto-picking and commit particles'}>
                            <span style={{ flex: 1 }}>
                                <Button
                                    variant="contained"
                                    size="small"
                                    fullWidth
                                    startIcon={isRunning ? <CircularProgress size={14} color="inherit" /> : <RunIcon />}
                                    onClick={handleRun}
                                    disabled={isBusy}
                                    sx={{ textTransform: 'none' }}
                                >
                                    {isRunning ? 'Running...' : 'Run'}
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>

                    {/* Validation status */}
                    <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {isValid ? (
                            <>
                                <ValidIcon sx={{ fontSize: 14, color: 'success.main' }} />
                                <Typography variant="caption" color="success.main">Ready</Typography>
                            </>
                        ) : (
                            <>
                                <ErrorIcon sx={{ fontSize: 14, color: 'warning.main' }} />
                                <Typography
                                    variant="caption"
                                    color="warning.main"
                                    sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                                    onClick={() => setShowErrors(!showErrors)}
                                >
                                    {validationErrors.length} issue{validationErrors.length !== 1 ? 's' : ''} — click to {showErrors ? 'hide' : 'show'}
                                </Typography>
                            </>
                        )}
                    </Box>
                </Box>

                {/* ---- Validation errors ---- */}
                <Collapse in={showErrors && validationErrors.length > 0}>
                    <Box sx={{ px: 2, pt: 1 }}>
                        <Alert severity="warning" sx={{ py: 0.5, '& .MuiAlert-message': { fontSize: '0.75rem' } }}>
                            <AlertTitle sx={{ fontSize: '0.8rem', mb: 0.5 }}>Fix before running</AlertTitle>
                            {validationErrors.map((err, i) => (
                                <Typography key={i} variant="caption" display="block" sx={{ lineHeight: 1.6 }}>
                                    • {err}
                                </Typography>
                            ))}
                        </Alert>
                    </Box>
                </Collapse>

                {/* ---- Schema-driven form ---- */}
                <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5 }}>
                    {schemaLoading && (
                        <Box sx={{ textAlign: 'center', py: 6 }}>
                            <CircularProgress size={28} />
                            <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1.5 }}>
                                Loading settings from backend...
                            </Typography>
                        </Box>
                    )}

                    {schemaError && (
                        <Box sx={{
                            p: 2, borderRadius: 1, mb: 2,
                            backgroundColor: alpha(theme.palette.error.main, 0.08),
                        }}>
                            <Typography variant="caption" color="error">
                                {schemaError}
                            </Typography>
                            <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                                Make sure the backend is running on {settings.ConfigData.SERVER_API_URL}
                            </Typography>
                        </Box>
                    )}

                    {schema && (
                        <SchemaForm
                            schema={schema}
                            values={pickerParams}
                            onChange={onPickerParamsChange}
                            defaultExpanded={['Templates', 'Auto-picking Settings']}
                            collapseAdvanced
                        />
                    )}
                </Box>
            </Box>
        </Drawer>
    );
};
