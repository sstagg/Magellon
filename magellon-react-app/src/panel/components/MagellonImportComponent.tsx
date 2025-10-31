import {
    Typography,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Box,
    Dialog,
    DialogContent,
    CircularProgress
} from "@mui/material";
import FolderIcon from '@mui/icons-material/Folder';
import ErrorIcon from '@mui/icons-material/Error';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { useState, useEffect } from "react";
import { settings } from "../../core/settings.ts";
import Button from "@mui/material/Button";
import {CheckCircleIcon} from "lucide-react";

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

type ImportStatus = 'idle' | 'processing' | 'success' | 'error';

export const MagellonImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [importStatus, setImportStatus] = useState<ImportStatus>('idle');
    const [importError, setImportError] = useState<string | null>(null);
    const [validationStatus, setValidationStatus] = useState<'none' | 'validating' | 'valid' | 'invalid'>('none');

    const exportUrl: string = BASE_URL.replace(/\/web$/, '/export');


    const validateDirectory = async (dirPath: string) => {
        setValidationStatus('validating');
        try {
            const response = await fetch(`${exportUrl}/validate-magellon-directory?source_dir=${encodeURIComponent(dirPath)}`);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail);
            }
            setValidationStatus('valid');
            return true;
        } catch (err) {
            setValidationStatus('invalid');
            setError(err instanceof Error ? err.message : 'Validation failed');
            return false;
        }
    };
    const handleItemClick = async (item: FileItem) => {
        if (!item.is_directory && item.name.endsWith('.json')) {
            const dirPath = item.path.split(/[\/\\]/).slice(0, -1).join('/');
            if (await validateDirectory(dirPath)) {
                setSelectedFile(item.path);
            }
        }
    };

    const handleImport = async () => {
        if (!selectedFile) return;
        const selectedDir = selectedFile.split(/[\/\\]/).slice(0, -1).join('/');
        // Get the directory path of the selected file
        // const selectedDir = selectedFile.substring(0, selectedFile.lastIndexOf('/'));

        setImportStatus('processing');
        setImportError(null);

        try {

            const response = await fetch(`${exportUrl}/magellon-import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    source_dir: selectedDir
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Import failed');
            }

            setImportStatus('success');
        } catch (err) {
            setImportStatus('error');
            setImportError(err instanceof Error ? err.message : 'Import failed');
        }
    };


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


    const handleCloseDialog = () => {
        setImportStatus('idle');
        setImportError(null);
    };
    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Import Data from Magellon Microscope Sessions
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
            <Box
  sx={{
    p: 2,
    mb: 3,
    borderRadius: 2,
    bgcolor: 'background.paper',
    boxShadow: 1,
  }}
>
  <Typography variant="h6" gutterBottom>
    Required Folder Structure
  </Typography>

  <div className="text-sm text-gray-700 ml-2">
    <div className="flex items-center gap-2">
      <span className="text-yellow-500">📁</span>
      <span className="font-medium">Main Folder (Upload this)</span>
    </div>

    <div className="ml-6 mt-1 border-l border-gray-300 pl-3">
      {/* home */}
      <div className="flex items-center gap-2 mt-1">
        <span className="text-yellow-500">📁</span>
        <span>home</span>
      </div>

      <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
        {/* gains */}
        <div className="flex items-center gap-2 mt-1">
          <span className="text-yellow-500">📁</span>
          <span>gains</span>
        </div>
        <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">📄</span>
            <span>gain.mrc</span>
          </div>
        </div>

        {/* defects (optional) */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-yellow-500">📁</span>
          <span>defects (Optional)</span>
        </div>
        <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">📄</span>
            <span>defects.txt</span>
          </div>
        </div>

        {/* frames */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-yellow-500">📁</span>
          <span>frames</span>
        </div>
        <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">📄</span>
            <span>example_frame.mrc</span>
          </div>
        </div>

        {/* original */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-yellow-500">📁</span>
          <span>original</span>
        </div>
        <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">📄</span>
            <span>raw_image.mrc</span>
          </div>
        </div>
      </div>

      {/* session.json */}
      <div className="flex items-center gap-2 mt-3">
        <span className="text-gray-500">📄</span>
        <span>session.json</span>
      </div>
    </div>
  </div>

  <Typography
    variant="caption"
    color="text.secondary"
    sx={{ mt: 2, display: 'block' }}
  >
    ⚠️ Ensure all required subfolders exist before uploading.
  </Typography>
</Box>

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
                                    secondary={item.is_directory ? 'Directory' : `File - ${item.size ? `${(item.size / 1024)?.toFixed(2)} KB` : 'Size unknown'}`}
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Box>

            {selectedFile && (
                <>
                    <Typography sx={{ mt: 2 }} color="primary">
                        Selected file: {selectedFile}
                    </Typography>
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={handleImport}
                        disabled={importStatus === 'processing'}
                    >
                        Import Data
                    </Button>
                </>


            )}
            {/* Status Dialog */}
            <Dialog
                open={importStatus !== 'idle'}
                onClose={importStatus !== 'processing' ? handleCloseDialog : undefined}
            >
                <DialogContent sx={{
                    minWidth: 300,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 2,
                    p: 4
                }}>
                    {importStatus === 'processing' && (
                        <>
                            <CircularProgress size={48} />
                            <Typography>
                                Processing import... Please wait
                            </Typography>
                        </>
                    )}
                    {importStatus === 'success' && (
                        <>
                            <CheckCircleIcon color="success" sx={{ fontSize: 48 }} />
                            <Typography>
                                Import completed successfully
                            </Typography>
                            <Button onClick={handleCloseDialog}>
                                Close
                            </Button>
                        </>
                    )}
                    {importStatus === 'error' && (
                        <>
                            <ErrorIcon color="error" sx={{ fontSize: 48 }} />
                            <Typography color="error">
                                Import failed
                            </Typography>
                            {importError && (
                                <Typography variant="body2" color="error">
                                    {importError}
                                </Typography>
                            )}
                            <Button onClick={handleCloseDialog}>
                                Close
                            </Button>
                        </>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
};