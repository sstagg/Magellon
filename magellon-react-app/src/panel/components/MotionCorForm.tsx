import {
    Typography,
    Box,
    TextField,
    Grid,
    Paper,
    Button,
    CircularProgress,
    Alert,
    Divider,
    InputAdornment,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent,
    LinearProgress,
    Chip
} from "@mui/material";
import { useState, useEffect, useRef } from "react";
import { Beaker, Upload, FileImage, Settings2, ChevronDown, Zap } from "lucide-react";
import { settings } from "../../core/settings.ts";
import getAxiosClient from '../../core/AxiosClient.ts';
import { useSessionNames } from "../../services/api/FetchUseSessionNames.ts";
import { SessionDto } from "../../components/features/session_viewer/ImageInfoDto.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export interface MotionCorParams {
    FmDose: number;
    PixSize: number;
    kV: number;
    PatchesX: number;
    PatchesY: number;
    Group: number;
    FtBin: number;
    Iter: number;
    Tol: number;
    FlipGain: number;
    RotGain: number;
    Bft_global: number;
    Bft_local: number;
}

export interface MotionCorFormData {
    sessionName: string;
    imageFile: File | null;
    gainFile: File | null;
    defectsFile: File | null;
    params: MotionCorParams;
}

export interface MotionCorFormProps {
    /** Initial session name */
    initialSessionName?: string;
    /** Initial parameter values */
    initialParams?: Partial<MotionCorParams>;
    /** Called when form is successfully submitted */
    onSuccess?: (taskId: string, sessionName: string) => void;
    /** Called when form submission fails */
    onError?: (error: string) => void;
    /** Custom submit handler - if provided, the component won't call the API directly */
    onSubmit?: (data: MotionCorFormData) => Promise<void>;
    /** Whether to show the paper wrapper */
    showPaper?: boolean;
    /** Title for the form */
    title?: string;
    /** Description for the form */
    description?: string;
}

const DEFAULT_PARAMS: MotionCorParams = {
    FmDose: 0.75,
    PixSize: 1.0,
    kV: 300,
    PatchesX: 5,
    PatchesY: 5,
    Group: 3,
    FtBin: 2.0,
    Iter: 7,
    Tol: 0.5,
    FlipGain: 0,
    RotGain: 0,
    Bft_global: 500,
    Bft_local: 150
};

type JobStatus = 'idle' | 'processing' | 'success' | 'error';

interface ProcessingState {
    status: JobStatus;
    taskId: string | null;
    progress: number;
    statusMessage: string;
    isConnected: boolean;
    wsError: string | null;
    resultData?: any; // Store the full result data from the server
}

export const MotionCorForm: React.FC<MotionCorFormProps> = ({
    initialSessionName = "testing",
    initialParams,
    onSuccess,
    onError,
    onSubmit,
    showPaper = true,
    title = "Motion Correction / Frame Alignment",
    description = "Corrects for beam-induced motion in cryo-EM movie stacks using MotionCor2"
}) => {
    // Fetch sessions from API
    const { data: sessions, isLoading: sessionsLoading, error: sessionsError } = useSessionNames();

    // Form state
    const [sessionName, setSessionName] = useState<string>(initialSessionName);
    const [imageFile, setImageFile] = useState<File | null>(null);
    const [gainFile, setGainFile] = useState<File | null>(null);
    const [defectsFile, setDefectsFile] = useState<File | null>(null);

    // MotionCor parameters
    const [params, setParams] = useState<MotionCorParams>({
        ...DEFAULT_PARAMS,
        ...initialParams
    });

    // Status state
    const [jobStatus, setJobStatus] = useState<JobStatus>('idle');
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // WebSocket and processing state
    const [processingState, setProcessingState] = useState<ProcessingState>({
        status: 'idle',
        taskId: null,
        progress: 0,
        statusMessage: '',
        isConnected: false,
        wsError: null
    });
    const wsRef = useRef<WebSocket | null>(null);

    const handleSessionChange = (event: SelectChangeEvent) => {
        setSessionName(event.target.value);
    };

    // WebSocket connection helper
    const connectWebSocket = (taskId: string) => {
        // Extract base URL from settings (e.g., http://localhost:8000)
        const backendUrl = settings.ConfigData.SERVER_API_URL;
        const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
        // Remove the protocol from the URL to get host:port
        const hostPart = backendUrl.replace(/^https?:\/\//, '');
        
        // Get auth token from localStorage
        const token = localStorage.getItem('access_token');
        
        // Construct WebSocket URL with token as query parameter
        // Note: endpoint is at /web/ws/motioncor-test/{task_id} with /web prefix from router
        const wsUrl = `${wsProtocol}//${hostPart}/web/ws/motioncor-test/${taskId}${token ? `?token=${token}` : ''}`;
        
        try {
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket connected for task:', taskId);
                setProcessingState(prev => ({
                    ...prev,
                    isConnected: true,
                    wsError: null,
                    statusMessage: 'Connected to task processing...'
                }));
            };

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    console.log('WebSocket message received:', message);
                    console.log('Message type:', message.type);

                    switch (message.type) {
                        case 'connected':
                            console.log('Task processing connected');
                            setProcessingState(prev => ({
                                ...prev,
                                statusMessage: 'Connected to task updates'
                            }));
                            break;

                        case 'status_update':
                            console.log('Status update:', message.message);
                            setProcessingState(prev => ({
                                ...prev,
                                status: 'processing',
                                progress: message.progress || prev.progress,
                                statusMessage: message.message || 'Processing...'
                            }));
                            setJobStatus('processing');
                            break;

                        case 'result':
                            console.log('Result received with data:', message.data);
                            console.log('Output files:', message.data?.output_files);
                            setProcessingState(prev => ({
                                ...prev,
                                status: 'success',
                                progress: 100,
                                statusMessage: 'Task completed successfully!',
                                resultData: message.data // Store the full result data
                            }));
                            setJobStatus('success');
                            setSuccessMessage(`Motion correction task completed. Task ID: ${taskId}`);
                            // Pass the result data to the success callback if available
                            onSuccess?.(taskId, sessionName, message.data);
                            closeWebSocket();
                            break;

                        case 'error':
                            console.error('Task error:', message.error);
                            setProcessingState(prev => ({
                                ...prev,
                                status: 'error',
                                statusMessage: `Error: ${message.error}`
                            }));
                            setJobStatus('error');
                            setError(message.error || 'Task failed');
                            onError?.(message.error || 'Task failed');
                            closeWebSocket();
                            break;

                        case 'ping':
                            // Keep-alive ping, no action needed
                            console.debug('Received ping');
                            break;

                        default:
                            console.warn('Unknown message type:', message.type);
                    }
                } catch (err) {
                    console.error('Error processing WebSocket message:', err);
                    console.error('Raw event data:', event.data);
                }
            };

            ws.onerror = (event) => {
                console.error('WebSocket error:', event);
                setProcessingState(prev => ({
                    ...prev,
                    isConnected: false,
                    wsError: 'WebSocket connection error'
                }));
                setError('WebSocket connection failed');
                setJobStatus('error');
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setProcessingState(prev => ({
                    ...prev,
                    isConnected: false
                }));
            };

            wsRef.current = ws;
        } catch (err) {
            console.error('Failed to create WebSocket:', err);
            setError('Failed to connect to task updates');
            setJobStatus('error');
        }
    };

    const closeWebSocket = () => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    };

    // Cleanup WebSocket on unmount
    useEffect(() => {
        return () => {
            closeWebSocket();
        };
    }, []);

    const handleParamChange = (field: keyof MotionCorParams, value: string) => {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
            setParams(prev => ({ ...prev, [field]: numValue }));
        } else if (value === '') {
            setParams(prev => ({ ...prev, [field]: 0 }));
        }
    };

    const handleImageFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setImageFile(event.target.files[0]);
        }
    };

    const handleGainFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setGainFile(event.target.files[0]);
        }
    };

    const handleDefectsFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setDefectsFile(event.target.files[0]);
        }
    };

    const handleReset = () => {
        setImageFile(null);
        setGainFile(null);
        setDefectsFile(null);
        setSessionName(initialSessionName);
        setParams({ ...DEFAULT_PARAMS, ...initialParams });
        setError(null);
        setSuccessMessage(null);
        setJobStatus('idle');
        setProcessingState({
            status: 'idle',
            taskId: null,
            progress: 0,
            statusMessage: '',
            isConnected: false,
            wsError: null
        });
        closeWebSocket();
    };

    const handleSubmit = async () => {
        setError(null);
        setSuccessMessage(null);

        // Validation
        if (!imageFile) {
            const errMsg = "Please select an image file (MRC/TIFF)";
            setError(errMsg);
            onError?.(errMsg);
            return;
        }
        if (!gainFile) {
            const errMsg = "Please select a gain reference file";
            setError(errMsg);
            onError?.(errMsg);
            return;
        }
        if (!sessionName) {
            const errMsg = "Please select a session";
            setError(errMsg);
            onError?.(errMsg);
            return;
        }

        setJobStatus('processing');

        // If custom submit handler is provided, use it
        if (onSubmit) {
            try {
                await onSubmit({
                    sessionName,
                    imageFile,
                    gainFile,
                    defectsFile,
                    params
                });
                setJobStatus('success');
                setSuccessMessage("Motion correction task submitted successfully");
            } catch (err: any) {
                setJobStatus('error');
                const errMsg = err.message || 'Failed to submit job';
                setError(errMsg);
                onError?.(errMsg);
            }
            return;
        }

        // Default API submission
        try {
            const formData = new FormData();
            formData.append('image_file', imageFile);
            formData.append('gain_file', gainFile);
            formData.append('session_name', sessionName);

            if (defectsFile) {
                formData.append('defects_file', defectsFile);
            }

            // Add parameters as JSON string
            const dataJson = JSON.stringify({
                FmDose: params.FmDose,
                PixSize: params.PixSize,
                kV: params.kV,
                Patchrows: params.PatchesY,
                Patchcols: params.PatchesX,
                Group: params.Group,
                FtBin: params.FtBin,
                Iter: params.Iter,
                Tol: params.Tol,
                FlipGain: params.FlipGain,
                RotGain: params.RotGain,
                Bft_global: params.Bft_global,
                Bft_local: params.Bft_local
            });
            formData.append('data', dataJson);

            const response = await apiClient.post('/web/test-motioncor', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            const taskId = response.data.task_id || 'N/A';
            setProcessingState(prev => ({
                ...prev,
                taskId,
                status: 'processing',
                progress: 10,
                statusMessage: 'Task queued, connecting to updates...'
            }));
            setJobStatus('processing');

            // Connect to WebSocket for real-time updates
            connectWebSocket(taskId);
        } catch (err: any) {
            setJobStatus('error');
            const errMsg = err.response?.data?.detail || err.message || 'Failed to submit job';
            setError(errMsg);
            onError?.(errMsg);
            setProcessingState(prev => ({
                ...prev,
                status: 'error',
                statusMessage: errMsg
            }));
        }
    };

    const formContent = (
        <>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <FileImage size={20} />
                {title}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                {description}
            </Typography>

            <Divider sx={{ mb: 3 }} />

            {/* Processing State Display */}
            {jobStatus === 'processing' && (
                <Box sx={{ mb: 3, p: 2, backgroundColor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'info.main' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <CircularProgress size={24} />
                        <Typography variant="subtitle1" color="info.main">
                            {processingState.statusMessage || 'Processing...'}
                        </Typography>
                    </Box>
                    {processingState.taskId && (
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1 }}>
                            Task ID: <code>{processingState.taskId}</code>
                        </Typography>
                    )}
                    {processingState.progress > 0 && (
                        <Box>
                            <LinearProgress variant="determinate" value={processingState.progress} />
                            <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
                                {processingState.progress}% Complete
                            </Typography>
                        </Box>
                    )}
                    {processingState.isConnected && (
                        <Chip
                            icon={<Zap size={14} />}
                            label="Connected"
                            size="small"
                            color="success"
                            variant="outlined"
                            sx={{ mt: 2 }}
                        />
                    )}
                </Box>
            )}

            {/* Status Alerts */}
            {error && (
                <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}
            {successMessage && (
                <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
                    {successMessage}
                </Alert>
            )}

            <Grid container spacing={3}>
                {/* Session Selector */}
                {/* <Grid size={{ xs: 12, md: 6 }}>
                    <FormControl fullWidth required>
                        <InputLabel id="session-select-label">Session</InputLabel>
                        <Select
                            labelId="session-select-label"
                            id="session-select"
                            value={sessionName}
                            label="Session"
                            onChange={handleSessionChange}
                            disabled={sessionsLoading}
                        >
                            <MenuItem value="">
                                <em>{sessionsLoading ? "Loading sessions..." : "Select a session"}</em>
                            </MenuItem>
                            {(sessions as SessionDto[])?.map((session) => (
                                <MenuItem key={session.Oid} value={session.name}>
                                    {session.name}
                                </MenuItem>
                            ))}
                        </Select>
                        {sessionsError && (
                            <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                                Failed to load sessions
                            </Typography>
                        )}
                    </FormControl>
                </Grid> */}

                {/* Empty grid for alignment */}
                <Grid size={{ xs: 12, md: 6 }} />

                {/* Image File Upload */}
                <Grid size={{ xs: 12, md: 4 }}>
                    <Box sx={{
                        border: '2px dashed',
                        borderColor: imageFile ? 'success.main' : 'divider',
                        borderRadius: 1,
                        p: 2,
                        textAlign: 'center',
                        backgroundColor: imageFile ? 'action.selected' : 'transparent',
                        transition: 'all 0.2s',
                        minHeight: 100,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center'
                    }}>
                        <input
                            accept=".mrc,.tif,.tiff,.eer"
                            style={{ display: 'none' }}
                            id="image-file-upload"
                            type="file"
                            onChange={handleImageFileChange}
                        />
                        <label htmlFor="image-file-upload">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<Upload size={18} />}
                                sx={{ mb: 1 }}
                                color={imageFile ? "success" : "primary"}
                            >
                                Image File *
                            </Button>
                        </label>
                        <Typography variant="body2" color="textSecondary" noWrap>
                            {imageFile ? imageFile.name : "MRC, TIFF, or EER movie"}
                        </Typography>
                    </Box>
                </Grid>

                {/* Gain File Upload */}
                <Grid size={{ xs: 12, md: 4 }}>
                    <Box sx={{
                        border: '2px dashed',
                        borderColor: gainFile ? 'success.main' : 'divider',
                        borderRadius: 1,
                        p: 2,
                        textAlign: 'center',
                        backgroundColor: gainFile ? 'action.selected' : 'transparent',
                        transition: 'all 0.2s',
                        minHeight: 100,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center'
                    }}>
                        <input
                            accept=".mrc,.tif,.tiff,.dm4"
                            style={{ display: 'none' }}
                            id="gain-file-upload"
                            type="file"
                            onChange={handleGainFileChange}
                        />
                        <label htmlFor="gain-file-upload">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<Upload size={18} />}
                                sx={{ mb: 1 }}
                                color={gainFile ? "success" : "primary"}
                            >
                                Gain File *
                            </Button>
                        </label>
                        <Typography variant="body2" color="textSecondary" noWrap>
                            {gainFile ? gainFile.name : "Gain reference (MRC/TIFF/DM4)"}
                        </Typography>
                    </Box>
                </Grid>

                {/* Defects File Upload (Optional) */}
                <Grid size={{ xs: 12, md: 4 }}>
                    <Box sx={{
                        border: '2px dashed',
                        borderColor: defectsFile ? 'success.main' : 'divider',
                        borderRadius: 1,
                        p: 2,
                        textAlign: 'center',
                        backgroundColor: defectsFile ? 'action.selected' : 'transparent',
                        transition: 'all 0.2s',
                        minHeight: 100,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center'
                    }}>
                        <input
                            accept=".txt,.defects"
                            style={{ display: 'none' }}
                            id="defects-file-upload"
                            type="file"
                            onChange={handleDefectsFileChange}
                        />
                        <label htmlFor="defects-file-upload">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<Upload size={18} />}
                                sx={{ mb: 1 }}
                                color={defectsFile ? "success" : "inherit"}
                            >
                                Defects File
                            </Button>
                        </label>
                        <Typography variant="body2" color="textSecondary" noWrap>
                            {defectsFile ? defectsFile.name : "Optional defects file"}
                        </Typography>
                    </Box>
                </Grid>
            </Grid>

            {/* Advanced Parameters Accordion */}
            <Accordion sx={{ mt: 3 }}>
                <AccordionSummary expandIcon={<ChevronDown />}>
                    <Typography sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Settings2 size={18} />
                        Advanced Parameters
                    </Typography>
                </AccordionSummary>
                <AccordionDetails>
                    <Grid container spacing={2}>
                        {/* Acquisition Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom>
                                Acquisition Parameters
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Pixel Size"
                                type="number"
                                value={params.PixSize}
                                onChange={(e) => handleParamChange('PixSize', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Dose per Frame"
                                type="number"
                                value={params.FmDose}
                                onChange={(e) => handleParamChange('FmDose', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">e/A^2</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Voltage"
                                type="number"
                                value={params.kV}
                                onChange={(e) => handleParamChange('kV', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">kV</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Frame Group"
                                type="number"
                                value={params.Group}
                                onChange={(e) => handleParamChange('Group', e.target.value)}
                                size="small"
                                helperText="Frames to group"
                            />
                        </Grid>

                        {/* Alignment Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
                                Alignment Parameters
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Patches X"
                                type="number"
                                value={params.PatchesX}
                                onChange={(e) => handleParamChange('PatchesX', e.target.value)}
                                size="small"
                                helperText="X patches for local alignment"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Patches Y"
                                type="number"
                                value={params.PatchesY}
                                onChange={(e) => handleParamChange('PatchesY', e.target.value)}
                                size="small"
                                helperText="Y patches for local alignment"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Iterations"
                                type="number"
                                value={params.Iter}
                                onChange={(e) => handleParamChange('Iter', e.target.value)}
                                size="small"
                                helperText="Max alignment iterations"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Tolerance"
                                type="number"
                                value={params.Tol}
                                onChange={(e) => handleParamChange('Tol', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">px</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>

                        {/* Processing Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
                                Processing Parameters
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Fourier Binning"
                                type="number"
                                value={params.FtBin}
                                onChange={(e) => handleParamChange('FtBin', e.target.value)}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Global B-Factor"
                                type="number"
                                value={params.Bft_global}
                                onChange={(e) => handleParamChange('Bft_global', e.target.value)}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Local B-Factor"
                                type="number"
                                value={params.Bft_local}
                                onChange={(e) => handleParamChange('Bft_local', e.target.value)}
                                size="small"
                            />
                        </Grid>

                        {/* Gain Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
                                Gain Correction
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Flip Gain"
                                type="number"
                                value={params.FlipGain}
                                onChange={(e) => handleParamChange('FlipGain', e.target.value)}
                                size="small"
                                helperText="0=none, 1=updown, 2=leftright"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                label="Rotate Gain"
                                type="number"
                                value={params.RotGain}
                                onChange={(e) => handleParamChange('RotGain', e.target.value)}
                                size="small"
                                helperText="0=none, 1=90, 2=180, 3=270"
                            />
                        </Grid>
                    </Grid>
                </AccordionDetails>
            </Accordion>

            {/* Submit Button */}
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button
                    variant="outlined"
                    onClick={handleReset}
                    disabled={jobStatus === 'processing'}
                >
                    Reset
                </Button>
                <Button
                    variant="contained"
                    color="primary"
                    onClick={handleSubmit}
                    disabled={jobStatus === 'processing'}
                    startIcon={jobStatus === 'processing' ? <CircularProgress size={18} color="inherit" /> : <Beaker size={18} />}
                >
                    {jobStatus === 'processing' ? 'Submitting...' : 'Run Motion Correction'}
                </Button>
            </Box>
        </>
    );

    if (showPaper) {
        return (
            <Paper elevation={2} sx={{ p: 3 }}>
                {formContent}
            </Paper>
        );
    }

    return <Box>{formContent}</Box>;
};

export default MotionCorForm;
