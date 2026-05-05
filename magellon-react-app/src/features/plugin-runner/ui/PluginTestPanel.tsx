/**
 * Plugin detail page's "Settings + Activity" workspace.
 *
 * Two columns, always visible side-by-side:
 *
 *   Settings (left, sticky)         Activity (right, scrolls)
 *   ────────────────────            ──────────────────────────
 *   Transport: Bus / Sync           ProgressTracker (bus only)
 *   SchemaForm (input)              Wire envelopes — out + in
 *   Run button                      Result (output schema-driven)
 *
 * On bus: submits via POST /plugins/{id}/jobs and joins the
 * job:{job_id} Socket.IO room; ProgressTracker, envelope card, and
 * result block populate from the live event stream
 * (``step_event`` + ``plugin_test_envelope``).
 *
 * On sync: posts to POST /dispatch/{category}/run; the HTTP response
 * lands in the result block and a synthetic envelope pair populates
 * the wire envelope card so the layout stays consistent across
 * transports.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    FormControlLabel,
    IconButton,
    Radio,
    RadioGroup,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Activity,
    ArrowDownLeft,
    ArrowUpRight,
    ChevronDown,
    ChevronRight,
    Play,
    Zap,
} from 'lucide-react';

import { SchemaForm, type BrowseFileRequest } from '../../../shared/ui/SchemaForm.tsx';
import {
    PluginSummary,
    useCategoryCapabilities,
    useDispatchSync,
    usePluginInputSchema,
    usePluginOutputSchema,
    useSubmitPluginJob,
} from '../api/PluginApi.ts';
import { ImagePickerDialog } from './ImagePickerDialog.tsx';
import { ProgressTracker } from './ProgressTracker.tsx';
import { useSocket } from '../../../shared/lib/useSocket.ts';

type Transport = 'bus' | 'sync';

interface EnvelopeFrame {
    direction: 'out' | 'in';
    kind: 'task' | 'result';
    transport: Transport;
    queue?: string | null;
    payload: unknown;
    /** Timestamp the React side recorded the frame, for ordering. */
    seenAt: number;
}

interface PluginTestPanelProps {
    plugin: PluginSummary;
    /** When false, renders the form but disables Run with a hint
     *  (e.g. plugin installed but not running). */
    runEnabled?: boolean;
    runDisabledReason?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatError = (err: unknown, fallback: string): string => {
    if (typeof err === 'object' && err !== null) {
        const r = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
        const detail = r.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
            return detail.map((d: any) => d?.msg || JSON.stringify(d)).join('\n');
        }
        if (typeof r.message === 'string') return r.message;
    }
    return fallback;
};

const buildDefaults = (schema: any): Record<string, unknown> => {
    if (!schema?.properties) return {};
    const out: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries<any>(schema.properties)) {
        if (prop?.default !== undefined) out[key] = prop.default;
    }
    return out;
};

// ---------------------------------------------------------------------------
// Envelope wire-shape pretty-printer
// ---------------------------------------------------------------------------

const EnvelopeCard: React.FC<{ frame: EnvelopeFrame }> = ({ frame }) => {
    const [open, setOpen] = useState(false);
    const isOut = frame.direction === 'out';
    const arrow = isOut ? <ArrowUpRight size={14} /> : <ArrowDownLeft size={14} />;
    const tone = isOut ? 'primary' : 'success';
    const label = isOut ? 'TaskMessage' : frame.kind === 'result' ? 'TaskResult' : 'Response';

    return (
        <Card variant="outlined" sx={{ mb: 1 }}>
            <Box
                onClick={() => setOpen((o) => !o)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setOpen((o) => !o);
                }}
                sx={{
                    px: 1.5, py: 0.75,
                    display: 'flex', alignItems: 'center', gap: 1,
                    cursor: 'pointer',
                    borderBottom: open ? '1px solid' : 'none',
                    borderColor: 'divider',
                    '&:hover': { bgcolor: 'action.hover' },
                }}
            >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <Chip
                    size="small"
                    icon={arrow}
                    color={tone as any}
                    variant="outlined"
                    label={isOut ? 'OUT' : 'IN'}
                />
                <Typography variant="caption" sx={{ fontFamily: 'monospace', flex: 1 }}>
                    {label}
                </Typography>
                {frame.queue && (
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                        {frame.queue}
                    </Typography>
                )}
                <Chip size="small" label={frame.transport} variant="outlined" />
            </Box>
            {open && (
                <Box
                    sx={{
                        px: 1.5, py: 1,
                        bgcolor: (t) => t.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
                        fontFamily: 'monospace', fontSize: 11,
                        overflowX: 'auto', maxHeight: 400, overflowY: 'auto',
                    }}
                >
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {JSON.stringify(frame.payload, null, 2)}
                    </pre>
                </Box>
            )}
        </Card>
    );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const PluginTestPanel: React.FC<PluginTestPanelProps> = ({
    plugin,
    runEnabled = true,
    runDisabledReason,
}) => {
    const { socket, sid, on, emit } = useSocket();
    const inputSchemaQ = usePluginInputSchema(plugin.plugin_id);
    const outputSchemaQ = usePluginOutputSchema(plugin.plugin_id);
    const capabilitiesQ = useCategoryCapabilities(plugin.category);
    const submit = useSubmitPluginJob(plugin.plugin_id);
    const sync = useDispatchSync(plugin.category ?? '');

    const inputSchema = inputSchemaQ.data ?? capabilitiesQ.data?.input_schema;
    const outputSchema = outputSchemaQ.data ?? capabilitiesQ.data?.output_schema;

    // Capability-aware transport availability — Sync is only offered
    // when at least one backend in the category advertises it.
    const supportsSync = useMemo(() => {
        const backends = capabilitiesQ.data?.backends ?? [];
        return backends.some((b) =>
            b.enabled && (b.capabilities ?? []).includes('sync'),
        );
    }, [capabilitiesQ.data]);

    const [transport, setTransport] = useState<Transport>('bus');
    useEffect(() => {
        // If Sync gets disabled at runtime (replica died), drop back to Bus.
        if (transport === 'sync' && !supportsSync) setTransport('bus');
    }, [supportsSync, transport]);

    const defaults = useMemo(() => buildDefaults(inputSchema), [inputSchema]);
    const [values, setValues] = useState<Record<string, unknown>>({});
    useEffect(() => {
        // Seed the form with schema-declared defaults the first time we
        // see the schema. Don't clobber user edits on subsequent reseats.
        setValues((prev) => (Object.keys(prev).length ? prev : defaults));
    }, [defaults]);

    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [envelopes, setEnvelopes] = useState<EnvelopeFrame[]>([]);
    const [syncResult, setSyncResult] = useState<unknown | null>(null);
    const [syncError, setSyncError] = useState<string | null>(null);

    // GPFS picker bridge — opens for any SchemaForm field that asks
    // (file_path / file_path_list ui_widget, or a heuristic match like
    // image_path / template_paths). The dialog stays mounted but only
    // renders when ``pickerRequest`` is set.
    const [pickerRequest, setPickerRequest] = useState<BrowseFileRequest | null>(null);
    const handleBrowseFile = (request: BrowseFileRequest) => setPickerRequest(request);

    // Subscribe to Socket.IO envelope tap for the current job. Same room
    // as step_event — joined once we have a job_id.
    useEffect(() => {
        if (!socket || !currentJobId) return;
        emit('join_job_room', { job_id: currentJobId });
        const off = on('plugin_test_envelope', (frame: any) => {
            setEnvelopes((prev) => [
                ...prev,
                { ...frame, seenAt: Date.now() } as EnvelopeFrame,
            ]);
        });
        return () => {
            off();
            emit('leave_job_room', { job_id: currentJobId });
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [socket, currentJobId]);

    const handleRun = async () => {
        setEnvelopes([]);
        setSyncResult(null);
        setSyncError(null);

        if (transport === 'sync') {
            try {
                const result = await sync.mutateAsync({ input: values });
                setSyncResult(result);
                // Render synthetic envelopes so the activity column has
                // a uniform shape regardless of transport.
                const now = Date.now();
                setEnvelopes([
                    {
                        direction: 'out', kind: 'task', transport: 'sync',
                        payload: { input: values },
                        seenAt: now,
                    },
                    {
                        direction: 'in', kind: 'result', transport: 'sync',
                        payload: result,
                        seenAt: now + 1,
                    },
                ]);
            } catch (err) {
                setSyncError(formatError(err, 'sync dispatch failed'));
            }
            return;
        }

        // Bus transport — submit and let Socket.IO drive the rest.
        try {
            const job = await submit.mutateAsync({ input: values, sid });
            setCurrentJobId(String(job.job_id));
        } catch (err) {
            setSyncError(formatError(err, 'bus dispatch failed'));
        }
    };

    const isBusy =
        (transport === 'bus' && submit.isLoading) ||
        (transport === 'sync' && sync.isLoading);

    // ----- Layout -----

    const settingsColumn = (
        <Stack spacing={2}>
            <Box>
                <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5 }}>
                    Transport
                </Typography>
                <RadioGroup
                    row
                    value={transport}
                    onChange={(e) => setTransport(e.target.value as Transport)}
                    sx={{ mt: 0.5 }}
                >
                    <FormControlLabel
                        value="bus"
                        control={<Radio size="small" />}
                        label={
                            <Tooltip title="Dispatch via RabbitMQ. Live envelope + step events stream over Socket.IO." placement="top">
                                <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                    <Activity size={14} /> <span>Bus</span>
                                </Stack>
                            </Tooltip>
                        }
                    />
                    <FormControlLabel
                        value="sync"
                        control={<Radio size="small" />}
                        disabled={!supportsSync}
                        label={
                            <Tooltip
                                title={
                                    supportsSync
                                        ? 'Call the plugin\'s HTTP /execute synchronously.'
                                        : 'No live backend in this category advertises Capability.SYNC.'
                                }
                                placement="top"
                            >
                                <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                                    <Zap size={14} /> <span>Sync</span>
                                </Stack>
                            </Tooltip>
                        }
                    />
                </RadioGroup>
            </Box>

            <Divider />

            <Box>
                <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5 }}>
                    Inputs
                </Typography>
                {inputSchemaQ.isLoading && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                        <CircularProgress size={20} />
                    </Box>
                )}
                {inputSchemaQ.isError && !inputSchema && (
                    <Alert severity="warning">
                        Could not load input schema for this plugin.
                    </Alert>
                )}
                {inputSchema && (
                    <SchemaForm
                        schema={inputSchema as any}
                        values={values}
                        onChange={setValues}
                        disabled={!runEnabled || isBusy}
                        onBrowseFile={handleBrowseFile}
                    />
                )}
            </Box>

            {syncError && (
                <Alert severity="error" onClose={() => setSyncError(null)} sx={{ whiteSpace: 'pre-wrap' }}>
                    {syncError}
                </Alert>
            )}

            <Stack direction="row" spacing={1}>
                <Button
                    variant="contained"
                    fullWidth
                    startIcon={isBusy ? <CircularProgress size={14} color="inherit" /> : <Play size={16} />}
                    onClick={handleRun}
                    disabled={!runEnabled || isBusy || !inputSchema}
                >
                    {isBusy ? 'Running…' : 'Run'}
                </Button>
            </Stack>

            {!runEnabled && runDisabledReason && (
                <Alert severity="info">{runDisabledReason}</Alert>
            )}
        </Stack>
    );

    const activityColumn = (
        <Stack spacing={2}>
            {transport === 'bus' && currentJobId && (
                <Card variant="outlined">
                    <CardContent sx={{ pb: '16px !important' }}>
                        <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5 }}>
                            Progress
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                            <ProgressTracker jobId={currentJobId} />
                        </Box>
                    </CardContent>
                </Card>
            )}

            <Card variant="outlined">
                <CardContent sx={{ pb: '16px !important' }}>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
                        <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5, flex: 1 }}>
                            Wire envelopes
                        </Typography>
                        {envelopes.length > 0 && (
                            <Chip size="small" label={`${envelopes.length}`} />
                        )}
                    </Stack>
                    {envelopes.length === 0 ? (
                        <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
                            No envelopes yet — Run sends the dispatched
                            TaskMessage and result here in real time.
                        </Typography>
                    ) : (
                        <Box>
                            {envelopes.map((f, i) => (
                                <EnvelopeCard key={i} frame={f} />
                            ))}
                        </Box>
                    )}
                </CardContent>
            </Card>

            {(syncResult || envelopes.some((e) => e.direction === 'in')) && (
                <Card variant="outlined">
                    <CardContent sx={{ pb: '16px !important' }}>
                        <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 0.5 }}>
                            Result
                        </Typography>
                        <Box
                            sx={{
                                mt: 1,
                                p: 1.5,
                                borderRadius: 1,
                                border: '1px solid',
                                borderColor: 'divider',
                                bgcolor: (t) => t.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
                                fontFamily: 'monospace', fontSize: 11,
                                overflowX: 'auto', maxHeight: 400, overflowY: 'auto',
                            }}
                        >
                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                {JSON.stringify(
                                    syncResult ??
                                    envelopes.find((e) => e.direction === 'in')?.payload,
                                    null,
                                    2,
                                )}
                            </pre>
                        </Box>
                        {outputSchema && (
                            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                                Output schema: {(outputSchema as any)?.title ?? 'available via /schema/output'}
                            </Typography>
                        )}
                    </CardContent>
                </Card>
            )}
        </Stack>
    );

    return (
        <Box
            sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '380px 1fr' },
                gap: 2,
                alignItems: 'start',
            }}
        >
            <Box sx={{ position: { md: 'sticky' }, top: { md: 16 } }}>
                <Card variant="outlined">
                    <CardContent>{settingsColumn}</CardContent>
                </Card>
            </Box>
            <Box>{activityColumn}</Box>

            {/* GPFS browser dialog — driven by SchemaForm's onBrowseFile.
                We always render the component but gate ``open`` on the
                pickerRequest so opening/closing is cheap. */}
            {pickerRequest && (
                pickerRequest.multiple ? (
                    <ImagePickerDialog
                        open
                        multiple
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(paths) => {
                            pickerRequest.onPick(paths);
                            setPickerRequest(null);
                        }}
                        initialPath={
                            Array.isArray(pickerRequest.current) && pickerRequest.current[0]
                                ? parentDir(pickerRequest.current[0])
                                : undefined
                        }
                    />
                ) : (
                    <ImagePickerDialog
                        open
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(path) => {
                            pickerRequest.onPick(path);
                            setPickerRequest(null);
                        }}
                        initialPath={
                            typeof pickerRequest.current === 'string'
                                ? parentDir(pickerRequest.current)
                                : undefined
                        }
                    />
                )
            )}
        </Box>
    );
};

function parentDir(p: string | null): string | undefined {
    if (!p) return undefined;
    const idx = p.replace(/\\/g, '/').lastIndexOf('/');
    if (idx <= 0) return undefined;
    return p.slice(0, idx);
}

export default PluginTestPanel;
