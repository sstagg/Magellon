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
    LinearProgress,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Typography,
} from "@mui/material";
import type { ChipProps } from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import ErrorIcon from "@mui/icons-material/Error";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
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
    const [stepTotal, setStepTotal] = useState<number>(0);
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
            const response = await apiClient.get("/web/files/browse", {
                params: { path },
            });
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
        const timeout = window.setTimeout(() => {
            fetchDirectory("/gpfs");
        }, 0);
        return () => window.clearTimeout(timeout);
    }, []);

    // On mount, check if an import is already running (e.g. after page navigation)
    // and auto-resume progress monitoring so the dialog shows live data.
    useEffect(() => {
        apiClient.get<{ job_id: string }>("/export/jobs/active")
            .then(({ data }) => {
                setJobId(data.job_id);
                setImportStatus("running");
            })
            .catch(() => {
                // 404 = no active job; ignore
            });
    }, []);

    // Socket.IO: join the job room and listen for real-time progress events.
    useEffect(() => {
        if (!jobId) return;
        socketEmit("join_job_room", { job_id: jobId });
        const off = socketOn("import_progress", (data: {
            job_id: string;
            event?: string;
            step_counts?: StepCounts;
            total?: number;
            elapsed_ms?: number;
        }) => {
            if (data?.job_id === jobId && ["scheduling", "running"].includes(importStatusRef.current)) {
                fetchSummary(jobId);
                if (data.step_counts) setStepCounts(data.step_counts);
                if (data.total) setStepTotal(data.total);
                if (data.elapsed_ms !== undefined) setElapsedMs(data.elapsed_ms);
            }
        });
        return () => {
            off();
            socketEmit("leave_job_room", { job_id: jobId });
        };
    }, [jobId, socketEmit, socketOn, fetchSummary]);

    // Polling fallback — still runs every 5 s in case a socket event is missed.
    useEffect(() => {
        if (!jobId || !["scheduling", "running"].includes(importStatus)) return;

        const timeout = window.setTimeout(() => {
            fetchSummary(jobId);
        }, 0);
        const interval = window.setInterval(() => fetchSummary(jobId), 5000);
        return () => {
            window.clearTimeout(timeout);
            window.clearInterval(interval);
        };
    }, [jobId, importStatus, fetchSummary]);

    const handleItemClick = async (item: FileItem) => {
        if (!item.is_directory && item.name === "session.json") {
            const dirPath = directoryName(item.path);
            if (await validateDirectory(dirPath)) {
                setSelectedFile(item.path);
            }
        }
    };

    const handleItemDoubleClick = (item: FileItem) => {
        if (item.is_directory) {
            fetchDirectory(item.path);
        }
    };

    const handleImport = async () => {
        if (!selectedDir) return;
        setImportStatus("scheduling");
        setImportError(null);
        setSummary(null);
        setJobId(null);
        setStepCounts(null);
        setStepTotal(0);
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
        setStepTotal(0);
        setElapsedMs(0);
    };

    const formatElapsed = (ms: number) => {
        const s = Math.floor(ms / 1000);
        if (s < 60) return `${s}s`;
        const m = Math.floor(s / 60);
        return `${m}m ${s % 60}s`;
    };

    const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/gpfs";
    const progress = summary?.total_tasks
        ? Math.round((summary.terminal_tasks / summary.total_tasks) * 100)
        : 0;
    const categoryRows = Object.entries(summary?.by_category ?? {});

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
                <DialogTitle>Magellon import</DialogTitle>
                <DialogContent>
                    <Stack spacing={2}>
                        {importStatus === "scheduling" && (
                            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                                <CircularProgress size={24} />
                                <Typography>Scheduling import job...</Typography>
                            </Stack>
                        )}

                        {importStatus === "running" && (
                            <>
                                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                                    <Clock size={22} />
                                    <Typography>Import is running</Typography>
                                </Stack>
                                <LinearProgress variant={summary?.total_tasks ? "determinate" : "indeterminate"} value={progress} />
                            </>
                        )}

                        {importStatus === "success" && (
                            <Alert icon={<CheckCircle size={20} />} severity="success">
                                Import completed.
                            </Alert>
                        )}

                        {importStatus === "error" && (
                            <Alert icon={<ErrorIcon />} severity="error">
                                {importError || "Import failed"}
                            </Alert>
                        )}

                        {jobId && (
                            <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                                <Typography variant="caption" color="text.secondary">
                                    Job: {jobId}
                                </Typography>
                                {elapsedMs > 0 && (
                                    <Typography variant="caption" color="text.secondary">
                                        Elapsed: {formatElapsed(elapsedMs)}
                                    </Typography>
                                )}
                            </Stack>
                        )}

                        {stepCounts && (
                            <Box>
                                <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
                                    Per-step ({stepTotal} images)
                                </Typography>
                                <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
                                    <Chip label={`PNG: ${stepCounts.png}`} size="small" variant="outlined" />
                                    <Chip label={`FFT: ${stepCounts.fft}`} size="small" variant="outlined" />
                                    <Chip label={`CTF: ${stepCounts.ctf}`} size="small" variant="outlined" color="primary" />
                                    <Chip label={`MotionCor: ${stepCounts.motioncor}`} size="small" variant="outlined" color="secondary" />
                                </Stack>
                            </Box>
                        )}

                        {summary && (
                            <Box>
                                <Stack
                                    direction="row"
                                    spacing={1}
                                    useFlexGap
                                    sx={{ mb: 1, flexWrap: "wrap" }}
                                >
                                    <Chip label={summary.derived_status} color={statusColor(summary.derived_status)} size="small" />
                                    <Chip label={`${summary.terminal_tasks}/${summary.total_tasks} terminal`} size="small" />
                                    <Chip label={`${summary.totals.completed ?? 0} done`} color="success" size="small" />
                                    <Chip label={`${summary.totals.failed ?? 0} error`} color="error" size="small" />
                                </Stack>

                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Category</TableCell>
                                            <TableCell align="right">Pending</TableCell>
                                            <TableCell align="right">Running</TableCell>
                                            <TableCell align="right">Done</TableCell>
                                            <TableCell align="right">Error</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {categoryRows.map(([category, counts]) => (
                                            <TableRow key={category}>
                                                <TableCell>{category}</TableCell>
                                                <TableCell align="right">{(counts.queued ?? 0) + (counts.pending ?? 0)}</TableCell>
                                                <TableCell align="right">
                                                    {(counts.running ?? 0) + (counts.processing ?? 0)}
                                                </TableCell>
                                                <TableCell align="right">{counts.completed ?? 0}</TableCell>
                                                <TableCell align="right">{counts.failed ?? 0}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </Box>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    {["scheduling", "running"].includes(importStatus) && (
                        <Button startIcon={<RefreshCcw size={16} />} disabled>
                            Updating
                        </Button>
                    )}
                    {!["scheduling", "running"].includes(importStatus) && (
                        <Button onClick={handleCloseDialog}>Close</Button>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};
