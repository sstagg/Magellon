/**
 * Workflow lineage viewer — renders the chain ``GET
 * /artifacts/{oid}/workflow.json`` returns as a vertical stack of
 * artifact cards. The root card is at top; ancestors stack below,
 * walking back toward the imported source.
 *
 * Each card surfaces:
 *   - artifact OID + kind (chip + monospace tail of the UUID)
 *   - producer plugin id + version (or "imported" badge for roots)
 *   - parameters used (collapsible JSON)
 *   - "Re-run with these params" button (CryoSPARC-style clone)
 *
 * No visual workflow editor — that's Pro. The OSS viewer is a clear
 * vertical list, with the producer-and-params block being the actual
 * load-bearing UX: it answers "how did this come to exist?" without
 * touching the database.
 */
import React, { useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AlertTriangle,
    ChevronDown,
    ChevronRight,
    Download,
    Play,
    Workflow as WorkflowIcon,
} from 'lucide-react';
import {
    useArtifactWorkflow,
    useReRunFromWorkflow,
    type WorkflowNode,
} from '../api/ArtifactApi.ts';


const shortenOid = (oid: string): string =>
    oid.length > 12 ? `${oid.slice(0, 8)}…${oid.slice(-4)}` : oid;


const ParamsBlock: React.FC<{ params: Record<string, unknown> | undefined }> = ({ params }) => {
    const [open, setOpen] = useState(false);
    if (!params || Object.keys(params).length === 0) return null;
    return (
        <Box sx={{ mt: 1 }}>
            <Stack
                direction="row"
                spacing={0.5}
                sx={{ alignItems: 'center', cursor: 'pointer' }}
                onClick={() => setOpen((o) => !o)}
            >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Params ({Object.keys(params).length})
                </Typography>
            </Stack>
            <Collapse in={open} unmountOnExit>
                <Box
                    sx={{
                        mt: 0.5,
                        p: 1,
                        borderRadius: 1,
                        border: '1px solid',
                        borderColor: 'divider',
                        bgcolor: (t) => (t.palette.mode === 'dark' ? 'grey.900' : 'grey.50'),
                        fontFamily: 'monospace',
                        fontSize: 12,
                        overflowX: 'auto',
                    }}
                >
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(params, null, 2)}
                    </pre>
                </Box>
            </Collapse>
        </Box>
    );
};


const NodeCard: React.FC<{
    node: WorkflowNode;
    isRoot: boolean;
    onReRun: (node: WorkflowNode) => void;
    reRunning: boolean;
}> = ({ node, isRoot, onReRun, reRunning }) => {
    const isImported = !node.producer;
    return (
        <Card variant="outlined" sx={{ borderColor: isRoot ? 'primary.main' : 'divider' }}>
            <CardContent sx={{ pb: '12px !important' }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    {isRoot && (
                        <Chip size="small" color="primary" label="Root" />
                    )}
                    <Chip size="small" variant="outlined" label={node.kind} />
                    <Tooltip title={node.oid} placement="top" arrow>
                        <Typography
                            variant="caption"
                            sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                        >
                            {shortenOid(node.oid)}
                        </Typography>
                    </Tooltip>
                    {isImported && (
                        <Chip
                            size="small"
                            variant="outlined"
                            icon={<Download size={12} />}
                            label={node.source ?? 'imported'}
                        />
                    )}
                </Stack>

                {node.producer && (
                    <>
                        <Typography variant="body2" sx={{ mt: 1 }}>
                            <strong>{node.producer.plugin_id}</strong>{' '}
                            <Typography
                                component="span"
                                variant="caption"
                                sx={{ color: 'text.secondary' }}
                            >
                                v{node.producer.plugin_version} · {node.producer.category}
                            </Typography>
                        </Typography>
                        <ParamsBlock params={node.producer.params} />
                        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                            <Tooltip
                                title="Re-submit this node's producing job with the same params"
                                placement="top"
                                arrow
                            >
                                <span>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={
                                            reRunning ? (
                                                <CircularProgress size={12} />
                                            ) : (
                                                <Play size={14} />
                                            )
                                        }
                                        disabled={reRunning}
                                        onClick={() => onReRun(node)}
                                    >
                                        Re-run
                                    </Button>
                                </span>
                            </Tooltip>
                        </Stack>
                    </>
                )}
            </CardContent>
        </Card>
    );
};


export const WorkflowChainView: React.FC<{ oid: string }> = ({ oid }) => {
    const { data, isLoading, error } = useArtifactWorkflow(oid);
    const reRun = useReRunFromWorkflow();
    const [feedback, setFeedback] = useState<
        { severity: 'success' | 'error'; text: string } | null
    >(null);

    const handleReRun = async (node: WorkflowNode) => {
        if (!node.producer) return;
        // Check for redaction — if the params block contains the
        // sentinel ``"<redacted>"`` value, surface this to the
        // operator so they don't accidentally re-run with a literal
        // ``<redacted>`` string in place of a secret.
        const redactedKeys = Object.entries(node.producer.params)
            .filter(([, v]) => v === '<redacted>')
            .map(([k]) => k);
        if (redactedKeys.length > 0) {
            const proceed = window.confirm(
                `These params were redacted server-side: ${redactedKeys.join(', ')}. ` +
                `Re-running will pass "<redacted>" literally. Continue?`,
            );
            if (!proceed) return;
        }
        try {
            const res = await reRun.mutateAsync({
                plugin_id: node.producer.plugin_id,
                input: node.producer.params,
            });
            setFeedback({
                severity: 'success',
                text: `Submitted re-run as job ${res.job_id}.`,
            });
        } catch (err: unknown) {
            const r = err as { response?: { data?: { detail?: unknown } }; message?: string };
            const detail = r.response?.data?.detail;
            setFeedback({
                severity: 'error',
                text:
                    typeof detail === 'string'
                        ? detail
                        : r.message ?? 'Re-run failed',
            });
        }
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
            </Box>
        );
    }
    if (error || !data) {
        return (
            <Alert severity="error" icon={<AlertTriangle size={18} />}>
                Workflow not found for this artifact.
            </Alert>
        );
    }

    return (
        <Stack spacing={2}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <WorkflowIcon size={20} />
                <Typography variant="h6" sx={{ flex: 1 }}>
                    Workflow lineage
                </Typography>
                <Chip
                    size="small"
                    variant="outlined"
                    label={data.lineage_shape}
                />
                {data.truncated_at_depth !== null && (
                    <Tooltip title="Chain exceeded the depth cap; older ancestors omitted">
                        <Chip size="small" color="warning" label="Truncated" />
                    </Tooltip>
                )}
            </Stack>

            {feedback && (
                <Alert
                    severity={feedback.severity}
                    onClose={() => setFeedback(null)}
                >
                    {feedback.text}
                </Alert>
            )}

            <NodeCard
                node={data.root_artifact}
                isRoot
                onReRun={handleReRun}
                reRunning={reRun.isPending}
            />

            {data.ancestors.map((node) => (
                <NodeCard
                    key={node.oid}
                    node={node}
                    isRoot={false}
                    onReRun={handleReRun}
                    reRunning={reRun.isPending}
                />
            ))}

            {data.ancestors.length === 0 && (
                <Alert severity="info">
                    No ancestors — this artifact was imported directly.
                </Alert>
            )}
        </Stack>
    );
};
