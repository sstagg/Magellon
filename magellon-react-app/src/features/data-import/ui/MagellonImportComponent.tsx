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
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import type { ChipProps } from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import ErrorIcon from "@mui/icons-material/Error";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import ImageIcon from "@mui/icons-material/Image";
import BarChartIcon from "@mui/icons-material/BarChart";
import BlurOnIcon from "@mui/icons-material/BlurOn";
import VideocamIcon from "@mui/icons-material/Videocam";
import type { AxiosError } from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle, Clock, RefreshCcw } from "lucide-react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useSocket } from "../../../shared/lib/useSocket.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

type FileItem = {
    id: number;
    name: string;
    is_directory: boolean;
    path: string;
    size?: number;
    created_at: string;
    updated_at: string;
};

type ImportStatus = "idle" | "scheduling" | "running" | "success" | "error";

type StepCounts = {
    png: number;
    fft: number;
    ctf: number;
    motioncor: number;
};

type ImportSummary = {
    job_id: string;
    name: string;
    status: string;
    derived_status: string;
    total_tasks: number;
    terminal_tasks: number;
    totals: Record<string, number>;
    by_category: Record<string, Record<string, number>>;
    created_at?: string | null;
};

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

const statusColor = (status: string): ChipProps["color"] => {
    if (status === "completed") return "success";
    if (status === "failed") return "error";
    if (status === "cancelled") return "warning";
    return "info";
};

const directoryName = (path: string) => path.replace(/\\/g, "/").split("/").slice(0, -1).join("/");

const errorMessage = (err: unknown, fallback: string) => {
    const axiosError = err as AxiosError<{ detail?: string }>;
    return axiosError.response?.data?.detail || axiosError.message || fallback;
};

const formatElapsed = (ms: number) => {
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return `${m}m ${s % 60}s`;
};

// ── Pipeline step row ────────────────────────────────────────────────────────

type StepRowProps = {
    icon: React.ReactNode;
    label: string;
    done: number;
    total: number;
    tooltip?: string;
    color?: "primary" | "secondary" | "info" | "success" | "warning";
    // Plugin steps only — completion data from image_job_task rows after
    // plugin results land via StepEventJobStateProjector / TaskOutputProcessor.
    // Omitted for local steps where done==completed.
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

// ── Component ────────────────────────────────────────────────────────────────

export const MagellonImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [importStatus, setImportStatus] = useState<ImportStatus>("idle");
    const [importError, setImportError] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [summary, setSummary] = useState<ImportSummary | null>(null);
    const [stepCounts, setStepCounts] = useState<StepCounts | null>(null);
    const [stepTotals, setStepTotals] = useState<StepCounts | null>(null);
    const [elapsedMs, setElapsedMs] = useState<number>(0);
    const { emit: socketEmit, on: socketOn } = useSocket();
    const importStatusRef = useRef(importStatus);

    const selectedDir = useMemo(
        () => selectedFile ? directoryName(selectedFile) : null,
        [selectedFile],
    );

    useEffect(() => {
        importStatusRef.current = importStatus;
    }, [importStatus]);

    const validateDirectory = async (dirPath: string) => {
        try {
            await apiClient.get("/export/validate-magellon-directory", {
                params: { source_dir: dirPath },
            });
            return true;
        } catch (err: unknown) {
            setError(errorMessage(err, "Validation failed"));
            return false;
        }
    };

    const fetchDirectory = async (path: string) => {
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.get("/web/files/browse", { params: { path } });
            setFiles(response.data);
            setCurrentPath(path);
        } catch (err: unknown) {
            const axiosError = err as AxiosError<{ detail?: string }>;
            if (axiosError.response?.status === 401) {
                setError("Please login to browse files");
            } else if (axiosError.response?.status === 403) {
                setError("You do not have permission to browse this directory");
            } else {
                setError(errorMessage(err, "An error occurred"));
            }
        } finally {
            setLoading(false);
        }
    };

    const fetchSummary = useCallback(async (id: string) => {
        try {
            const response = await apiClient.get<ImportSummary>(`/export/job/${id}/summary`);
            const next = response.data;
            setSummary(next);
            if (terminalStatuses.has(next.derived_status)) {
                setImportStatus(next.derived_status === "completed" ? "success" : "error");
                if (next.derived_status !== "completed") {
                    setImportError(`Import ${next.derived_status}`);
                }
            } else {
                setImportStatus("running");
            }
        } catch (err: unknown) {
            const axiosError = err as AxiosError<{ detail?: string }>;
            if (axiosError.response?.status !== 404) {
                setImportStatus("error");
                setImportError(errorMessage(err, "Could not read import progress"));
            }
        }
    }, []);

    useEffect(() => {
        const timeout = window.setTimeout(() => fetchDirectory("/gpfs"), 0);
        return () => window.clearTimeout(timeout);
    }, []);

    // On mount, resume monitoring if an import is already running.
    useEffect(() => {
        apiClient.get<{ job_id: string; name?: string }>("/export/jobs/active")
            .then(({ data }) => {
                // Guard: only resume actual import jobs — the endpoint may return
                // non-import jobs (HoleDetection, etc.) that share the same status
                // filter on the backend.  Import jobs are always named "Import: …".
                if (!data.name?.startsWith("Import:")) return;
                setJobId(data.job_id);
                // Let fetchSummary resolve the real status (running / success / error)
                // rather than always forcing "running" before the first poll.
                return fetchSummary(data.job_id);
            })
            .catch(() => {});
    }, [fetchSummary]);

    // Socket.IO: join the job room and listen for real-time progress events.
    useEffect(() => {
        if (!jobId) return;
        socketEmit("join_job_room", { job_id: jobId });
        const off = socketOn("import_progress", (data: {
            job_id: string;
            event?: string;
            step_counts?: StepCounts;
            step_totals?: StepCounts;
            elapsed_ms?: number;
        }) => {
            if (data?.job_id === jobId && ["scheduling", "running"].includes(importStatusRef.current)) {
                fetchSummary(jobId);
                if (data.step_counts) setStepCounts(data.step_counts);
                if (data.step_totals) setStepTotals(data.step_totals);
                if (data.elapsed_ms !== undefined) setElapsedMs(data.elapsed_ms);
            }
        });
        return () => {
            off();
            socketEmit("leave_job_room", { job_id: jobId });
        };
    }, [jobId, socketEmit, socketOn, fetchSummary]);

    // Polling fallback every 5 s.
    useEffect(() => {
        if (!jobId || !["scheduling", "running"].includes(importStatus)) return;
        const timeout = window.setTimeout(() => fetchSummary(jobId), 0);
        const interval = window.setInterval(() => fetchSummary(jobId), 5000);
        return () => {
            window.clearTimeout(timeout);
            window.clearInterval(interval);
        };
    }, [jobId, importStatus, fetchSummary]);

    const handleItemClick = async (item: FileItem) => {
        if (!item.is_directory && item.name === "session.json") {
            const dirPath = directoryName(item.path);
            if (await validateDirectory(dirPath)) setSelectedFile(item.path);
        }
    };

    const handleItemDoubleClick = (item: FileItem) => {
        if (item.is_directory) fetchDirectory(item.path);
    };

    const handleImport = async () => {
        if (!selectedDir) return;
        setImportStatus("scheduling");
        setImportError(null);
        setSummary(null);
        setJobId(null);
        setStepCounts(null);
        setStepTotals(null);
        setElapsedMs(0);

        try {
            const response = await apiClient.post("/export/magellon-import", {
                source_dir: selectedDir,
                replace_existing: true,
            });
            setJobId(response.data.job_id);
            setImportStatus("running");
        } catch (err: unknown) {
            setImportStatus("error");
            setImportError(errorMessage(err, "Import failed"));
        }
    };

    const handleCloseDialog = () => {
        if (["scheduling", "running"].includes(importStatus)) return;
        setImportStatus("idle");
        setImportError(null);
        setJobId(null);
        setSummary(null);
        setStepCounts(null);
        setStepTotals(null);
        setElapsedMs(0);
    };

    const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/gpfs";

    // Per-step compute cost — used to weight overall progress so MotionCor
    // (slow GPU work) doesn't get drowned out by PNG/FFT (cheap local work)
    // when the bar advances. Tune as plugin timings change.
    const STEP_WEIGHTS = { png: 1, fft: 1, ctf: 2, motioncor: 7 } as const;
    const overallWorkTotal = (Object.keys(STEP_WEIGHTS) as Array<keyof typeof STEP_WEIGHTS>)
        .reduce((acc, k) => acc + STEP_WEIGHTS[k] * (stepTotals?.[k] ?? 0), 0);
    const overallWorkDone = (Object.keys(STEP_WEIGHTS) as Array<keyof typeof STEP_WEIGHTS>)
        .reduce((acc, k) => acc + STEP_WEIGHTS[k] * (stepCounts?.[k] ?? 0), 0);
    const overallPct = overallWorkTotal > 0
        ? Math.min(100, Math.round((overallWorkDone / overallWorkTotal) * 100))
        : 0;

    // Image count for context only — distinct from work progress.
    const overallImages = summary?.total_tasks ?? 0;

    // Derive session name from summary or job name
    const sessionName = summary?.name?.replace(/^Import:\s*/i, "") ?? null;

    return (
        <Box>
            <Typography variant="h6" gutterBottom>
                Import Data from Magellon Microscope Sessions
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                Select a Magellon project folder under the configured GPFS root, choose
                its session.json file, then start the import.
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                Current path: {currentPath}
            </Typography>

            {currentPath !== "/gpfs" && (
                <Button size="small" onClick={() => fetchDirectory(parentPath)} sx={{ mb: 2 }}>
                    Back to parent
                </Button>
            )}

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <Alert severity="info" sx={{ mb: 2 }}>
                Required structure: session.json beside home/original, home/frames, and
                home/gains. Output is written under the configured Magellon home directory.
            </Alert>

            <Box
                sx={{
                    border: 1,
                    borderColor: "divider",
                    borderRadius: 1,
                    minHeight: 360,
                    maxHeight: 560,
                    overflow: "auto",
                }}
            >
                {loading ? (
                    <Stack sx={{ p: 3, alignItems: "center" }}>
                        <CircularProgress size={28} />
                    </Stack>
                ) : (
                    <List dense>
                        {files.map((item) => (
                            <ListItem
                                key={item.path}
                                data-testid={`import-file-${item.name}`}
                                onClick={() => handleItemClick(item)}
                                onDoubleClick={() => handleItemDoubleClick(item)}
                                sx={{
                                    cursor: "pointer",
                                    "&:hover": { backgroundColor: "action.hover" },
                                    bgcolor: selectedFile === item.path ? "action.selected" : "inherit",
                                }}
                            >
                                <ListItemIcon>
                                    {item.is_directory ? (
                                        <FolderIcon color="primary" />
                                    ) : (
                                        <InsertDriveFileIcon />
                                    )}
                                </ListItemIcon>
                                <ListItemText
                                    primary={item.name}
                                    secondary={
                                        item.is_directory
                                            ? "Directory"
                                            : `File - ${item.size ? `${(item.size / 1024).toFixed(2)} KB` : "Size unknown"}`
                                    }
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Box>

            {selectedFile && (
                <Stack spacing={1.5} sx={{ mt: 2, alignItems: "flex-start" }}>
                    <Typography color="primary">Selected file: {selectedFile}</Typography>
                    <Button
                        data-testid="magellon-import-start"
                        variant="contained"
                        onClick={handleImport}
                        disabled={["scheduling", "running"].includes(importStatus)}
                    >
                        Import Data
                    </Button>
                </Stack>
            )}

            <Dialog
                open={importStatus !== "idle"}
                onClose={handleCloseDialog}
                fullWidth
                maxWidth="sm"
            >
                <DialogTitle>
                    {sessionName ? `Importing ${sessionName}` : "Magellon import"}
                </DialogTitle>

                <DialogContent>
                    <Stack spacing={2}>

                        {/* ── Status header ── */}
                        {importStatus === "scheduling" && (
                            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                                <CircularProgress size={22} />
                                <Typography>Scheduling import job…</Typography>
                            </Stack>
                        )}

                        {importStatus === "success" && (
                            <Alert icon={<CheckCircle size={20} />} severity="success">
                                Import completed successfully.
                            </Alert>
                        )}

                        {importStatus === "error" && (
                            <Alert icon={<ErrorIcon />} severity="error">
                                {importError || "Import failed"}
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

                        {/* ── Overall progress bar (weighted by step cost) ── */}
                        {(importStatus === "running" || importStatus === "success") && (
                            <Box>
                                <Stack direction="row" sx={{ mb: 0.5, justifyContent: "space-between" }}>
                                    <Tooltip
                                        title={`Weighted by step cost: PNG ×${STEP_WEIGHTS.png}, FFT ×${STEP_WEIGHTS.fft}, CTF ×${STEP_WEIGHTS.ctf}, MotionCor ×${STEP_WEIGHTS.motioncor}`}
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
                                    variant={overallWorkTotal > 0 ? "determinate" : "indeterminate"}
                                    value={overallPct}
                                    sx={{ height: 8, borderRadius: 4 }}
                                    color={importStatus === "success" ? "success" : "primary"}
                                />
                            </Box>
                        )}

                        {/* ── Pipeline steps table ── */}
                        {(stepCounts || summary) && (
                            <>
                                <Divider />
                                <Typography variant="subtitle2" color="text.secondary">
                                    Pipeline steps
                                </Typography>
                                <Table size="small" sx={{ "& td, & th": { border: 0 } }}>
                                    <TableBody>
                                        <StepRow
                                            icon={<ImageIcon fontSize="small" />}
                                            label="PNG Conversion"
                                            done={stepCounts?.png ?? 0}
                                            total={stepTotals?.png ?? overallImages}
                                            color="primary"
                                        />
                                        <StepRow
                                            icon={<BarChartIcon fontSize="small" />}
                                            label="FFT Computation"
                                            done={stepCounts?.fft ?? 0}
                                            total={stepTotals?.fft ?? overallImages}
                                            color="info"
                                        />
                                        <StepRow
                                            icon={<BlurOnIcon fontSize="small" />}
                                            label="CTF Estimation"
                                            done={stepCounts?.ctf ?? 0}
                                            total={stepTotals?.ctf ?? 0}
                                            tooltip="Top bar: dispatched to CTF plugin. Thin bar: results returned (image_meta_data written)."
                                            color="secondary"
                                            completed={summary?.by_category?.ctf?.completed ?? 0}
                                            failed={summary?.by_category?.ctf?.failed ?? 0}
                                        />
                                        <StepRow
                                            icon={<VideocamIcon fontSize="small" />}
                                            label="Motion Correction"
                                            done={stepCounts?.motioncor ?? 0}
                                            total={stepTotals?.motioncor ?? 0}
                                            tooltip="Top bar: dispatched to MotionCor plugin. Thin bar: results returned (image_meta_data written)."
                                            color="warning"
                                            completed={summary?.by_category?.motioncor?.completed ?? 0}
                                            failed={summary?.by_category?.motioncor?.failed ?? 0}
                                        />
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
                    {["scheduling", "running"].includes(importStatus) ? (
                        <Button startIcon={<RefreshCcw size={16} />} disabled size="small">
                            Updating…
                        </Button>
                    ) : (
                        <Button onClick={handleCloseDialog} size="small">Close</Button>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};
