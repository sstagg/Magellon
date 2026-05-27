import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    LinearProgress,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import type { ChipProps } from "@mui/material";
import ErrorIcon from "@mui/icons-material/Error";
import Inventory2Icon from "@mui/icons-material/Inventory2";
import BlurCircularIcon from "@mui/icons-material/BlurCircular";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import SettingsSuggestIcon from "@mui/icons-material/SettingsSuggest";
import { CheckCircle, Clock, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import type {
    ParticleExportStatus,
    ParticlePipelineStage,
    ParticlePipelineSummary,
} from "../lib/useParticleExportPipelineProgress.ts";

const statusColor = (status: string): ChipProps["color"] => {
    if (status === "completed") return "success";
    if (status === "failed") return "error";
    if (status === "cancelled") return "warning";
    if (status === "queued") return "default";
    return "info";
};

const formatElapsed = (ms: number) => {
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return `${m}m ${s % 60}s`;
};

const stageIcon = (key: string): ReactNode => {
    if (key === "prepare") return <FactCheckIcon fontSize="small" />;
    if (key === "extract") return <Inventory2Icon fontSize="small" />;
    if (key === "classify") return <BlurCircularIcon fontSize="small" />;
    return <SettingsSuggestIcon fontSize="small" />;
};

const StageRow = ({ stage }: { stage: ParticlePipelineStage }) => {
    const pct = Math.max(0, Math.min(100, Number(stage.progress || 0)));
    const complete = stage.status === "completed";
    return (
        <TableRow>
            <TableCell sx={{ py: 1, pr: 1, width: 32, color: complete ? "success.main" : "text.secondary" }}>
                {stageIcon(stage.key)}
            </TableCell>
            <TableCell sx={{ py: 1, minWidth: 150 }}>
                <Typography variant="body2">{stage.label}</Typography>
                {stage.detail && (
                    <Typography variant="caption" color="text.secondary">{stage.detail}</Typography>
                )}
            </TableCell>
            <TableCell sx={{ py: 1, width: "38%" }}>
                <Tooltip title={`${pct}%`} arrow>
                    <Box>
                        <LinearProgress
                            variant={stage.status === "running" && pct === 0 ? "indeterminate" : "determinate"}
                            value={pct}
                            color={complete ? "success" : "primary"}
                            sx={{ height: 6, borderRadius: 3 }}
                        />
                    </Box>
                </Tooltip>
            </TableCell>
            <TableCell align="right" sx={{ py: 1, whiteSpace: "nowrap" }}>
                <Chip label={stage.status} color={statusColor(stage.status)} size="small" variant="outlined" />
            </TableCell>
        </TableRow>
    );
};

type Props = {
    open: boolean;
    onClose: () => void;
    status: ParticleExportStatus;
    error: string | null;
    jobId: string | null;
    summary: ParticlePipelineSummary | null;
    elapsedMs: number;
    sessionName: string | null;
};

export const ParticleExportPipelineProgressDialog = ({
    open,
    onClose,
    status,
    error,
    jobId,
    summary,
    elapsedMs,
    sessionName,
}: Props) => {
    const isBusy = status === "scheduling" || status === "running";
    const overallPct = summary?.progress ?? (status === "success" ? 100 : 0);
    const result = summary?.result;

    return (
        <Dialog open={open} onClose={isBusy ? undefined : onClose} fullWidth maxWidth="sm">
            <DialogTitle>
                {sessionName ? `Export pipeline: ${sessionName}` : "Particle export pipeline"}
            </DialogTitle>
            <DialogContent>
                <Stack spacing={2}>
                    {status === "scheduling" && (
                        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                            <CircularProgress size={22} />
                            <Typography>Scheduling particle extraction and classification...</Typography>
                        </Stack>
                    )}

                    {status === "success" && (
                        <Alert icon={<CheckCircle size={20} />} severity="success">
                            Particle extraction and 2D classification completed.
                        </Alert>
                    )}

                    {status === "error" && (
                        <Alert icon={<ErrorIcon />} severity="error">
                            {error || summary?.error || "Particle export pipeline failed"}
                        </Alert>
                    )}

                    {summary && (
                        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                            <Chip label={summary.derived_status} color={statusColor(summary.derived_status)} size="small" />
                            {elapsedMs > 0 && (
                                <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                                    <Clock size={14} />
                                    <Typography variant="caption" color="text.secondary">
                                        {formatElapsed(elapsedMs)}
                                    </Typography>
                                </Stack>
                            )}
                            {summary.stage_key && (
                                <Chip label={summary.stage_key} size="small" variant="outlined" />
                            )}
                        </Stack>
                    )}

                    {(status === "running" || status === "success") && (
                        <Box>
                            <Stack direction="row" sx={{ mb: 0.5, justifyContent: "space-between" }}>
                                <Typography variant="caption" color="text.secondary">Overall</Typography>
                                <Typography variant="caption" color="text.secondary">{overallPct}%</Typography>
                            </Stack>
                            <LinearProgress
                                variant={summary ? "determinate" : "indeterminate"}
                                value={overallPct}
                                color={status === "success" ? "success" : "primary"}
                                sx={{ height: 8, borderRadius: 4 }}
                            />
                        </Box>
                    )}

                    {summary?.stages?.length ? (
                        <>
                            <Divider />
                            <Typography variant="subtitle2" color="text.secondary">
                                Pipeline steps
                            </Typography>
                            <Table size="small" sx={{ "& td, & th": { border: 0 } }}>
                                <TableBody>
                                    {summary.stages.map((stage) => (
                                        <StageRow key={stage.key} stage={stage} />
                                    ))}
                                </TableBody>
                            </Table>
                        </>
                    ) : null}

                    {summary?.child_jobs?.length ? (
                        <>
                            <Divider />
                            <Typography variant="subtitle2" color="text.secondary">
                                Plugin jobs
                            </Typography>
                            <Stack spacing={1}>
                                {summary.child_jobs.map((child) => (
                                    <Stack
                                        key={child.key}
                                        direction="row"
                                        spacing={1}
                                        sx={{ alignItems: "center", justifyContent: "space-between" }}
                                    >
                                        <Box sx={{ minWidth: 0 }}>
                                            <Typography variant="body2">
                                                {child.label || child.plugin_id || child.key}
                                            </Typography>
                                            {child.job_id && (
                                                <Typography variant="caption" color="text.disabled" sx={{ display: "block" }}>
                                                    Job: {child.job_id}
                                                </Typography>
                                            )}
                                        </Box>
                                        <Chip
                                            label={child.status || "queued"}
                                            color={statusColor(child.status || "queued")}
                                            size="small"
                                            variant="outlined"
                                        />
                                    </Stack>
                                ))}
                            </Stack>
                        </>
                    ) : null}

                    {result && (
                        <>
                            <Divider />
                            <Typography variant="subtitle2" color="text.secondary">
                                Outputs
                            </Typography>
                            <Stack spacing={0.5}>
                                <Typography variant="caption" color="text.secondary">
                                    Stack artifact: {result.particle_stack_artifact_id}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    Class averages artifact: {result.class_averages_artifact_id}
                                </Typography>
                                {result.output_root && (
                                    <Typography variant="caption" color="text.secondary" sx={{ wordBreak: "break-all" }}>
                                        Output: {result.output_root}
                                    </Typography>
                                )}
                            </Stack>
                        </>
                    )}

                    {jobId && (
                        <Typography variant="caption" color="text.disabled">
                            Job: {jobId}
                        </Typography>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                {isBusy ? (
                    <Button startIcon={<RefreshCcw size={16} />} disabled size="small">
                        Updating...
                    </Button>
                ) : (
                    <Button onClick={onClose} size="small">Close</Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
