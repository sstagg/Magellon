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
    Paper,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Chip
} from "@mui/material";
import FolderIcon from '@mui/icons-material/Folder';
import ErrorIcon from '@mui/icons-material/Error';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import { useState, useEffect } from "react";
import { settings } from "../../core/settings.ts";
import Button from "@mui/material/Button";
import { CheckCircleIcon } from "lucide-react";
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

type SerialEMDefaults = {
    pixel_size: number;
    acceleration_voltage: number;
    spherical_aberration: number;
    amplitude_contrast: number;
    magnification: number;
    detector_pixel_size: number;
    rot_gain?: number;
    flip_gain?: number;
}

type SerialEMFileType = 'mrc' | 'st' | 'mdoc' | 'nav';

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


export const SerialEMImportComponent = () => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    const [selectedDirectory, setSelectedDirectory] = useState<string | null>(null);
    const [importStatus, setImportStatus] = useState<ImportStatus>('idle');
    const [importError, setImportError] = useState<string | null>(null);
    const [validationStatus, setValidationStatus] = useState<'none' | 'validating' | 'valid' | 'invalid'>('none');
    const [detectedFiles, setDetectedFiles] = useState<{ [key: string]: number }>({
        'mrc': 0,
        'st': 0,
        'mdoc': 0,
        'nav': 0
    });

    // SerialEM specific state variables
    const [serialemDirPath, setSerialemDirPath] = useState<string>("");
    const [magellonProjectName, setMagellonProjectName] = useState<string>("");
    const [magellonSessionName, setMagellonSessionName] = useState<string>("");
    const [dataType, setDataType] = useState<'single-particle' | 'tomography'>('single-particle');
    const [frameType, setFrameType] = useState<'gain-corrected' | 'raw'>('gain-corrected');
    const [defaults, setDefaults] = useState<SerialEMDefaults>({
        pixel_size: 1.0,
        acceleration_voltage: 300,
        spherical_aberration: 2.7,
        amplitude_contrast: 0.1,
        magnification: 50000,
        detector_pixel_size: 5.0,
        rot_gain:0,
        flip_gain:0
    });

    const validateSerialEMDirectory = async (dirPath: string) => {
        setValidationStatus('validating');
        try {
            const response = await apiClient.get('/export/validate-serialem-directory', {
                params: { source_dir: dirPath }
            });

            // Update detected files count
            if (response.data.file_counts) {
                setDetectedFiles(response.data.file_counts);
            }

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
            setSelectedDirectory(item.path);
            setSerialemDirPath(item.path);
            // Validate and detect SerialEM files
            // await validateSerialEMDirectory(item.path);
        }
    };

    const handleImport = async () => {
        if (!selectedDirectory) return;

        // Validate required fields
        if (!serialemDirPath || !magellonProjectName || !magellonSessionName) {
            setError("Please fill in all required fields");
            return;
        }

        // Validate numeric fields
        if (defaults.pixel_size <= 0 || defaults.detector_pixel_size <= 0) {
            setError("Pixel sizes must be greater than 0");
            return;
        }

        if (defaults.magnification <= 0) {
            setError("Magnification must be greater than 0");
            return;
        }

        setImportStatus('processing');
        setImportError(null);

        try {
            await apiClient.post('/export/serialem-import', {
                target_directory: serialemDirPath,
                serial_em_dir_path: selectedDirectory,
                magellon_project_name: magellonProjectName,
                magellon_session_name: magellonSessionName,
                session_name: magellonSessionName,
                data_type: dataType,
                frame_type: frameType,
                default_data: {
                    pixel_size: defaults.pixel_size,
                    acceleration_voltage: defaults.acceleration_voltage,
                    spherical_aberration: defaults.spherical_aberration,
                    amplitude_contrast: defaults.amplitude_contrast,
                    magnification: defaults.magnification,
                    detector_pixel_size: defaults.detector_pixel_size,
                    rot_gain: defaults.rot_gain,
                    flip_gain: defaults.flip_gain
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
    const handleDefaultsChange = (field: keyof SerialEMDefaults, value: string) => {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
            setDefaults({
                ...defaults,
                [field]: numValue
            });
        } else if (value === '') {
            setDefaults({
                ...defaults,
                [field]: 0
            });
        }
    };

    const getFileIcon = (fileName: string) => {
        const extension = fileName.split('.').pop()?.toLowerCase();
        if (extension === 'mrc' || extension === 'st') {
            return <ImageIcon color="action" />;
        } else if (extension === 'mdoc' || extension === 'nav') {
            return <DescriptionIcon color="action" />;
        }
        return <InsertDriveFileIcon />;
    };

    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Import Data from SerialEM Sessions
            </Typography>

            <Typography variant="body2" color="textSecondary" gutterBottom>
                If you are using Docker, please select a directory from the MAGELLON_GPFS_PATH that was configured during installation in the .env file.
                Select a SerialEM data directory containing MRC/ST files and their metadata.
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
            {/* Folder Structure Validation Guide */}
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

    {/* settings */}
    <div className="flex items-center gap-2 mt-2">
      <span className="text-yellow-500">📁</span>
      <span>settings</span>
    </div>
    <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
      <div className="flex items-center gap-2">
        <span className="text-gray-500">📄</span>
        <span>settings.txt</span>
      </div>
    </div>

    {/* medium_mag (same level as settings) */}
    <div className="flex items-center gap-2 mt-2">
      <span className="text-yellow-500">📁</span>
      <span>medium_mag</span>
    </div>
    <div className="ml-6 mt-1 border-l border-gray-200 pl-3">
      <div className="flex items-center gap-2">
        <span className="text-gray-500">📄</span>
        <span>MMM.mrc</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-gray-500">📄</span>
        <span>MMM.mrc.mdoc</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-gray-500">📄</span>
        <span>.....</span>
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
                                        getFileIcon(item.name)}
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
                        SerialEM Import Configuration
                    </Typography>

                    {/* {validationStatus === 'valid' && ( */}
                        <Box sx={{ mb: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                Detected SerialEM Files:
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {detectedFiles.mrc > 0 && (
                                    <Chip label={`${detectedFiles.mrc} MRC files`} size="small" color="primary" />
                                )}
                                {detectedFiles.st > 0 && (
                                    <Chip label={`${detectedFiles.st} ST files`} size="small" color="primary" />
                                )}
                                {detectedFiles.mdoc > 0 && (
                                    <Chip label={`${detectedFiles.mdoc} MDOC files`} size="small" color="info" />
                                )}
                                {detectedFiles.nav > 0 && (
                                    <Chip label={`${detectedFiles.nav} NAV files`} size="small" color="info" />
                                )}
                            </Box>
                        </Box>
                    {/* )} */}

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
                                label="SerialEM Directory Path"
                                value={serialemDirPath}
                                onChange={(e) => setSerialemDirPath(e.target.value)}
                                variant="outlined"
                                margin="normal"
                                helperText="Full path to the SerialEM data directory"
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

                        <Grid item xs={12} md={6}>
                            <FormControl fullWidth margin="normal">
                                <InputLabel>Data Type</InputLabel>
                                <Select
                                    value={dataType}
                                    label="Data Type"
                                    onChange={(e) => setDataType(e.target.value as 'single-particle' | 'tomography')}
                                >
                                    <MenuItem value="single-particle">Single Particle</MenuItem>
                                    <MenuItem value="tomography">Tomography</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <FormControl fullWidth margin="normal">
                                <InputLabel>Frame Type</InputLabel>
                                <Select
                                    value={frameType}
                                    label="Frame Type"
                                    onChange={(e) => setFrameType(e.target.value as 'gain-corrected' | 'raw')}
                                >
                                    <MenuItem value="gain-corrected">Gain Corrected</MenuItem>
                                    <MenuItem value="raw">Raw Frames</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12}>
                            <Typography variant="subtitle1" sx={{ mt: 2 }}>
                                Microscope Parameters
                            </Typography>
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Pixel Size (Å/pixel)"
                                value={defaults.pixel_size}
                                onChange={(e) => handleDefaultsChange('pixel_size', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.01, min: 0.01 }}
                                helperText="Calibrated pixel size at specimen level"
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Acceleration Voltage (kV)"
                                value={defaults.acceleration_voltage}
                                onChange={(e) => handleDefaultsChange('acceleration_voltage', e.target.value)}
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
                                value={defaults.spherical_aberration}
                                onChange={(e) => handleDefaultsChange('spherical_aberration', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.1, min: 0 }}
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Amplitude Contrast"
                                value={defaults.amplitude_contrast}
                                onChange={(e) => handleDefaultsChange('amplitude_contrast', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.01, min: 0, max: 1 }}
                                helperText="Typical: 0.07-0.1 for cryo-EM"
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Magnification"
                                value={defaults.magnification}
                                onChange={(e) => handleDefaultsChange('magnification', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 1000, min: 1000 }}
                                helperText="Nominal magnification"
                            />
                        </Grid>

                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                required
                                type="number"
                                label="Detector Pixel Size (μm)"
                                value={defaults.detector_pixel_size}
                                onChange={(e) => handleDefaultsChange('detector_pixel_size', e.target.value)}
                                variant="outlined"
                                margin="normal"
                                inputProps={{ step: 0.1, min: 0.1 }}
                                helperText="Physical detector pixel size"
                            />
                        </Grid>
<Grid item xs={12} md={4}>
  <TextField
    fullWidth
    required
    select
    label="Rot Gain"
    value={defaults.rot_gain}
    onChange={(e) =>
      handleDefaultsChange("rot_gain", String(e.target.value))
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
    value={defaults.flip_gain}
    onChange={(e) =>
      handleDefaultsChange("flip_gain", String(e.target.value))
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
                                // disabled={importStatus === 'processing' || validationStatus === 'invalid'}
                                size="large"
                            >
                                Import SerialEM Data
                            </Button>
                            {/* {validationStatus === 'invalid' && ( */}
                                {/* <Typography variant="caption" color="error" sx={{ ml: 2 }}>
                                    No valid SerialEM files found in selected directory
                                </Typography> */}
                            {/* )} */}
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
                                Processing SerialEM import... Please wait
                            </Typography>
                            <Typography variant="caption" color="textSecondary">
                                This may take a few minutes for large datasets
                            </Typography>
                        </>
                    )}
                    {importStatus === 'success' && (
                        <>
                            <CheckCircleIcon color="success" sx={{ fontSize: 48 }} />
                            <Typography>
                                SerialEM data imported successfully
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
                                <Typography variant="body2" color="error" align="center">
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