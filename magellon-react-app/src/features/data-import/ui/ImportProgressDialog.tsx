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
import ImageIcon from "@mui/icons-material/Image";
import BarChartIcon from "@mui/icons-material/BarChart";
import BlurOnIcon from "@mui/icons-material/BlurOn";
import VideocamIcon from "@mui/icons-material/Videocam";
import { CheckCircle, Clock, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import type {
    ImportStatus,
    ImportSummary,
    StepCounts,
} from "../lib/useImportJobProgress.ts";

// ── Step config — drives the pipeline-steps table ────────────────────────────

type StepDef = {
    key: keyof StepCounts;
    label: string;
    icon: ReactNode;
    color: "primary" | "secondary" | "info" | "warning";
    weight: number;          // contribution to weighted overall progress
    pluginCategory?: string; // when set, render the completion sub-bar from
                             // summary.by_category[pluginCategory]
};

// Defaults model the Magellon importer's emitted step counters.
// Other importers that emit the same `import_progress` shape will reuse them;
// custom step sets can be passed via the `steps` prop.
export const DEFAULT_IMPORT_STEPS: StepDef[] = [
    { key: "png",       label: "PNG Conversion",   icon: <ImageIcon fontSize="small" />,    color: "primary",   weight: 1 },
    { key: "fft",       label: "FFT Computation",  icon: <BarChartIcon fontSize="small" />, color: "info",      weight: 1 },
    { key: "ctf",       label: "CTF Estimation",   icon: <BlurOnIcon fontSize="small" />,   color: "secondary", weight: 2, pluginCategory: "ctf" },
    { key: "motioncor", label: "Motion Correction",icon: <VideocamIcon fontSize="small" />, color: "warning",   weight: 7, pluginCategory: "motioncor" },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

const statusColor = (status: string): ChipProps["color"] => {
    if (status === "completed") return "success";
    if (status === "failed") return "error";
    if (status === "cancelled") return "warning";
    return "info";
};

const formatElapsed = (ms: number) => {
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return `${m}m ${s % 60}s`;
};

// ── Pipeline step row ────────────────────────────────────────────────────────

type StepRowProps = {
    icon: ReactNode;
    label: string;
    done: number;
    total: number;
    tooltip?: string;
    color?: "primary" | "secondary" | "info" | "success" | "warning";
    completed?: number;
    failed?: number;
};

const StepRow = ({ icon, label, done, total, tooltip, color = "primary", completed, failed }: StepRowProps) => {
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const isComplete = total > 0 && done >= total;
    const showPluginCounter = completed !== undefined || failed !== undefined;
    const completedPct = total > 0 && completed !== undefined
        ? Math.round((completed / total) * 100)
        : 0;
    const allReturned = total > 0
        && completed !== undefined
        && (completed + (failed ?? 0)) >= total;
    return (
        <TableRow>
            <TableCell sx={{ py: 1, pr: 1, width: 32, color: isComplete ? "success.main" : "text.secondary" }}>
                {icon}
            </TableCell>
            <TableCell sx={{ py: 1, minWidth: 130 }}>
                <Typography variant="body2">{label}</Typography>
            </TableCell>
            <TableCell sx={{ py: 1, width: "40%" }}>
                <Tooltip title={tooltip ?? `${done} / ${total}`} arrow>
                    <Box>
                        <LinearProgress
                            variant="determinate"
                            value={pct}
                            color={isComplete ? "success" : color}
                            sx={{ height: 6, borderRadius: 3 }}
                        />
                        {showPluginCounter && total > 0 && (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
                                <Box sx={{ flex: 1 }}>
                                    <LinearProgress
                                        variant="determinate"
                                        value={completedPct}
                                        color={allReturned ? "success" : "info"}
                                        sx={{ height: 3, borderRadius: 2, opacity: 0.7 }}
                                    />
                                </Box>
                                <Typography
                                    variant="caption"
                                    sx={{ fontSize: 10, lineHeight: 1, whiteSpace: "nowrap" }}
                                    color="text.secondary"
                                >
                                    ✓ {completed ?? 0}
                                    {(failed ?? 0) > 0 && (
                                        <Typography
                                            component="span"
                                            variant="caption"
                                            sx={{ fontSize: 10, ml: 0.5 }}
                                            color="error"
                                        >
                                            ✗ {failed}
                                        </Typography>
                                    )}
                                </Typography>
                            </Box>
                        )}
                    </Box>
                </Tooltip>
            </TableCell>
            <TableCell align="right" sx={{ py: 1, whiteSpace: "nowrap" }}>
                <Typography variant="body2" color={isComplete ? "success.main" : "text.primary"}>
                    {done}
                    {total > 0 && (
                        <Typography component="span" variant="caption" color="text.secondary">
                            {" "}/ {total}
                        </Typography>
                    )}
                </Typography>
            </TableCell>
            <TableCell align="right" sx={{ py: 1, width: 48 }}>
                {total > 0 && (
                    <Typography variant="caption" color="text.secondary">{pct}%</Typography>
                )}
            </TableCell>
        </TableRow>
    );
};

// ── Dialog ───────────────────────────────────────────────────────────────────

export type ImportProgressDialogProps = {
    open: boolean;
    onClose: () => void;
    status: ImportStatus;
    error: string | null;
    jobId: string | null;
    summary: ImportSummary | null;
    stepCounts: StepCounts | null;
    stepTotals: StepCounts | null;
    elapsedMs: number;
    sessionName: string | null;
    // "Magellon import" / "Leginon import" / "SerialEM import" — shown when no
    // session name is available yet (before the first summary poll).
    titleFallback?: string;
    // Override per importer. Steps the host doesn't emit will render at 0/0
    // (the dialog hides rows whose total is 0 if not also rendered).
    steps?: StepDef[];
};

export const ImportProgressDialog = ({
    open, onClose, status, error, jobId, summary,
    stepCounts, stepTotals, elapsedMs, sessionName,
    titleFallback = "Import",
    steps = DEFAULT_IMPORT_STEPS,
}: ImportProgressDialogProps) => {

    // Weighted-overall: each step contributes weight × (done / total). Steps
    // with no total (e.g. an importer that doesn't emit MotionCor counts)
    // contribute zero on both sides — they don't drag the bar.
    const overallWorkTotal = steps.reduce(
        (acc, s) => acc + s.weight * (stepTotals?.[s.key] ?? 0), 0,
    );
    const overallWorkDone = steps.reduce(
        (acc, s) => acc + s.weight * (stepCounts?.[s.key] ?? 0), 0,
    );
    // Fallback when no step counts are emitted: use task-level terminal/total.
    const fallbackPct = summary && summary.total_tasks > 0
        ? Math.round((summary.terminal_tasks / summary.total_tasks) * 100)
        : 0;
    const overallPct = overallWorkTotal > 0
        ? Math.min(100, Math.round((overallWorkDone / overallWorkTotal) * 100))
        : fallbackPct;
    const overallImages = summary?.total_tasks ?? 0;
    const isRunningOrSuccess = status === "running" || status === "success";
    const isBusy = status === "scheduling" || status === "running";

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>
                {sessionName ? `Importing ${sessionName}` : titleFallback}
            </DialogTitle>

            <DialogContent>
                <Stack spacing={2}>

                    {/* ── Status header ── */}
                    {status === "scheduling" && (
                        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                            <CircularProgress size={22} />
                            <Typography>Scheduling import job…</Typography>
                        </Stack>
                    )}

                    {status === "success" && (
                        <Alert icon={<CheckCircle size={20} />} severity="success">
                            Import completed successfully.
                        </Alert>
                    )}

                    {status === "error" && (
                        <Alert icon={<ErrorIcon />} severity="error">
                            {error || "Import failed"}
                        </Alert>
                    )}

                    {/* ── Meta row: status chip + elapsed ── */}
                    {summary && (
                        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                            <Chip
                                label={summary.derived_status}
                                color={statusColor(summary.derived_status)}
                                size="small"
                            />
                            {elapsedMs > 0 && (
                                <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                                    <Clock size={14} />
                                    <Typography variant="caption" color="text.secondary">
                                        {formatElapsed(elapsedMs)}
                                    </Typography>
                                </Stack>
                            )}
                            {summary.totals.failed > 0 && (
                                <Chip
                                    label={`${summary.totals.failed} failed`}
                                    color="error"
                                    size="small"
                                    variant="outlined"
                                />
                            )}
                        </Stack>
                    )}

                    {/* ── Overall progress bar (weighted by step cost when available) ── */}
                    {isRunningOrSuccess && (
                        <Box>
                            <Stack direction="row" sx={{ mb: 0.5, justifyContent: "space-between" }}>
                                <Tooltip
                                    title={
                                        overallWorkTotal > 0
                                            ? `Weighted by step cost: ${steps.map(s => `${s.label} ×${s.weight}`).join(", ")}`
                                            : "Fallback: completed tasks / total tasks (importer does not emit per-step counters)"
                                    }
                                    placement="top"
                                >
                                    <Typography variant="caption" color="text.secondary" sx={{ cursor: "help" }}>
                                        Overall
                                    </Typography>
                                </Tooltip>
                                <Typography variant="caption" color="text.secondary">
                                    {overallPct}%{overallImages > 0 ? ` · ${overallImages} images` : ""}
                                </Typography>
                            </Stack>
                            <LinearProgress
                                variant={overallWorkTotal > 0 || (summary?.total_tasks ?? 0) > 0 ? "determinate" : "indeterminate"}
                                value={overallPct}
                                sx={{ height: 8, borderRadius: 4 }}
                                color={status === "success" ? "success" : "primary"}
                            />
                        </Box>
                    )}

                    {/* ── Pipeline steps table ── only when the importer emits counters */}
                    {stepCounts && (
                        <>
                            <Divider />
                            <Typography variant="subtitle2" color="text.secondary">
                                Pipeline steps
                            </Typography>
                            <Table size="small" sx={{ "& td, & th": { border: 0 } }}>
                                <TableBody>
                                    {steps.map((s) => {
                                        const total = stepTotals?.[s.key] ?? (s.pluginCategory ? 0 : overallImages);
                                        const cat = s.pluginCategory ? summary?.by_category?.[s.pluginCategory] : undefined;
                                        return (
                                            <StepRow
                                                key={s.key}
                                                icon={s.icon}
                                                label={s.label}
                                                done={stepCounts?.[s.key] ?? 0}
                                                total={total}
                                                color={s.color}
                                                tooltip={s.pluginCategory
                                                    ? `Top bar: dispatched to ${s.label} plugin. Thin bar: results returned.`
                                                    : undefined}
                                                completed={cat?.completed}
                                                failed={cat?.failed}
                                            />
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </>
                    )}

                    {/* ── Job ID (collapsed, low emphasis) ── */}
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
                        Updating…
                    </Button>
                ) : (
                    <Button onClick={onClose} size="small">Close</Button>
                )}
            </DialogActions>
        </Dialog>
    );
};
