import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Divider,
    LinearProgress,
    Stack,
    Typography,
    Alert,
    Chip,
} from '@mui/material';
import { Play } from 'lucide-react';
import { useQueryClient } from 'react-query';
import {
    usePluginInputSchema,
    useSubmitPluginJob,
    PluginSummary,
} from '../api/PluginApi.ts';
import { SchemaForm } from './SchemaForm.tsx';
import { ResultRenderer } from './results/ResultRenderers.tsx';
import { useJobStore } from '../../../app/layouts/PanelLayout/useJobStore.ts';
import { useSocket } from '../../../shared/lib/useSocket.ts';

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

                <Typography variant="subtitle2" sx={{ mb: 1 }}>Input</Typography>
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
                    {submit.isError && (
                        <Typography color="error" variant="caption">
                            {(submit.error as any)?.response?.data?.detail || 'Submission failed'}
                        </Typography>
                    )}
                </Stack>

                {currentJob && (
                    <Box sx={{ mt: 3 }}>
                        <Divider sx={{ mb: 2 }} />
                        <JobProgress jobId={currentJob.job_id} pluginId={plugin.plugin_id} />
                    </Box>
                )}
            </CardContent>
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
