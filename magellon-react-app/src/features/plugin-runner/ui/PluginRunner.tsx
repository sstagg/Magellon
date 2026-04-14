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
    LinearProgress,
    Stack,
    Typography,
    Alert,
    Chip,
} from '@mui/material';
import { ChevronDown, ChevronRight, Image as ImageIcon, Layers, Play } from 'lucide-react';
import { useQueryClient } from 'react-query';
import {
    JobSubmitRequest,
    usePluginInputSchema,
    useSubmitPluginJob,
    PluginSummary,
} from '../api/PluginApi.ts';
import { SchemaForm } from './SchemaForm.tsx';
import { ResultRenderer } from './results/ResultRenderers.tsx';
import { ImagePickerDialog } from './ImagePickerDialog.tsx';
import { useJobStore } from '../../../app/layouts/PanelLayout/useJobStore.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';
import { settings } from '../../../shared/config/settings.ts';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { useAuth } from '../../auth/model/AuthContext.tsx';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

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

    const defaults = useMemo(() => buildDefaults(schema), [schema]);
    const [values, setValues] = useState<Record<string, any>>({});
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [showRequest, setShowRequest] = useState(false);
    const [imagePickerOpen, setImagePickerOpen] = useState(false);
    const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
    const [pickedPath, setPickedPath] = useState<string | null>(null);
    const [lastImageDir, setLastImageDir] = useState<string | null>(null);
    const [lastTemplateDir, setLastTemplateDir] = useState<string | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);

    const imagePathField = useMemo(() => findImagePathField(schema), [schema]);
    const templatePathsField = useMemo(() => findTemplatePathsField(schema), [schema]);

    React.useEffect(() => {
        if (!pickedPath) {
            setPreviewUrl(null);
            setPreviewError(null);
            return;
        }
        let revoked = false;
        let objectUrl: string | null = null;
        setPreviewError(null);
        api
            .get('/web/files/preview', { params: { path: pickedPath }, responseType: 'blob' })
            .then((res) => {
                if (revoked) return;
                objectUrl = URL.createObjectURL(res.data);
                setPreviewUrl(objectUrl);
            })
            .catch((err) => {
                if (revoked) return;
                setPreviewError(err.response?.data?.detail || err.message || 'Preview failed');
            });
        return () => {
            revoked = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [pickedPath]);

    const handlePickImage = (path: string) => {
        setPickedPath(path);
        setValues((prev) => {
            const next = { ...prev };
            if (imagePathField) next[imagePathField] = path;
            const apix = imagePixelSizeFor(plugin.plugin_id, path);
            if (apix != null) next['image_pixel_size'] = apix;
            return next;
        });
    };

    const handlePickTemplates = (paths: string[]) => {
        if (!templatePathsField) return;
        setValues((prev) => {
            const existing = Array.isArray(prev[templatePathsField]) ? prev[templatePathsField] : [];
            const merged = Array.from(new Set([...existing, ...paths]));
            const next: Record<string, any> = { ...prev, [templatePathsField]: merged };
            const apix = templatePixelSizeFor(plugin.plugin_id, paths);
            if (apix != null) next['template_pixel_size'] = apix;
            return next;
        });
    };

    const requestPreview = useMemo(() => {
        const body: JobSubmitRequest = { input: values, name: `${plugin.name} run` };
        const base = settings.ConfigData.SERVER_API_URL.replace(/\/$/, '');
        const url = `${base}/plugins/${plugin.plugin_id}/jobs${sid ? `?sid=${sid}` : ''}`;
        return { url, body };
    }, [plugin.plugin_id, plugin.name, values, sid]);

    React.useEffect(() => {
        if (schema && Object.keys(values).length === 0) {
            setValues({ ...defaults, ...pluginTestDefaultsFor(plugin.plugin_id) });
        }
    }, [schema]); // eslint-disable-line react-hooks/exhaustive-deps

    const currentJob = useJobStore((s) =>
        currentJobId ? s.jobs.find((j) => j.job_id === currentJobId) : undefined,
    );

    const handleSubmit = async () => {
        try {
            const job = await submit.mutateAsync({
                input: values,
                name: `${plugin.name} run`,
                user_id: user?.id,
                sid,
            });
            setCurrentJobId(job.job_id);
            useJobStore.getState().upsertJob(job);
            queryClient.invalidateQueries(['plugin-jobs']);
        } catch (err) {
            // mutation state carries the error
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
        ? values[templatePathsField as string].length
        : 0;

    return (
        <Card variant="outlined">
            <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="h6">{plugin.name}</Typography>
                    <Chip size="small" label={`v${plugin.version}`} />
                    <Chip size="small" variant="outlined" label={plugin.category} />
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {plugin.description}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Grid container spacing={3}>
                    <Grid size={{ xs: 12, md: 7 }}>
                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1, rowGap: 1 }}>
                            <Typography variant="subtitle2" sx={{ flex: 1, minWidth: 80 }}>Input</Typography>
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<ImageIcon size={14} />}
                                onClick={() => setImagePickerOpen(true)}
                            >
                                Pick test image…
                            </Button>
                            {templatePathsField && (
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<Layers size={14} />}
                                    onClick={() => setTemplatePickerOpen(true)}
                                >
                                    Pick templates…
                                </Button>
                            )}
                        </Stack>
                        {pickedPath && (
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block', mb: 0.5, wordBreak: 'break-all' }}
                            >
                                Test image: {pickedPath}
                                {imagePathField && ` → "${imagePathField}"`}
                            </Typography>
                        )}
                        {templatePathsField && templateCount > 0 && (
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block', mb: 1 }}
                            >
                                {templateCount} template(s) → "{templatePathsField}"
                            </Typography>
                        )}
                        <SchemaForm
                            schema={schema}
                            value={values}
                            onChange={setValues}
                            disabled={submit.isLoading || currentJob?.status === 'running'}
                        />

                        <Collapse in={showRequest}>
                            <Box
                                sx={{
                                    mt: 2,
                                    p: 1.5,
                                    borderRadius: 1,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    bgcolor: 'action.hover',
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    overflowX: 'auto',
                                }}
                            >
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                    POST {requestPreview.url}
                                </Typography>
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                    {JSON.stringify(requestPreview.body, null, 2)}
                                </pre>
                            </Box>
                        </Collapse>
                    </Grid>

                    <Grid size={{ xs: 12, md: 5 }}>
                        <Box sx={{ position: { md: 'sticky' }, top: { md: 16 } }}>
                            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2, rowGap: 1 }}>
                                <Button
                                    variant="contained"
                                    startIcon={<Play size={16} />}
                                    onClick={handleSubmit}
                                    disabled={submit.isLoading || currentJob?.status === 'running'}
                                >
                                    {currentJob?.status === 'running' ? 'Running…' : 'Run'}
                                </Button>
                                <Button
                                    size="small"
                                    variant="text"
                                    onClick={() => setShowRequest((v) => !v)}
                                    startIcon={showRequest ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                >
                                    {showRequest ? 'Hide request' : 'Show request'}
                                </Button>
                            </Stack>
                            {submit.isError && (
                                <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                                    {formatSubmitError(submit.error)}
                                </Alert>
                            )}
                            <Typography variant="subtitle2" sx={{ mb: 1 }}>Preview</Typography>
                            {previewError ? (
                                <Alert severity="warning">{previewError}</Alert>
                            ) : previewUrl ? (
                                <Box
                                    sx={{
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        borderRadius: 1,
                                        p: 1,
                                        display: 'flex',
                                        justifyContent: 'center',
                                        bgcolor: 'action.hover',
                                    }}
                                >
                                    <img
                                        src={previewUrl}
                                        alt="Test image preview"
                                        style={{ maxWidth: '100%', maxHeight: 420, objectFit: 'contain' }}
                                    />
                                </Box>
                            ) : (
                                <Box
                                    sx={{
                                        border: '1px dashed',
                                        borderColor: 'divider',
                                        borderRadius: 1,
                                        p: 3,
                                        textAlign: 'center',
                                        color: 'text.secondary',
                                        bgcolor: 'action.hover',
                                    }}
                                >
                                    <Typography variant="caption">
                                        Pick a test image to preview it here.
                                    </Typography>
                                </Box>
                            )}

                            {currentJob && (
                                <Box sx={{ mt: 3 }}>
                                    <Divider sx={{ mb: 2 }} />
                                    <JobProgress jobId={currentJob.job_id} pluginId={plugin.plugin_id} />
                                </Box>
                            )}
                        </Box>
                    </Grid>
                </Grid>
            </CardContent>

            <ImagePickerDialog
                open={imagePickerOpen}
                onClose={() => setImagePickerOpen(false)}
                onPick={handlePickImage}
                onPathChange={setLastImageDir}
                initialPath={lastImageDir ?? parentDir(pickedPath) ?? undefined}
            />
            <ImagePickerDialog
                open={templatePickerOpen}
                onClose={() => setTemplatePickerOpen(false)}
                multiple
                onPick={handlePickTemplates}
                onPathChange={setLastTemplateDir}
                title="Pick templates"
                initialPath={lastTemplateDir ?? parentDir(pickedPath) ?? undefined}
            />
        </Card>
    );
};

function parentDir(path: string | null | undefined): string | null {
    if (!path) return null;
    const norm = path.replace(/\\/g, '/');
    const idx = norm.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = norm.slice(0, idx);
    if (/^[A-Za-z]:$/.test(parent)) return parent + '/';
    return parent || '/';
}

// ---------------------------------------------------------------------------

interface JobProgressProps {
    jobId: string;
    pluginId: string;
}

const JobProgress: React.FC<JobProgressProps> = ({ jobId, pluginId }) => {
    const job = useJobStore((s) => s.jobs.find((j) => j.job_id === jobId));
    if (!job) return null;

    const statusColor =
        job.status === 'completed' ? 'success' :
        job.status === 'failed' ? 'error' :
        job.status === 'running' ? 'info' : 'default';

    return (
        <Box>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <Chip size="small" color={statusColor as any} label={job.status} />
                <Typography variant="caption" color="text.secondary">
                    job {job.job_id}
                </Typography>
            </Stack>
            {(job.status === 'running' || job.status === 'queued') && (
                <LinearProgress
                    variant="determinate"
                    value={job.progress ?? 0}
                    sx={{ height: 6, borderRadius: 1 }}
                />
            )}
            {job.status === 'failed' && job.error && (
                <Alert severity="error" sx={{ mt: 1 }}>{job.error}</Alert>
            )}
            {job.status === 'completed' && (
                <ResultRenderer pluginId={pluginId} result={job.result} />
            )}
        </Box>
    );
};

// ---------------------------------------------------------------------------

function formatSubmitError(err: any): string {
    const status = err?.response?.status;
    const data = err?.response?.data;
    const detail = typeof data?.detail === 'string'
        ? data.detail
        : data?.detail
            ? JSON.stringify(data.detail, null, 2)
            : null;
    if (status && detail) return `HTTP ${status}: ${detail}`;
    if (status) return `HTTP ${status}: ${err?.message ?? 'Request failed'}`;
    if (err?.message === 'Network Error') {
        return 'Network error — the server may have returned a response without CORS headers. Check the backend log for the real error.';
    }
    return err?.message || 'Submission failed';
}

function buildDefaults(schema: any): Record<string, any> {
    if (!schema?.properties) return {};
    const out: Record<string, any> = {};
    for (const [key, prop] of Object.entries<any>(schema.properties)) {
        if (prop?.default !== undefined) out[key] = prop.default;
    }
    return out;
}

/** Pick the schema property most likely to hold a single image path. */
function findImagePathField(schema: any): string | null {
    if (!schema?.properties) return null;
    const stringKeys = Object.entries<any>(schema.properties)
        .filter(([, prop]) => prop?.type === 'string')
        .map(([key]) => key);
    const imagePath = stringKeys.find((k) => /image.*path|micrograph.*path/i.test(k));
    if (imagePath) return imagePath;
    const anyPath = stringKeys.find((k) => /path$/i.test(k) || /_path/i.test(k));
    if (anyPath) return anyPath;
    const imageKey = stringKeys.find((k) => /image|micrograph/i.test(k));
    return imageKey ?? null;
}

// ---------------------------------------------------------------------------
// Plugin-specific test-bench presets. Values come from the plugin's own
// Sandbox README so "pick test image + pick templates + run" just works.

interface PluginPreset {
    defaults?: Record<string, any>;
    imagePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
    templatePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
}

const PLUGIN_PRESETS: Record<string, PluginPreset> = {
    'pp/template-picker': {
        defaults: {
            diameter_angstrom: 220,
            invert_templates: true,
            bin_factor: 1,
            threshold: 0.35,
        },
        imagePixelSizesByFilename: [
            { match: /24may23b/i, apix: 1.230 },
            { match: /25may06y/i, apix: 0.830 },
        ],
        templatePixelSizesByFilename: [
            { match: /origTemplate/i, apix: 2.646 },
        ],
    },
};

function pluginTestDefaultsFor(pluginId: string): Record<string, any> {
    return PLUGIN_PRESETS[pluginId]?.defaults ?? {};
}

function imagePixelSizeFor(pluginId: string, path: string): number | null {
    const preset = PLUGIN_PRESETS[pluginId];
    if (!preset?.imagePixelSizesByFilename) return null;
    const name = path.split(/[\\/]/).pop() ?? path;
    return preset.imagePixelSizesByFilename.find((r) => r.match.test(name))?.apix ?? null;
}

function templatePixelSizeFor(pluginId: string, paths: string[]): number | null {
    const preset = PLUGIN_PRESETS[pluginId];
    if (!preset?.templatePixelSizesByFilename || paths.length === 0) return null;
    // All templates must match the same rule, otherwise don't auto-fill.
    for (const rule of preset.templatePixelSizesByFilename) {
        if (paths.every((p) => rule.match.test(p.split(/[\\/]/).pop() ?? p))) {
            return rule.apix;
        }
    }
    return null;
}

/** Pick the schema property most likely to hold a list of template paths. */
function findTemplatePathsField(schema: any): string | null {
    if (!schema?.properties) return null;
    const arrayOfStringKeys = Object.entries<any>(schema.properties)
        .filter(([, prop]) => prop?.type === 'array' && prop?.items?.type === 'string')
        .map(([key]) => key);
    const templateKey = arrayOfStringKeys.find((k) => /template/i.test(k));
    if (templateKey) return templateKey;
    return arrayOfStringKeys.find((k) => /path/i.test(k)) ?? null;
}
