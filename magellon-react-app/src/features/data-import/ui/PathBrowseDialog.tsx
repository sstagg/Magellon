import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import { useEffect, useState } from "react";
import getAxiosClient from "../../../shared/api/AxiosClient.ts";
import { apiErrorMessage } from "../../../shared/api/apiError.ts";
import { settings } from "../../../shared/config/settings.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

type FileItem = { name: string; is_directory: boolean; path: string; size?: number };

const parentOf = (path: string) => path.split("/").slice(0, -1).join("/") || "/gpfs";

/** Browse the research storage (/gpfs on the server) and choose a folder or a file.
 *  Double-click a folder to open it. Paths are the server's /gpfs/... form. */
export const PathBrowseDialog = ({ open, mode, title, startPath, onClose, onChoose }: {
    open: boolean;
    mode: "folder" | "file";
    title: string;
    startPath: string;
    onClose: () => void;
    onChoose: (path: string) => void;
}) => {
    const [path, setPath] = useState(startPath);
    const [items, setItems] = useState<FileItem[]>([]);
    const [selected, setSelected] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = async (target: string) => {
        setLoading(true);
        setError(null);
        setSelected(null);
        try {
            const response = await apiClient.get("/web/files/browse", { params: { path: target } });
            const list = (response.data as FileItem[]).slice()
                .sort((a, b) => Number(b.is_directory) - Number(a.is_directory) || a.name.localeCompare(b.name));
            setItems(list);
            setPath(target);
        } catch (err) {
            // A typed path that doesn't exist: start from the root instead.
            if (target !== "/gpfs") return load("/gpfs");
            setError(apiErrorMessage(err, "Could not open this folder"));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) load(startPath || "/gpfs");
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    const choice = mode === "folder" ? (selected ?? path) : selected;

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {mode === "folder"
                        ? "Double-click a folder to open it. Choose the open folder, or click one to choose it."
                        : "Double-click a folder to open it, then click the file."}
                </Typography>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                    <Button size="small" disabled={path === "/gpfs" || loading} onClick={() => load(parentOf(path))}>
                        Up
                    </Button>
                    <Typography variant="body2" sx={{ wordBreak: "break-all" }}>{path}</Typography>
                </Box>
                {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
                <Box sx={{ border: 1, borderColor: "divider", borderRadius: 1, height: 420, overflow: "auto" }}>
                    {loading ? (
                        <Box sx={{ p: 3, textAlign: "center" }}><CircularProgress size={28} /></Box>
                    ) : (
                        <List dense>
                            {items.map((item) => {
                                const choosable = item.is_directory === (mode === "folder");
                                return (
                                    <ListItemButton
                                        key={item.path}
                                        selected={selected === item.path}
                                        onClick={() => choosable && setSelected(item.path)}
                                        onDoubleClick={() => item.is_directory && load(item.path)}
                                    >
                                        <ListItemIcon>
                                            {item.is_directory ? <FolderIcon color="primary" /> : <InsertDriveFileIcon />}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={item.name}
                                            secondary={item.is_directory ? null
                                                : item.size ? `${(item.size / 1048576).toFixed(1)} MB` : null}
                                        />
                                    </ListItemButton>
                                );
                            })}
                            {!items.length && <Typography sx={{ p: 2 }} color="text.secondary">Empty folder</Typography>}
                        </List>
                    )}
                </Box>
            </DialogContent>
            <DialogActions>
                <Typography variant="body2" color="text.secondary" sx={{ flex: 1, pl: 2, wordBreak: "break-all" }}>
                    {choice ? `Choose: ${choice}` : "Click a file to choose it"}
                </Typography>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" disabled={!choice || choice === "/gpfs"}
                        onClick={() => { if (choice) { onChoose(choice); onClose(); } }}>
                    {mode === "folder" ? "Choose folder" : "Choose file"}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
