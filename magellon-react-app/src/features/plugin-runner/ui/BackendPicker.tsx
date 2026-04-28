import React from 'react';
import {
    Box,
    Chip,
    CircularProgress,
    FormControl,
    MenuItem,
    Select,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import { Server, Star } from 'lucide-react';
import { useCategoryCapabilities, type CapabilitiesBackend } from '../api/PluginApi.ts';

interface BackendPickerProps {
    /** The plugin's category name (matches ``CategoryContract.category.name``). */
    category: string;
    /**
     * Currently pinned backend_id. ``null`` = "use category default" (the
     * dispatcher round-robins or routes to the operator-pinned default).
     */
    value: string | null;
    onChange: (backendId: string | null) => void;
    /** Disabled while a job is mid-flight. */
    disabled?: boolean;
}

/**
 * Pin a TaskMessage to a specific backend within a category (X.1).
 *
 * Backend = "the substitutable second axis under category." Two plugins
 * may serve the same category (e.g. ``ctffind4`` vs ``gctf`` under CTF);
 * leaving this control on its default ("Auto") preserves today's
 * round-robin behaviour, while picking a specific backend pins
 * dispatch to that one.
 *
 * Hidden when the category has fewer than two live backends — the
 * picker would just be a one-option dropdown that adds noise.
 *
 * Reads from ``GET /plugins/capabilities``, the same source the
 * dispatcher uses, so the UI can never offer a backend the dispatcher
 * doesn't see.
 */
export const BackendPicker: React.FC<BackendPickerProps> = ({
    category,
    value,
    onChange,
    disabled = false,
}) => {
    const { data: cat, isLoading, isError } = useCategoryCapabilities(category);

    if (isLoading) {
        return (
            <Stack direction="row" spacing={1} sx={{
                alignItems: "center"
            }}>
                <CircularProgress size={14} />
                <Typography variant="caption" sx={{
                    color: "text.secondary"
                }}>
                    Loading backends…
                </Typography>
            </Stack>
        );
    }

    // No capabilities row OR fewer than 2 live backends → nothing useful
    // to pick. Hide the control so it doesn't add visual noise. The
    // category-default routing still works on the backend.
    if (isError || !cat || cat.backends.length < 2) {
        return null;
    }

    const defaultBackend = cat.backends.find((b) => b.is_default_for_category);
    const selectValue = value ?? '__auto__';

    return (
        <Box sx={{ mb: 2 }}>
            <Stack
                direction="row"
                spacing={1}
                sx={{
                    alignItems: "center",
                    mb: 0.5
                }}>
                <Server size={14} />
                <Typography
                    variant="overline"
                    sx={{
                        color: "text.secondary",
                        letterSpacing: 0.5
                    }}>
                    Backend
                </Typography>
                {defaultBackend && (
                    <Tooltip title={`Operator default for ${cat.name}`}>
                        <Chip
                            size="small"
                            color="success"
                            variant="outlined"
                            icon={<Star size={12} />}
                            label={`default: ${defaultBackend.backend_id}`}
                        />
                    </Tooltip>
                )}
            </Stack>
            <FormControl size="small" fullWidth disabled={disabled}>
                <Select
                    value={selectValue}
                    onChange={(e) => {
                        const v = e.target.value;
                        onChange(v === '__auto__' ? null : String(v));
                    }}
                    renderValue={(v) => (
                        <Typography variant="body2">
                            {v === '__auto__'
                                ? 'Auto (use category default)'
                                : String(v)}
                        </Typography>
                    )}
                >
                    <MenuItem value="__auto__">
                        <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                                alignItems: "center",
                                width: '100%'
                            }}>
                            <Box sx={{ flex: 1 }}>
                                <Typography variant="body2">Auto</Typography>
                                <Typography variant="caption" sx={{
                                    color: "text.secondary"
                                }}>
                                    Use category default {defaultBackend ? `(${defaultBackend.backend_id})` : ''}
                                </Typography>
                            </Box>
                        </Stack>
                    </MenuItem>
                    {cat.backends.map((b) => (
                        <MenuItem key={b.backend_id} value={b.backend_id} disabled={!b.enabled}>
                            <BackendOption backend={b} />
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
            {value && (
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        mt: 0.5,
                        display: 'block'
                    }}>
                    Pinned. Dispatch will fail (503) if backend{' '}
                    <code>{value}</code> isn't live — no silent fallback.
                </Typography>
            )}
        </Box>
    );
};

interface BackendOptionProps {
    backend: CapabilitiesBackend;
}

const BackendOption: React.FC<BackendOptionProps> = ({ backend }) => (
    <Stack
        direction="row"
        spacing={1}
        sx={{
            alignItems: "center",
            width: '100%'
        }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={0.5} sx={{
                alignItems: "center"
            }}>
                <Typography variant="body2">{backend.backend_id}</Typography>
                {backend.is_default_for_category && (
                    <Chip
                        size="small"
                        color="success"
                        variant="outlined"
                        icon={<Star size={10} />}
                        label="default"
                        sx={{ height: 18 }}
                    />
                )}
                {!backend.enabled && (
                    <Chip size="small" color="default" label="disabled" sx={{ height: 18 }} />
                )}
                {backend.live_replicas > 1 && (
                    <Chip
                        size="small"
                        variant="outlined"
                        label={`${backend.live_replicas} replicas`}
                        sx={{ height: 18 }}
                    />
                )}
            </Stack>
            <Typography
                variant="caption"
                sx={{
                    color: "text.secondary",
                    display: 'block'
                }}>
                {backend.name} v{backend.version}
                {backend.capabilities.length > 0 && ` · ${backend.capabilities.join(', ')}`}
            </Typography>
        </Box>
    </Stack>
);
