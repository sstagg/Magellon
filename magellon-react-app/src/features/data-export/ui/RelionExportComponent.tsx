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
    Alert,
    Checkbox,
    Chip,
    Divider,
    ListItemText,
    OutlinedInput,
    Stack
} from "@mui/material";
import ErrorIcon from '@mui/icons-material/Error';
import { useState, useEffect, useCallback } from "react";
import { settings } from "../../../shared/config/settings.ts";
import Button from "@mui/material/Button";
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { Play, RefreshCcw } from "lucide-react";
import { useParticleExportPipelineProgress } from "../lib/useParticleExportPipelineProgress.ts";
import { ParticleExportPipelineProgressDialog } from "./ParticleExportPipelineProgressDialog.tsx";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

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

type PickingRunSummary = {
    name: string;
    image_count: number;
    particle_count: number;
    class_counts: Record<string, number>;
    sample_image_name?: string | null;
    updated_at?: string | null;
};

type PipelineFormData = {
    picking_run_name: string;
    output_directory: string;
    include_classes: string[];
    box_size: number;
    edge_width: number;
    apix: string;
    num_classes: number;
    num_presentations: number;
    align_iters: number;
    threads: number;
    can_threads: number;
    compute_backend: 'cpu' | 'torch-auto' | 'torch-cuda' | 'torch-mps' | 'torch-cpu';
    max_particles: string;
    invert: boolean;
    write_aligned_stack: boolean;
};

const PARTICLE_CLASS_OPTIONS = [
    { id: '1', label: 'Good' },
    { id: '2', label: 'Edge' },
    { id: '3', label: 'Contamination' },
    { id: '4', label: 'Uncertain' },
];

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

    const [pickingRuns, setPickingRuns] = useState<PickingRunSummary[]>([]);
    const [loadingPickingRuns, setLoadingPickingRuns] = useState(false);
    const [pipelineError, setPipelineError] = useState<string | null>(null);
    const [pipelineForm, setPipelineForm] = useState<PipelineFormData>({
        picking_run_name: '',
        output_directory: '',
        include_classes: ['1'],
        box_size: 256,
        edge_width: 2,
        apix: '',
        num_classes: 50,
        num_presentations: 50000,
        align_iters: 2,
        threads: 4,
        can_threads: 4,
        compute_backend: 'torch-auto',
        max_particles: '',
        invert: false,
        write_aligned_stack: false,
    });
    const pipelineProgress = useParticleExportPipelineProgress();

    // Validation state
    const [errors, setErrors] = useState<{[key: string]: string}>({});

    // Fetch available sessions
    const fetchSessions = async () => {
        setLoadingSessions(true);
        try {
            const response = await apiClient.get('/web/sessions');
            setSessions(response.data);
        } catch (err: any) {
            console.error('Failed to fetch sessions:', err.response?.data?.detail || err.message);
        } finally {
            setLoadingSessions(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    const fetchPickingRuns = useCallback(async (sessionName: string) => {
        if (!sessionName) {
            setPickingRuns([]);
            return;
        }
        setLoadingPickingRuns(true);
        setPipelineError(null);
        try {
            const response = await apiClient.get<PickingRunSummary[]>(
                '/export/particle-pipeline/picking-runs',
                { params: { session_name: sessionName } },
            );
            setPickingRuns(response.data);
            setPipelineForm((prev) => ({
                ...prev,
                picking_run_name: response.data.some((run) => run.name === prev.picking_run_name)
                    ? prev.picking_run_name
                    : (response.data[0]?.name ?? ''),
            }));
        } catch (err: any) {
            setPickingRuns([]);
            setPipelineError(err.response?.data?.detail || err.message || 'Failed to load particle-picking runs');
        } finally {
            setLoadingPickingRuns(false);
        }
    }, []);

    useEffect(() => {
        fetchPickingRuns(formData.session_name);
    }, [formData.session_name, fetchPickingRuns]);

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
        if (field === 'session_name') {
            setPipelineForm((prev) => ({ ...prev, picking_run_name: '' }));
        }

        // Clear error for this field if it exists
        if (errors[field]) {
            setErrors({
                ...errors,
                [field]: ''
            });
        }
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
            const response = await apiClient.post('/export/generate-relion-starfile', formData);
            setExportResult(response.data);
            setExportStatus('success');
        } catch (err: any) {
            setExportStatus('error');
            setExportError(err.response?.data?.detail || err.message || 'Export failed');
        }
    };

    const handlePipelineChange = (field: keyof PipelineFormData, value: any) => {
        setPipelineForm((prev) => ({
            ...prev,
            [field]: value,
        }));
        setPipelineError(null);
    };

    const handleStartParticlePipeline = async () => {
        if (!formData.session_name) {
            setPipelineError('Please select a session first');
            return;
        }
        if (!pipelineForm.picking_run_name) {
            setPipelineError('Please select a particle-picking run');
            return;
        }
        if (pipelineForm.include_classes.length === 0) {
            setPipelineError('Select at least one particle class to extract');
            return;
        }

        pipelineProgress.scheduling();
        setPipelineError(null);
        try {
            const payload = {
                session_name: formData.session_name,
                picking_run_name: pipelineForm.picking_run_name,
                output_directory: pipelineForm.output_directory.trim() || null,
                include_classes: pipelineForm.include_classes,
                box_size: pipelineForm.box_size,
                edge_width: pipelineForm.edge_width,
                apix: pipelineForm.apix.trim() ? Number(pipelineForm.apix) : null,
                num_classes: pipelineForm.num_classes,
                num_presentations: pipelineForm.num_presentations,
                align_iters: pipelineForm.align_iters,
                threads: pipelineForm.threads,
                can_threads: pipelineForm.can_threads,
                compute_backend: pipelineForm.compute_backend,
                max_particles: pipelineForm.max_particles.trim() ? Number(pipelineForm.max_particles) : null,
                invert: pipelineForm.invert,
                write_aligned_stack: pipelineForm.write_aligned_stack,
            };
            const response = await apiClient.post('/export/particle-pipeline/start', payload);
            pipelineProgress.start(response.data.job_id);
        } catch (err: any) {
            const message = err.response?.data?.detail || err.message || 'Particle export pipeline failed to start';
            setPipelineError(message);
            pipelineProgress.fail(message);
        }
    };

    const handleCloseDialog = () => {
        setExportStatus('idle');
        setExportError(null);
        setExportResult(null);
    };

    const selectedPickingRun = pickingRuns.find((run) => run.name === pipelineForm.picking_run_name);
    const pipelineBusy = pipelineProgress.status === 'scheduling' || pipelineProgress.status === 'running';

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
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
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
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
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
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Magnification Filter"
                            value={formData.magnification}
                            onChange={(e) => handleInputChange('magnification', parseInt(e.target.value) || 0)}
                            variant="outlined"
                            error={!!errors.magnification}
                            helperText={errors.magnification || "Filter images by magnification (0 = no filter)"}
                            slotProps={{
                                htmlInput: { min: 0 }
                            }}
                        />
                    </Grid>

                    {/* Source MRC Directory */}
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
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
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
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
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
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
                    <Grid sx={{ mt: 2 }} size={12}>
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

            <Paper sx={{ p: 3, mt: 3 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', mb: 2 }}>
                    <Box>
                        <Typography variant="h6" gutterBottom>
                            Particle Extraction and 2D Classification
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                            Select a saved picking run, box the particles with Stack Maker, then classify the stack with CAN.
                        </Typography>
                    </Box>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshCcw size={16} />}
                        onClick={() => fetchPickingRuns(formData.session_name)}
                        disabled={!formData.session_name || loadingPickingRuns}
                        size="small"
                        sx={{ alignSelf: { xs: 'flex-start', md: 'center' } }}
                    >
                        Refresh Runs
                    </Button>
                </Stack>

                {pipelineError && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {pipelineError}
                    </Alert>
                )}

                <Grid container spacing={3}>
                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
                        <FormControl fullWidth disabled={!formData.session_name || loadingPickingRuns}>
                            <InputLabel>Particle-picking run</InputLabel>
                            <Select
                                value={pipelineForm.picking_run_name}
                                label="Particle-picking run"
                                onChange={(e) => handlePipelineChange('picking_run_name', e.target.value)}
                            >
                                {!formData.session_name && (
                                    <MenuItem disabled>Select a session first</MenuItem>
                                )}
                                {formData.session_name && loadingPickingRuns && (
                                    <MenuItem disabled>Loading runs...</MenuItem>
                                )}
                                {formData.session_name && !loadingPickingRuns && pickingRuns.length === 0 && (
                                    <MenuItem disabled>No saved picking runs</MenuItem>
                                )}
                                {pickingRuns.map((run) => (
                                    <MenuItem key={run.name} value={run.name}>
                                        {run.name} ({run.particle_count} particles)
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
                        <TextField
                            fullWidth
                            label="Pipeline Output Directory"
                            value={pipelineForm.output_directory}
                            onChange={(e) => handlePipelineChange('output_directory', e.target.value)}
                            helperText="Leave empty for the session export_pipeline directory"
                        />
                    </Grid>

                    {selectedPickingRun && (
                        <Grid size={12}>
                            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                                <Chip size="small" label={`${selectedPickingRun.image_count} micrographs`} />
                                <Chip size="small" label={`${selectedPickingRun.particle_count} particles`} />
                                {PARTICLE_CLASS_OPTIONS.map((option) => (
                                    selectedPickingRun.class_counts?.[option.id] ? (
                                        <Chip
                                            key={option.id}
                                            size="small"
                                            variant="outlined"
                                            label={`${option.label}: ${selectedPickingRun.class_counts[option.id]}`}
                                        />
                                    ) : null
                                ))}
                            </Stack>
                        </Grid>
                    )}

                    <Grid
                        size={{
                            xs: 12,
                            md: 6
                        }}>
                        <FormControl fullWidth>
                            <InputLabel>Classes to extract</InputLabel>
                            <Select
                                multiple
                                value={pipelineForm.include_classes}
                                onChange={(e) => {
                                    const value = e.target.value;
                                    handlePipelineChange(
                                        'include_classes',
                                        typeof value === 'string' ? value.split(',') : value,
                                    );
                                }}
                                input={<OutlinedInput label="Classes to extract" />}
                                renderValue={(selected) => (
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {(selected as string[]).map((value) => {
                                            const option = PARTICLE_CLASS_OPTIONS.find((item) => item.id === value);
                                            return <Chip key={value} label={option?.label || value} size="small" />;
                                        })}
                                    </Box>
                                )}
                            >
                                {PARTICLE_CLASS_OPTIONS.map((option) => (
                                    <MenuItem key={option.id} value={option.id}>
                                        <Checkbox checked={pipelineForm.include_classes.includes(option.id)} />
                                        <ListItemText primary={option.label} />
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Box Size"
                            value={pipelineForm.box_size}
                            onChange={(e) => handlePipelineChange('box_size', parseInt(e.target.value) || 256)}
                            slotProps={{ htmlInput: { min: 16, step: 16 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Edge Width"
                            value={pipelineForm.edge_width}
                            onChange={(e) => handlePipelineChange('edge_width', parseInt(e.target.value) || 0)}
                            slotProps={{ htmlInput: { min: 0 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Pixel Size Override"
                            value={pipelineForm.apix}
                            onChange={(e) => handlePipelineChange('apix', e.target.value)}
                            slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Max Particles"
                            value={pipelineForm.max_particles}
                            onChange={(e) => handlePipelineChange('max_particles', e.target.value)}
                            slotProps={{ htmlInput: { min: 1 } }}
                        />
                    </Grid>

                    <Grid size={12}>
                        <Divider />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="2D Classes"
                            value={pipelineForm.num_classes}
                            onChange={(e) => handlePipelineChange('num_classes', parseInt(e.target.value) || 50)}
                            slotProps={{ htmlInput: { min: 2, step: 1 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Presentations"
                            value={pipelineForm.num_presentations}
                            onChange={(e) => handlePipelineChange('num_presentations', parseInt(e.target.value) || 50000)}
                            slotProps={{ htmlInput: { min: 1000, step: 1000 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Align Iters"
                            value={pipelineForm.align_iters}
                            onChange={(e) => handlePipelineChange('align_iters', parseInt(e.target.value) || 1)}
                            slotProps={{ htmlInput: { min: 1 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <FormControl fullWidth>
                            <InputLabel>Compute Backend</InputLabel>
                            <Select
                                value={pipelineForm.compute_backend}
                                label="Compute Backend"
                                onChange={(e) => handlePipelineChange('compute_backend', e.target.value)}
                            >
                                <MenuItem value="torch-auto">Torch Auto</MenuItem>
                                <MenuItem value="cpu">CPU</MenuItem>
                                <MenuItem value="torch-cuda">Torch CUDA</MenuItem>
                                <MenuItem value="torch-mps">Torch MPS</MenuItem>
                                <MenuItem value="torch-cpu">Torch CPU</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="Worker Threads"
                            value={pipelineForm.threads}
                            onChange={(e) => handlePipelineChange('threads', parseInt(e.target.value) || 1)}
                            slotProps={{ htmlInput: { min: 1 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <TextField
                            fullWidth
                            type="number"
                            label="CAN Threads"
                            value={pipelineForm.can_threads}
                            onChange={(e) => handlePipelineChange('can_threads', parseInt(e.target.value) || 1)}
                            slotProps={{ htmlInput: { min: 1 } }}
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={pipelineForm.invert}
                                    onChange={(e) => handlePipelineChange('invert', e.target.checked)}
                                />
                            }
                            label="Invert contrast"
                        />
                    </Grid>

                    <Grid
                        size={{
                            xs: 12,
                            md: 3
                        }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={pipelineForm.write_aligned_stack}
                                    onChange={(e) => handlePipelineChange('write_aligned_stack', e.target.checked)}
                                />
                            }
                            label="Write aligned stack"
                        />
                    </Grid>

                    <Grid sx={{ mt: 1 }} size={12}>
                        <Button
                            variant="contained"
                            startIcon={<Play size={18} />}
                            onClick={handleStartParticlePipeline}
                            disabled={pipelineBusy || !formData.session_name || !pipelineForm.picking_run_name}
                            size="large"
                        >
                            {pipelineBusy ? 'Pipeline Running...' : 'Run Extraction and 2D Classification'}
                        </Button>
                    </Grid>
                </Grid>
            </Paper>

            <ParticleExportPipelineProgressDialog
                open={pipelineProgress.status !== 'idle'}
                onClose={pipelineProgress.reset}
                status={pipelineProgress.status}
                error={pipelineProgress.error}
                jobId={pipelineProgress.jobId}
                summary={pipelineProgress.summary}
                elapsedMs={pipelineProgress.elapsedMs}
                sessionName={pipelineProgress.sessionName}
            />

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
