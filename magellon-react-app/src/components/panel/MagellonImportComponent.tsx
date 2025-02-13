import { Typography, List, ListItem, ListItemIcon, ListItemText, Box } from "@mui/material";
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { useState, useEffect } from "react";
import { settings } from "../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;

type FileItem = {
    id: number;
    name: string;
    is_directory: boolean;
    path: string;
    size?: number;
    created_at: string;
    updated_at: string;
};

export const MagellonImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedFile, setSelectedFile] = useState<string | null>(null);

    const fetchDirectory = async (path: string) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `${BASE_URL}/files/browse?path=${encodeURIComponent(path)}`
            );
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setFiles(data);
            setCurrentPath(path);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDirectory(currentPath);
    }, []);

    const handleItemDoubleClick = (item: FileItem) => {
        if (item.is_directory) {
            fetchDirectory(item.path);
        }
    };

    const handleItemClick = (item: FileItem) => {
        if (!item.is_directory && item.name.endsWith('.json')) {
            setSelectedFile(item.path);
            console.log('Selected session file:', item);
        }
    };

    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Import Data from Magellan Microscope Sessions
            </Typography>

            <Typography variant="body2" color="textSecondary" gutterBottom>
                If you are using Docker, please select a directory from the MAGELLON_GPFS_PATH that was configured during installation in the .env file.
                Select a session file (session.json) and click the import button
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
                Current path: {currentPath}
            </Typography>

            {currentPath !== "/gpfs" && (
                <Typography
                    variant="body2"
                    sx={{
                        cursor: 'pointer',
                        color: 'primary.main',
                        mb: 2
                    }}
                    onClick={() => {
                        const parentPath = currentPath.split('/').slice(0, -1).join('/') || "/gpfs";
                        fetchDirectory(parentPath);
                    }}
                >
                    ← Go back to parent directory
                </Typography>
            )}

            {error && (
                <Typography color="error" sx={{ mt: 1 }} gutterBottom>
                    Error: {error}
                </Typography>
            )}

            <Box sx={{
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                minHeight: 400,
                maxHeight: 600,
                overflow: 'auto',
                mt: 2
            }}>
                {loading ? (
                    <Typography sx={{ p: 2 }}>Loading...</Typography>
                ) : (
                    <List>
                        {files.map((item) => (
                            <ListItem
                                key={item.path}
                                onClick={() => handleItemClick(item)}
                                onDoubleClick={() => handleItemDoubleClick(item)}
                                sx={{
                                    cursor: 'pointer',
                                    '&:hover': {
                                        backgroundColor: 'action.hover',
                                    },
                                    bgcolor: selectedFile === item.path ? 'action.selected' : 'inherit'
                                }}
                            >
                                <ListItemIcon>
                                    {item.is_directory ?
                                        <FolderIcon color="primary" /> :
                                        <InsertDriveFileIcon />}
                                </ListItemIcon>
                                <ListItemText
                                    primary={item.name}
                                    secondary={item.is_directory ? 'Directory' : `File - ${item.size ? `${(item.size / 1024).toFixed(2)} KB` : 'Size unknown'}`}
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Box>

            {selectedFile && (
                <Typography sx={{ mt: 2 }} color="primary">
                    Selected file: {selectedFile}
                </Typography>
            )}
        </div>
    );
};