import {
    Typography,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    MenuItem,
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
import getAxiosClient from '../../core/AxiosClient.ts';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;
const exportUrl: string = BASE_URL.replace(/\/web$/, '/export');
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

type DefaultData = {
    pixel_size: number;
    acceleration_voltage: number;
    spherical_aberration: number;
    flip_gain: number;
    rot_gain: number;
}

type ImportStatus = 'idle' | 'processing' | 'success' | 'error';

const rotGainOptions = [
  { value: 0, label: "0 — No rotation (default)" },
  { value: 1, label: "1 — Rotate 90° counter-clockwise" },
  { value: 2, label: "2 — Rotate 180°" },
  { value: 3, label: "3 — Rotate 270° counter-clockwise" },
];

const flipGainOptions = [
  { value: 0, label: "0 — No flipping (default)" },
  { value: 1, label: "1 — Flip upside down (horizontal axis)" },
  { value: 2, label: "2 — Flip left–right (vertical axis)" },
];


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
        spherical_aberration: 2.7,
        rot_gain:0,
        flip_gain:0
    });

    const validateDirectory = async (dirPath: string) => {
        setValidationStatus('validating');
        try {
            await apiClient.get('/export/validate-epu-directory', {
                params: { source_dir: dirPath }
            });
            setValidationStatus('valid');
            return true;
        } catch (err: any) {
            setValidationStatus('invalid');
            setError(err.response?.data?.detail || err.message || 'Validation failed');
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
            await apiClient.post('/export/epu-import', {
                target_directory: epuDirPath,
                epu_dir_path: selectedDirectory,
                magellon_project_name: magellonProjectName,
                magellon_session_name: magellonSessionName,
                default_data: {
                    pixel_size: defaultData.pixel_size,
                    acceleration_voltage: defaultData.acceleration_voltage,
                    spherical_aberration: defaultData.spherical_aberration,
                    rot_gain: defaultData.rot_gain,
                    flip_gain: defaultData.flip_gain
                }
            });

            setImportStatus('success');
        } catch (err: any) {
            setImportStatus('error');
            setImportError(err.response?.data?.detail || err.message || 'Import failed');
        }
    };

    const fetchDirectory = async (path: string) => {
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.get('/web/files/browse', {
                params: { path }
            });
            setFiles(response.data);
            setCurrentPath(path);
        } catch (err: any) {
            if (err.response?.status === 401) {
                setError('Please login to browse files');
            } else if (err.response?.status === 403) {
                setError('You do not have permission to browse this directory');
            } else {
                setError(err.response?.data?.detail || err.message || 'An error occurred');
            }
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
    <div className="flex items-center gap-2 mt-1">
      <span className="text-yellow-500">📁</span>
      <span>defects(Optional)</span>
    </div>
    <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
      <div className="flex items-center gap-2">
        <span className="text-gray-500">📄</span>
        <span>defects.txt</span>
      </div>
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
                                    secondary={item.is_directory ? 'Directory' : `File - ${item.size ? `${(item.size / 1024)?.toFixed(2)} KB` : 'Size unknown'}`}
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
                      <Grid item xs={12} md={4}>
                        <TextField
                          fullWidth
                          required
                          select
                          label="Rot Gain"
                          value={defaultData.rot_gain}
                          onChange={(e) =>
                            handleDefaultDataChange("rot_gain", e.target.value)
                          }
                          variant="outlined"
                          margin="normal"
                        >
                          {rotGainOptions.map((opt) => (
                            <MenuItem key={opt.value} value={String(opt.value)}>
                              {opt.label}
                            </MenuItem>
                          ))}
                        </TextField>
                      </Grid>
                      
                      
                      <Grid item xs={12} md={4}>
                        <TextField
                          fullWidth
                          required
                          select
                          label="Flip Gain"
                          value={defaultData.flip_gain}
                          onChange={(e) =>
                            handleDefaultDataChange("flip_gain", e.target.value)
                          }
                          variant="outlined"
                          margin="normal"
                        >
                          {flipGainOptions.map((opt) => (
                            <MenuItem key={opt.value} value={String(opt.value)}>
                              {opt.label}
                            </MenuItem>
                          ))}
                        </TextField>
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