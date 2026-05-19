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
import { useEffect, useMemo, useState } from "react";
import { CheckCircle, Clock, RefreshCcw } from "lucide-react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";

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

    const selectedDir = useMemo(
        () => selectedFile ? directoryName(selectedFile) : null,
        [selectedFile],
    );

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

    useEffect(() => {
        const timeout = window.setTimeout(() => {
            fetchDirectory("/gpfs");
        }, 0);
        return () => window.clearTimeout(timeout);
    }, []);

    useEffect(() => {
        if (!jobId || !["scheduling", "running"].includes(importStatus)) return;

        let cancelled = false;
        const poll = async () => {
            try {
                const response = await apiClient.get<ImportSummary>(
                    `/export/job/${jobId}/summary`,
                );
                if (cancelled) return;
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
                if (cancelled) return;
                const axiosError = err as AxiosError<{ detail?: string }>;
                if (axiosError.response?.status !== 404) {
                    setImportStatus("error");
                    setImportError(errorMessage(err, "Could not read import progress"));
                }
            }
        };

        poll();
        const interval = window.setInterval(poll, 2000);
        return () => {
            cancelled = true;
            window.clearInterval(interval);
        };
    }, [jobId, importStatus]);

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
                            <Typography variant="caption" color="text.secondary">
                                Job: {jobId}
                            </Typography>
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
                                                <TableCell align="right">{counts.pending ?? 0}</TableCell>
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
