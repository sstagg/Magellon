import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Collapse,
    Divider,
    Grid,
    Stack,
    Typography,
    Alert,
    Chip,
} from '@mui/material';
import { ChevronDown, ChevronRight, Image as ImageIcon, Layers, Play, X as XIcon } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import type {
    JobSubmitRequest,
    PluginSummary} from '../api/PluginApi.ts';
import {
    useCancelJob,
    usePluginInputSchema,
    useSubmitPluginJob
} from '../api/PluginApi.ts';
import { BackendPicker } from './BackendPicker.tsx';
import { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import { ImagePickerDialog } from './ImagePickerDialog.tsx';
import { RunPreviewPane } from './RunPreviewPane.tsx';
import { useJobStore } from '../../../shared/lib/stores/useJobStore.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import { usePreviewState } from '../model/usePreviewState.ts';
import { useTestImagePicker } from '../model/useTestImagePicker.ts';
import { formatSubmitError, parseFieldErrors } from '../model/formErrors.ts';
import { buildDefaults, findImagePathField, findTemplatePathsField } from '../model/schemaFields.ts';
import { pluginTestDefaultsFor } from '../model/pluginPresets.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useAuth } from '../../auth/model/AuthContext.tsx';

interface PluginRunnerProps {
    plugin: PluginSummary;
}

/** Schema-driven single-job runner. Progress comes from Socket.IO. */
export const PluginRunner: React.FC<PluginRunnerProps> = ({ plugin }) => {
    const { sid } = useSocket();
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const { data: schema, isLoading: schemaLoading, error: schemaError } =
        usePluginInputSchema(plugin.plugin_id);
    const submit = useSubmitPluginJob(plugin.plugin_id);
    const cancel = useCancelJob();

    // Plugins that advertise Capability.PREVIEW use the preview /
    // retune endpoint on this page — test images typically don't
    // exist in the DB, so saving to image-metadata or creating job
    // rows isn't useful. Pre-fix this branch hard-coded
    // ``plugin.plugin_id === 'pp/template-picker'``, which silently
    // disabled preview mode after PI-5 (the broker plugin announces
    // as ``particle_picking/Template Picker``). Switch to capability
    // detection so any future plugin that opts into PREVIEW gets
    // the right UX.
    const usePreviewMode = (plugin.capabilities ?? []).includes('preview');

    const defaults = useMemo(() => buildDefaults(schema), [schema]);
    const [values, setValues] = useState<Record<string, unknown>>({});
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [showRequest, setShowRequest] = useState(false);
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // X.1: backend pin within the category. ``null`` = use the
    // category default.
    const [targetBackend, setTargetBackend] = useState<string | null>(null);

    // Tunable keys — fields whose changes can be re-applied via /retune without
    // redoing the expensive FFT. Derived from the plugin's own schema metadata.
    const tunableKeys = useMemo<Set<string>>(() => {
        const out = new Set<string>();
        const props = (schema as { properties?: Record<string, { ui_tunable?: boolean }> })?.properties;
        if (props) {
            for (const [key, raw] of Object.entries(props)) {
                if (raw?.ui_tunable === true) out.add(key);
            }
        }
        return out;
    }, [schema]);

    const imagePathField = useMemo(() => findImagePathField(schema), [schema]);
    const templatePathsField = useMemo(() => findTemplatePathsField(schema), [schema]);

    const {
        imagePickerOpen,
        setImagePickerOpen,
        templatePickerOpen,
        setTemplatePickerOpen,
        pickedPath,
        setPickedPath,
        setLastImageDir,
        setLastTemplateDir,
        imagePickerInitialPath,
        templatePickerInitialPath,
        handlePickImage,
        handlePickTemplates,
    } = useTestImagePicker({
        pluginId: plugin.plugin_id,
        imagePathField,
        templatePathsField,
        setValues,
    });

    // Local preview state for plugins advertising the preview capability,
    // plus the blob preview of the picked test image.
    const preview = usePreviewState({
        usePreviewMode,
        pickedPath,
        values,
        tunableKeys,
        setFieldErrors,
    });

    const requestPreview = useMemo(() => {
        const base = settings.ConfigData.SERVER_API_URL.replace(/\/$/, '');
        if (usePreviewMode) {
            return {
                url: `${base}/particle-picking/preview`,
                body: values,
            };
        }
        const body: JobSubmitRequest = { input: values, name: `${plugin.name} run` };
        if (targetBackend) body.target_backend = targetBackend;
        const url = `${base}/plugins/${plugin.plugin_id}/jobs${sid ? `?sid=${sid}` : ''}`;
        return { url, body };
    }, [plugin.plugin_id, plugin.name, values, sid, usePreviewMode, targetBackend]);

    React.useEffect(() => {
        if (schema && Object.keys(values).length === 0) {
            setValues({ ...defaults, ...pluginTestDefaultsFor(plugin.plugin_id) });
        }
    }, [schema]); // eslint-disable-line react-hooks/exhaustive-deps

    const currentJob = useJobStore((s) =>
        currentJobId ? s.jobs.find((j) => j.job_id === currentJobId) : undefined,
    );

    const handleSubmit = async () => {
        setFieldErrors({});
        try {
            const job = await submit.mutateAsync({
                input: values,
                name: `${plugin.name} run`,
                user_id: user?.id,
                target_backend: targetBackend ?? undefined,
                sid,
            });
            setCurrentJobId(job.job_id);
            useJobStore.getState().upsertJob(job);
            queryClient.invalidateQueries({ queryKey: ['plugin-jobs'] });
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
            const parsed = parseFieldErrors(detail);
            if (Object.keys(parsed).length > 0) setFieldErrors(parsed);
        }
    };

    if (schemaLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (schemaError) {
        return <Alert severity="error">Failed to load input schema for {plugin.plugin_id}</Alert>;
    }

    const templateCount = Array.isArray(values[templatePathsField ?? ''])
        ? (values[templatePathsField as string] as unknown[]).length
        : 0;

    const pickedName = pickedPath ? (pickedPath.split(/[\\/]/).pop() || pickedPath) : null;
    const isRunning = usePreviewMode
        ? preview.previewRunning
        : (submit.isPending || currentJob?.status === 'running' || currentJob?.status === 'queued');

    return (
        <Card variant="outlined" sx={{ overflow: 'visible' }}>
            <CardContent sx={{ pb: 2 }}>
                <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={2}
                    sx={{
                        alignItems: { xs: 'flex-start', sm: 'center' },
                        justifyContent: "space-between",
                        mb: 1
                    }}>
                    <Box sx={{ minWidth: 0 }}>
                        <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                                alignItems: "center",
                                flexWrap: "wrap",
                                rowGap: 0.5
                            }}>
                            <Typography variant="h6" sx={{ lineHeight: 1.2 }}>{plugin.name}</Typography>
                            <Chip size="small" label={`v${plugin.version}`} />
                            <Chip size="small" variant="outlined" label={plugin.category} />
                        </Stack>
                        <Typography
                            variant="body2"
                            sx={{
                                color: "text.secondary",
                                mt: 0.5
                            }}>
                            {plugin.description}
                        </Typography>
                    </Box>
                    <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                            alignItems: "center",
                            flexShrink: 0
                        }}>
                        <Button
                            size="small"
                            variant="text"
                            onClick={() => setShowRequest((v) => !v)}
                            startIcon={showRequest ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            sx={{ color: 'text.secondary' }}
                        >
                            Request
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={isRunning ? <CircularProgress size={14} color="inherit" /> : <Play size={16} />}
                            onClick={usePreviewMode ? preview.handlePreview : handleSubmit}
                            disabled={isRunning}
                        >
                            {usePreviewMode
                                ? (preview.previewRunning ? 'Previewing…' : 'Preview')
                                : (currentJob?.status === 'running' ? 'Running…'
                                    : currentJob?.status === 'queued' ? 'Queued…' : 'Run')}
                        </Button>
                        {!usePreviewMode
                            && currentJobId
                            && (currentJob?.status === 'running' || currentJob?.status === 'queued') && (
                            <Button
                                variant="outlined"
                                color="warning"
                                startIcon={<XIcon size={14} />}
                                onClick={() => cancel.mutate(currentJobId)}
                                disabled={cancel.isPending}
                            >
                                {cancel.isPending ? 'Cancelling…' : 'Cancel'}
                            </Button>
                        )}
                    </Stack>
                </Stack>

                <Divider sx={{ mt: 2, mb: 2 }} />

                <Grid container spacing={3}>
                    <Grid size={{ xs: 12, md: 7 }}>
                        <Typography
                            variant="overline"
                            sx={{
                                color: "text.secondary",
                                letterSpacing: 0.5
                            }}>
                            Inputs
                        </Typography>
                        <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                                alignItems: "center",
                                flexWrap: "wrap",
                                mt: 0.5,
                                mb: 1.5,
                                rowGap: 1
                            }}>
                            {pickedName ? (
                                <Chip
                                    size="small"
                                    icon={<ImageIcon size={14} />}
                                    label={pickedName}
                                    title={pickedPath ?? undefined}
                                    onDelete={() => {
                                        setPickedPath(null);
                                        if (imagePathField) {
                                            setValues((prev) => ({ ...prev, [imagePathField]: undefined }));
                                        }
                                    }}
                                    deleteIcon={<XIcon size={14} />}
                                    onClick={() => setImagePickerOpen(true)}
                                />
                            ) : (
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<ImageIcon size={14} />}
                                    onClick={() => setImagePickerOpen(true)}
                                >
                                    Pick test image…
                                </Button>
                            )}
                            {templatePathsField && (
                                templateCount > 0 ? (
                                    <Chip
                                        size="small"
                                        icon={<Layers size={14} />}
                                        label={`${templateCount} template${templateCount === 1 ? '' : 's'}`}
                                        onDelete={() => setValues((prev) => ({ ...prev, [templatePathsField]: [] }))}
                                        deleteIcon={<XIcon size={14} />}
                                        onClick={() => setTemplatePickerOpen(true)}
                                    />
                                ) : (
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<Layers size={14} />}
                                        onClick={() => setTemplatePickerOpen(true)}
                                    >
                                        Pick templates…
                                    </Button>
                                )
                            )}
                        </Stack>

                        {/*
                         * Backend picker (X.1) — self-hides when the
                         * category has fewer than 2 live backends, so
                         * single-impl categories see no UI noise. Pinning
                         * a backend forces dispatch to that specific
                         * implementation; "Auto" preserves today's
                         * category-default routing.
                         */}
                        {!usePreviewMode && (
                            <BackendPicker
                                category={plugin.category}
                                value={targetBackend}
                                onChange={setTargetBackend}
                                disabled={isRunning}
                            />
                        )}

                        <SchemaForm
                            schema={schema ?? {}}
                            values={values}
                            onChange={(next) => {
                                setValues(next);
                                if (Object.keys(fieldErrors).length > 0) {
                                    const remaining: Record<string, string> = {};
                                    for (const [k, msg] of Object.entries(fieldErrors)) {
                                        if (next[k] === values[k]) remaining[k] = msg;
                                    }
                                    setFieldErrors(remaining);
                                }
                            }}
                            disabled={isRunning}
                            errors={fieldErrors}
                        />

                        <Collapse in={showRequest}>
                            <Box
                                sx={{
                                    mt: 2,
                                    p: 1.5,
                                    borderRadius: 1,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    bgcolor: (t) => t.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    overflowX: 'auto',
                                }}
                            >
                                <Typography
                                    variant="caption"
                                    sx={{
                                        color: "text.secondary",
                                        display: 'block',
                                        mb: 0.5
                                    }}>
                                    POST {requestPreview.url}
                                </Typography>
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                    {JSON.stringify(requestPreview.body, null, 2)}
                                </pre>
                            </Box>
                        </Collapse>
                    </Grid>

                    <Grid size={{ xs: 12, md: 5 }}>
                        <RunPreviewPane
                            pluginId={plugin.plugin_id}
                            usePreviewMode={usePreviewMode}
                            submitError={submit.isError ? formatSubmitError(submit.error) : null}
                            preview={preview}
                            tunableKeys={tunableKeys}
                            currentJob={currentJob}
                            currentJobId={currentJobId}
                            values={values}
                        />
                    </Grid>
                </Grid>
            </CardContent>
            <ImagePickerDialog
                open={imagePickerOpen}
                onClose={() => setImagePickerOpen(false)}
                onPick={handlePickImage}
                onPathChange={setLastImageDir}
                initialPath={imagePickerInitialPath}
                storageKey="imagePicker:lastPath:shared"
            />
            <ImagePickerDialog
                open={templatePickerOpen}
                onClose={() => setTemplatePickerOpen(false)}
                multiple
                onPick={handlePickTemplates}
                onPathChange={setLastTemplateDir}
                title="Pick templates"
                initialPath={templatePickerInitialPath}
                storageKey="imagePicker:lastPath:shared"
            />
        </Card>
    );
};
