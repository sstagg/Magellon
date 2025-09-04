import {
    Typography,
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
    FormControlLabel,
    Switch,
    Alert
} from "@mui/material";
import ErrorIcon from '@mui/icons-material/Error';
import { useState, useEffect } from "react";
import { settings } from "../../core/settings.ts";
import Button from "@mui/material/Button";
import { CheckCircleIcon } from "lucide-react";
import { SelectChangeEvent } from '@mui/material';

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL;
const exportUrl: string = BASE_URL.replace(/\/web$/, '/export');

type FileCopyMode = 'symlink' | 'copy' | 'none';

type RelionExportRequest = {
    session_name: string;
    output_directory: string;
    magnification: number;
    has_movie: boolean;
    file_copy_mode: FileCopyMode;
    source_mrc_directory: string;
};

type ExportStatus = 'idle' | 'processing' | 'success' | 'error';

type SessionDto = {
    Oid: string;
    name: string;
};

export const RelionExportComponent = () => {
    const [exportStatus, setExportStatus] = useState<ExportStatus>('idle');
    const [exportError, setExportError] = useState<string | null>(null);
    const [exportResult, setExportResult] = useState<any>(null);
    const [sessions, setSessions] = useState<SessionDto[]>([]);
    const [loadingSessions, setLoadingSessions] = useState(false);

    // Form state
    const [formData, setFormData] = useState<RelionExportRequest>({
        session_name: '',
        output_directory: '',
        magnification: 0,
        has_movie: true,
        file_copy_mode: 'symlink',
        source_mrc_directory: 'images'
    });

    // Validation state
    const [errors, setErrors] = useState<{[key: string]: string}>({});

    // Fetch available sessions
    const fetchSessions = async () => {
        setLoadingSessions(true);
        try {
            const response = await fetch(`${BASE_URL}/sessions`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setSessions(data);
        } catch (err) {
            console.error('Failed to fetch sessions:', err);
        } finally {
            setLoadingSessions(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    // Validation function
    const validateForm = (): boolean => {
        const newErrors: {[key: string]: string} = {};

        if (!formData.session_name) {
            newErrors.session_name = "Please select a session";
        }

        if (!formData.output_directory.trim()) {
            newErrors.output_directory = "Output directory is required";
        }

        if (formData.magnification < 0) {
            newErrors.magnification = "Magnification must be 0 or greater";
        }

        if (!formData.source_mrc_directory.trim()) {
            newErrors.source_mrc_directory = "Source MRC directory is required";
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    // Handle form field changes
    const handleInputChange = (field: keyof RelionExportRequest, value: any) => {
        setFormData({
            ...formData,
            [field]: value
        });

        // Clear error for this field if it exists
        if (errors[field]) {
            setErrors({
                ...errors,
                [field]: ''
            });
        }
    };

    // Handle select changes
    const handleSelectChange = (event: SelectChangeEvent<string>) => {
        const { name, value } = event.target;
        handleInputChange(name as keyof RelionExportRequest, value);
    };

    // Handle export
    const handleExport = async () => {
        if (!validateForm()) {
            return;
        }

        setExportStatus('processing');
        setExportError(null);
        setExportResult(null);

        try {
            const response = await fetch(`${exportUrl}/generate-relion-starfile`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Export failed');
            }

            const result = await response.json();
            setExportResult(result);
            setExportStatus('success');
        } catch (err) {
            setExportStatus('error');
            setExportError(err instanceof Error ? err.message : 'Export failed');
        }
    };

    const handleCloseDialog = () => {
        setExportStatus('idle');
        setExportError(null);
        setExportResult(null);
    };

    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Export RELION Star File
            </Typography>

            <Typography variant="body2" color="textSecondary" gutterBottom>
                Generate a RELION star file from database session data. This will query the database for session and image data,
                apply filters for magnification and movie presence, extract CTF parameters from metadata, and generate a
                RELION-compatible star file with optional MRC file copying/symlinking.
            </Typography>

            <Paper sx={{ p: 3, mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                    Export Configuration
                </Typography>

                <Grid container spacing={3}>
                    {/* Session Selection */}
                    <Grid item xs={12} md={6}>
                        <FormControl fullWidth variant="outlined" error={!!errors.session_name}>
                            <InputLabel>Session *</InputLabel>
                            <Select
                                value={formData.session_name}
                                onChange={(e) => handleInputChange('session_name', e.target.value)}
                                label="Session *"
                                disabled={loadingSessions}
                            >
                                {loadingSessions ? (
                                    <MenuItem disabled>Loading sessions...</MenuItem>
                                ) : (
                                    sessions.map((session) => (
                                        <MenuItem key={session.Oid} value={session.name}>
                                            {session.name}
                                        </MenuItem>
                                    ))
                                )}
                            </Select>
                            {errors.session_name && (
                                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                                    {errors.session_name}
                                </Typography>
                            )}
                        </FormControl>
                    </Grid>

                    {/* Output Directory */}
                    <Grid item xs={12} md={6}>
                        <TextField
                            fullWidth
                            required
                            label="Output Directory"
                            value={formData.output_directory}
                            onChange={(e) => handleInputChange('output_directory', e.target.value)}
                            variant="outlined"
                            error={!!errors.output_directory}
                            helperText={errors.output_directory || "Directory where the star file will be generated"}
                        />
                    </Grid>

                    {/* Magnification */}
                    <Grid item xs={12} md={6}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Magnification Filter"
                            value={formData.magnification}
                            onChange={(e) => handleInputChange('magnification', parseInt(e.target.value) || 0)}
                            variant="outlined"
                            error={!!errors.magnification}
                            helperText={errors.magnification || "Filter images by magnification (0 = no filter)"}
                            inputProps={{ min: 0 }}
                        />
                    </Grid>

                    {/* Source MRC Directory */}
                    <Grid item xs={12} md={6}>
                        <TextField
                            fullWidth
                            required
                            label="Source MRC Directory"
                            value={formData.source_mrc_directory}
                            onChange={(e) => handleInputChange('source_mrc_directory', e.target.value)}
                            variant="outlined"
                            error={!!errors.source_mrc_directory}
                            helperText={errors.source_mrc_directory || "Directory containing MRC files"}
                        />
                    </Grid>

                    {/* File Copy Mode */}
                    <Grid item xs={12} md={6}>
                        <FormControl fullWidth variant="outlined">
                            <InputLabel>File Copy Mode</InputLabel>
                            <Select
                                value={formData.file_copy_mode}
                                onChange={(e) => handleInputChange('file_copy_mode', e.target.value as FileCopyMode)}
                                label="File Copy Mode"
                            >
                                <MenuItem value="symlink">Symlink</MenuItem>
                                <MenuItem value="copy">Copy</MenuItem>
                                <MenuItem value="none">None</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>

                    {/* Has Movie Filter */}
                    <Grid item xs={12} md={6}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={formData.has_movie}
                                    onChange={(e) => handleInputChange('has_movie', e.target.checked)}
                                />
                            }
                            label="Filter for images with movies"
                        />
                    </Grid>

                    {/* Export Button */}
                    <Grid item xs={12} sx={{ mt: 2 }}>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleExport}
                            disabled={exportStatus === 'processing'}
                            size="large"
                        >
                            {exportStatus === 'processing' ? 'Generating...' : 'Generate RELION Star File'}
                        </Button>
                    </Grid>
                </Grid>

                {/* File Copy Mode Information */}
                <Box sx={{ mt: 3 }}>
                    <Alert severity="info">
                        <Typography variant="body2">
                            <strong>File Copy Modes:</strong><br/>
                            • <strong>Symlink:</strong> Creates symbolic links to original MRC files (recommended, saves space)<br/>
                            • <strong>Copy:</strong> Creates full copies of MRC files (requires more disk space)<br/>
                            • <strong>None:</strong> Only generates star file without copying/linking MRC files
                        </Typography>
                    </Alert>
                </Box>
            </Paper>

            {/* Export Status Dialog */}
            <Dialog
                open={exportStatus !== 'idle'}
                onClose={exportStatus !== 'processing' ? handleCloseDialog : undefined}
                maxWidth="md"
                fullWidth
            >
                <DialogContent sx={{
                    minWidth: 300,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 2,
                    p: 4
                }}>
                    {exportStatus === 'processing' && (
                        <>
                            <CircularProgress size={48} />
                            <Typography>
                                Generating RELION star file... Please wait
                            </Typography>
                            <Typography variant="body2" color="textSecondary" align="center">
                                This may take a few minutes depending on the size of your dataset
                            </Typography>
                        </>
                    )}

                    {exportStatus === 'success' && (
                        <>
                            <CheckCircleIcon color="success" sx={{ fontSize: 48 }} />
                            <Typography variant="h6">
                                Export completed successfully!
                            </Typography>

                            {exportResult && (
                                <Box sx={{ mt: 2, width: '100%' }}>
                                    <Typography variant="subtitle2" gutterBottom>
                                        Export Details:
                                    </Typography>
                                    <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                                        <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                                            {JSON.stringify(exportResult, null, 2)}
                                        </Typography>
                                    </Paper>
                                </Box>
                            )}

                            <Button onClick={handleCloseDialog} sx={{ mt: 2 }}>
                                Close
                            </Button>
                        </>
                    )}

                    {exportStatus === 'error' && (
                        <>
                            <ErrorIcon color="error" sx={{ fontSize: 48 }} />
                            <Typography variant="h6" color="error">
                                Export failed
                            </Typography>
                            {exportError && (
                                <Alert severity="error" sx={{ mt: 2, width: '100%' }}>
                                    <Typography variant="body2">
                                        {exportError}
                                    </Typography>
                                </Alert>
                            )}
                            <Button onClick={handleCloseDialog} sx={{ mt: 2 }}>
                                Close
                            </Button>
                        </>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
};