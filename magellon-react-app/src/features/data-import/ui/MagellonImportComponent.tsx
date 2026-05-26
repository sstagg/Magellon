import {
    Alert,
    Box,
    Button,
    CircularProgress,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Stack,
    Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import type { AxiosError } from "axios";
import { useEffect, useMemo, useState } from "react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { settings } from "../../../shared/config/settings.ts";
import { useImportJobProgress } from "../lib/useImportJobProgress.ts";
import { ImportProgressDialog } from "./ImportProgressDialog.tsx";

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

const directoryName = (path: string) => path.replace(/\\/g, "/").split("/").slice(0, -1).join("/");

const errorMessage = (err: unknown, fallback: string) => {
    const axiosError = err as AxiosError<{ detail?: string }>;
    return axiosError.response?.data?.detail || axiosError.message || fallback;
};

// ── Component ────────────────────────────────────────────────────────────────

export const MagellonImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const progress = useImportJobProgress();

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

    useEffect(() => {
        const timeout = window.setTimeout(() => fetchDirectory("/gpfs"), 0);
        return () => window.clearTimeout(timeout);
    }, []);

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
        progress.scheduling();
        try {
            const response = await apiClient.post("/export/magellon-import", {
                source_dir: selectedDir,
                replace_existing: true,
            });
            progress.start(response.data.job_id);
        } catch (err: unknown) {
            progress.fail(errorMessage(err, "Import failed"));
        }
    };

    const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/gpfs";

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
                        disabled={["scheduling", "running"].includes(progress.status)}
                    >
                        Import Data
                    </Button>
                </Stack>
            )}

            <ImportProgressDialog
                open={progress.status !== "idle"}
                onClose={progress.reset}
                status={progress.status}
                error={progress.error}
                jobId={progress.jobId}
                summary={progress.summary}
                stepCounts={progress.stepCounts}
                stepTotals={progress.stepTotals}
                elapsedMs={progress.elapsedMs}
                sessionName={progress.sessionName}
                titleFallback="Magellon import"
            />
        </Box>
    );
};
