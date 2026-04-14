import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Collapse,
    Divider,
    LinearProgress,
    Stack,
    Typography,
    Alert,
    Chip,
} from '@mui/material';
import { ChevronDown, ChevronRight, Image as ImageIcon, Play } from 'lucide-react';
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

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

interface PluginRunnerProps {
    plugin: PluginSummary;
}

/** Schema-driven single-job runner. Progress comes from Socket.IO. */
export const PluginRunner: React.FC<PluginRunnerProps> = ({ plugin }) => {
    const { sid } = useSocket();
    const queryClient = useQueryClient();
    const { data: schema, isLoading: schemaLoading, error: schemaError } =
        usePluginInputSchema(plugin.plugin_id);
    const submit = useSubmitPluginJob(plugin.plugin_id);

    const defaults = useMemo(() => buildDefaults(schema), [schema]);
    const [values, setValues] = useState<Record<string, any>>({});
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [showRequest, setShowRequest] = useState(false);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [pickedPath, setPickedPath] = useState<string | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);

    const imagePathField = useMemo(() => findImagePathField(schema), [schema]);

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
        if (imagePathField) {
            setValues((prev) => ({ ...prev, [imagePathField]: path }));
        }
    };

    const requestPreview = useMemo(() => {
        const body: JobSubmitRequest = { input: values, name: `${plugin.name} run` };
        const base = settings.ConfigData.SERVER_API_URL.replace(/\/$/, '');
        const url = `${base}/plugins/${plugin.plugin_id}/jobs${sid ? `?sid=${sid}` : ''}`;
        return { url, body };
    }, [plugin.plugin_id, plugin.name, values, sid]);

    React.useEffect(() => {
        // Seed with schema defaults the first time the schema lands.
        if (schema && Object.keys(values).length === 0) {
            setValues(defaults);
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
                sid,
            });
            setCurrentJobId(job.job_id);
            // Seed the store immediately so the UI reflects the queued job
            // before the first Socket.IO update lands.
            useJobStore.getState().upsertJob(job);
            queryClient.invalidateQueries(['plugin-jobs']);
        } catch (err) {
            // The mutation state carries the error; nothing else to do.
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

                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="subtitle2" sx={{ flex: 1 }}>Input</Typography>
                    <Button
                        size="small"
                        variant="outlined"
                        startIcon={<ImageIcon size={14} />}
                        onClick={() => setPickerOpen(true)}
                    >
                        Pick test image…
                    </Button>
                </Stack>
                {pickedPath && (
                    <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', mb: 1, wordBreak: 'break-all' }}
                    >
                        Test image: {pickedPath}
                        {imagePathField && ` → injected into "${imagePathField}"`}
                    </Typography>
                )}
                <SchemaForm
                    schema={schema}
                    value={values}
                    onChange={setValues}
                    disabled={submit.isLoading || currentJob?.status === 'running'}
                />

                <Stack direction="row" spacing={1} sx={{ mt: 3 }} alignItems="center">
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
                    {submit.isError && (
                        <Typography color="error" variant="caption">
                            {(submit.error as any)?.response?.data?.detail || 'Submission failed'}
                        </Typography>
                    )}
                </Stack>

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

                {(previewUrl || previewError) && (
                    <Box sx={{ mt: 3 }}>
                        <Divider sx={{ mb: 2 }} />
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>Preview</Typography>
                        {previewError ? (
                            <Alert severity="warning">{previewError}</Alert>
                        ) : (
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
                                    src={previewUrl!}
                                    alt="Test image preview"
                                    style={{ maxWidth: '100%', maxHeight: 360, objectFit: 'contain' }}
                                />
                            </Box>
                        )}
                    </Box>
                )}

                {currentJob && (
                    <Box sx={{ mt: 3 }}>
                        <Divider sx={{ mb: 2 }} />
                        <JobProgress jobId={currentJob.job_id} pluginId={plugin.plugin_id} />
                    </Box>
                )}
            </CardContent>

            <ImagePickerDialog
                open={pickerOpen}
                onClose={() => setPickerOpen(false)}
                onPick={handlePickImage}
                initialPath={pickedPath ?? undefined}
            />
        </Card>
    );
};

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

function buildDefaults(schema: any): Record<string, any> {
    if (!schema?.properties) return {};
    const out: Record<string, any> = {};
    for (const [key, prop] of Object.entries<any>(schema.properties)) {
        if (prop?.default !== undefined) out[key] = prop.default;
    }
    return out;
}

/** Pick the schema property most likely to hold an image path. */
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
