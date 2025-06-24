import {
    Typography,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Box,
    Dialog,
    DialogContent,
    CircularProgress,
    TextField,
    Grid,
    Paper
} from "@mui/material";
import FolderIcon from '@mui/icons-material/Folder';
import ErrorIcon from '@mui/icons-material/Error';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { useState, useEffect } from "react";
import { settings } from "../../core/settings.ts";
import Button from "@mui/material/Button";
import {CheckCircleIcon} from "lucide-react";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;
const exportUrl: string = BASE_URL.replace(/\/web$/, '/export');

type FileItem = {
    id: number;
    name: string;
    is_directory: boolean;
    path: string;
    size?: number;
    created_at: string;
    updated_at: string;
};

type DefaultData = {
    pixel_size: number;
    acceleration_voltage: number;
    spherical_aberration: number;
}

type ImportStatus = 'idle' | 'processing' | 'success' | 'error';

export const EpuImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedDirectory, setSelectedDirectory] = useState<string | null>(null);
    const [importStatus, setImportStatus] = useState<ImportStatus>('idle');
    const [importError, setImportError] = useState<string | null>(null);
    const [validationStatus, setValidationStatus] = useState<'none' | 'validating' | 'valid' | 'invalid'>('none');

    // New state variables for the additional fields
    const [epuDirPath, setEpuDirPath] = useState<string>("");
    const [magellonProjectName, setMagellonProjectName] = useState<string>("");
    const [magellonSessionName, setMagellonSessionName] = useState<string>("");
    const [defaultData, setDefaultData] = useState<DefaultData>({
        pixel_size: 0,
        acceleration_voltage: 300,
        spherical_aberration: 2.7
    });

    const validateDirectory = async (dirPath: string) => {
        setValidationStatus('validating');
        try {
            const response = await fetch(`${exportUrl}/validate-epu-directory?source_dir=${encodeURIComponent(dirPath)}`);
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
        if (item.is_directory) {
            // if (await validateDirectory(item.path)) {
            setSelectedDirectory(item.path);
            setEpuDirPath(item.path); // Auto-fill EPU directory path when selecting a directory
            // }
        }
    };

    const handleImport = async () => {
        if (!selectedDirectory) return;

        // Validate required fields
        if (!epuDirPath || !magellonProjectName || !magellonSessionName) {
            setError("Please fill in all required fields");
            return;
        }

        // Validate numeric fields
        if (defaultData.pixel_size <= 0) {
            setError("Pixel size must be greater than 0");
            return;
        }

        setImportStatus('processing');
        setImportError(null);

        try {
            const response = await fetch(`${exportUrl}/epu-import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    target_directory: epuDirPath,
                    epu_dir_path: selectedDirectory,
                    magellon_project_name: magellonProjectName,
                    magellon_session_name: magellonSessionName,
                    default_data: {
                        pixel_size: defaultData.pixel_size,
                        acceleration_voltage: defaultData.acceleration_voltage,
                        spherical_aberration: defaultData.spherical_aberration
                    }
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

    // Handle changes to default data fields
    const handleDefaultDataChange = (field: keyof DefaultData, value: string) => {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
            setDefaultData({
                ...defaultData,
                [field]: numValue
            });
        } else if (value === '') {
            setDefaultData({
                ...defaultData,
                [field]: 0
            });
        }
    };

    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Import Data from EPU Sessions
            </Typography>

            <Typography variant="body2" color="textSecondary" gutterBottom>
                If you are using Docker, please select a directory from the MAGELLON_GPFS_PATH that was configured during installation in the .env file.
                Select an EPU directory and fill in the required information.
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
                                    bgcolor: selectedDirectory === item.path ? 'action.selected' : 'inherit'
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

            {selectedDirectory && (
                <Paper sx={{ p: 3, mt: 3 }}>
                    <Typography variant="h6" gutterBottom>
                        Import Configuration
                    </Typography>

                    <Grid container spacing={3}>
                        <Grid item xs={12}>
                            <TextField
                                fullWidth
                                label="Selected Directory (Target)"
                                value={selectedDirectory}
                                disabled
                                variant="outlined"
                                margin="normal"
                            />
                        </Grid>

                        <Grid item xs={12}>
                            <TextField
                                fullWidth
                                required
                                label="EPU Directory Path"
                                value={epuDirPath}
                                onChange={(e) => setEpuDirPath(e.target.value)}
                                variant="outlined"
                                margin="normal"
                                helperText="Full path to the EPU directory"
                            />
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <TextField
                                fullWidth
                                required
                                label="Magellon Project Name"
                                value={magellonProjectName}
                                onChange={(e) => setMagellonProjectName(e.target.value)}
                                variant="outlined"
                                margin="normal"
                            />
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <TextField
                                fullWidth
                                required
                                label="Magellon Session Name"
                                value={magellonSessionName}
                                onChange={(e) => setMagellonSessionName(e.target.value)}
                                variant="outlined"
                                margin="normal"
                            />
                        </Grid>

                        <Grid item xs={12}>
                            <Typography variant="subtitle1" sx={{ mt: 2 }}>
                                Default Data
                            </Typography>
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Pixel Size (Å)"
                                value={defaultData.pixel_size}
                                onChange={(e) => handleDefaultDataChange('pixel_size', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.01, min: 0.01 }}
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Acceleration Voltage (kV)"
                                value={defaultData.acceleration_voltage}
                                onChange={(e) => handleDefaultDataChange('acceleration_voltage', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 10, min: 100 }}
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Spherical Aberration (mm)"
                                value={defaultData.spherical_aberration}
                                onChange={(e) => handleDefaultDataChange('spherical_aberration', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.1, min: 0 }}
                            />
                        </Grid>

                        <Grid item xs={12} sx={{ mt: 2 }}>
                            <Button
                                variant="contained"
                                color="primary"
                                onClick={handleImport}
                                disabled={importStatus === 'processing'}
                                size="large"
                            >
                                Import EPU Data
                            </Button>
                        </Grid>
                    </Grid>
                </Paper>
            )}

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