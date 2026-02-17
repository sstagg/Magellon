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
    SelectChangeEvent
} from "@mui/material";
import { useState } from "react";
import { Beaker, Upload, FileImage, Settings2, ChevronDown, Focus } from "lucide-react";
import { settings } from "../../core/settings.ts";
import getAxiosClient from '../../core/AxiosClient.ts';
import { useSessionNames } from "../../services/api/FetchUseSessionNames.ts";
import { SessionDto } from "../../components/features/session_viewer/ImageInfoDto.ts";

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

export interface CTFParams {
    PixSize: number;
    kV: number;
    Cs: number;
    AmpContrast: number;
    SpectrumSize: number;
    MinRes: number;
    MaxRes: number;
    MinDefocus: number;
    MaxDefocus: number;
    DefocusStep: number;
    Astigmatism: number;
    PhaseShift: boolean;
}

export interface CTFFormData {
    sessionName: string;
    imageFile: File | null;
    params: CTFParams;
}

export interface CTFFormProps {
    initialSessionName?: string;
    initialParams?: Partial<CTFParams>;
    onSuccess?: (taskId: string, sessionName: string) => void;
    onError?: (error: string) => void;
    onSubmit?: (data: CTFFormData) => Promise<void>;
    showPaper?: boolean;
    title?: string;
    description?: string;
}

const DEFAULT_PARAMS: CTFParams = {
    PixSize: 1.0,
    kV: 300,
    Cs: 2.7,
    AmpContrast: 0.1,
    SpectrumSize: 512,
    MinRes: 30.0,
    MaxRes: 5.0,
    MinDefocus: 5000,
    MaxDefocus: 50000,
    DefocusStep: 500,
    Astigmatism: 100,
    PhaseShift: false
};

type JobStatus = 'idle' | 'processing' | 'success' | 'error';

export const CTFForm: React.FC<CTFFormProps> = ({
    initialSessionName = "",
    initialParams,
    onSuccess,
    onError,
    onSubmit,
    showPaper = true,
    title = "CTF Estimation",
    description = "Estimates Contrast Transfer Function parameters using CTFFIND4"
}) => {
    const { data: sessions, isLoading: sessionsLoading, error: sessionsError } = useSessionNames();

    const [sessionName, setSessionName] = useState<string>(initialSessionName);
    const [imageFile, setImageFile] = useState<File | null>(null);

    const [params, setParams] = useState<CTFParams>({
        ...DEFAULT_PARAMS,
        ...initialParams
    });

    const [jobStatus, setJobStatus] = useState<JobStatus>('idle');
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const handleSessionChange = (event: SelectChangeEvent) => {
        setSessionName(event.target.value);
    };

    const handleParamChange = (field: keyof CTFParams, value: string) => {
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

    const handleReset = () => {
        setImageFile(null);
        setSessionName(initialSessionName);
        setParams({ ...DEFAULT_PARAMS, ...initialParams });
        setError(null);
        setSuccessMessage(null);
        setJobStatus('idle');
    };

    const handleSubmit = async () => {
        setError(null);
        setSuccessMessage(null);

        if (!imageFile) {
            const errMsg = "Please select an image file (MRC/TIFF)";
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

        if (onSubmit) {
            try {
                await onSubmit({
                    sessionName,
                    imageFile,
                    params
                });
                setJobStatus('success');
                setSuccessMessage("CTF estimation task submitted successfully");
            } catch (err: any) {
                setJobStatus('error');
                const errMsg = err.message || 'Failed to submit job';
                setError(errMsg);
                onError?.(errMsg);
            }
            return;
        }

        try {
            const formData = new FormData();
            formData.append('image_file', imageFile);
            formData.append('session_name', sessionName);

            const dataJson = JSON.stringify({
                PixSize: params.PixSize,
                kV: params.kV,
                Cs: params.Cs,
                AmpContrast: params.AmpContrast,
                SpectrumSize: params.SpectrumSize,
                MinRes: params.MinRes,
                MaxRes: params.MaxRes,
                MinDefocus: params.MinDefocus,
                MaxDefocus: params.MaxDefocus,
                DefocusStep: params.DefocusStep,
                Astigmatism: params.Astigmatism,
                PhaseShift: params.PhaseShift
            });
            formData.append('data', dataJson);

            const response = await apiClient.post('/web/test-ctf', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            setJobStatus('success');
            const taskId = response.data.task_id || 'N/A';
            setSuccessMessage(`CTF estimation task created successfully. Task ID: ${taskId}`);
            onSuccess?.(taskId, sessionName);
        } catch (err: any) {
            setJobStatus('error');
            const errMsg = err.response?.data?.detail || err.message || 'Failed to submit job';
            setError(errMsg);
            onError?.(errMsg);
        }
    };

    const formContent = (
        <>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Focus size={20} />
                {title}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                {description}
            </Typography>

            <Divider sx={{ mb: 3 }} />

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
                <Grid size={{ xs: 12, md: 6 }}>
                    <FormControl fullWidth required variant="filled">
                        <InputLabel id="ctf-session-select-label">Session</InputLabel>
                        <Select
                            labelId="ctf-session-select-label"
                            id="ctf-session-select"
                            value={sessionName}
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
                </Grid>

                <Grid size={{ xs: 12, md: 6 }} />

                {/* Image File Upload */}
                <Grid size={{ xs: 12, md: 6 }}>
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
                            accept=".mrc,.tif,.tiff"
                            style={{ display: 'none' }}
                            id="ctf-image-file-upload"
                            type="file"
                            onChange={handleImageFileChange}
                        />
                        <label htmlFor="ctf-image-file-upload">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<Upload size={18} />}
                                sx={{ mb: 1 }}
                                color={imageFile ? "success" : "primary"}
                            >
                                Micrograph File *
                            </Button>
                        </label>
                        <Typography variant="body2" color="textSecondary" noWrap>
                            {imageFile ? imageFile.name : "Motion-corrected micrograph (MRC/TIFF)"}
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
                        {/* Microscope Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom>
                                Microscope Parameters
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
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
                                variant="filled"
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
                                variant="filled"
                                label="Spherical Aberration (Cs)"
                                type="number"
                                value={params.Cs}
                                onChange={(e) => handleParamChange('Cs', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">mm</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Amplitude Contrast"
                                type="number"
                                value={params.AmpContrast}
                                onChange={(e) => handleParamChange('AmpContrast', e.target.value)}
                                size="small"
                                helperText="Typically 0.07-0.1"
                            />
                        </Grid>

                        {/* Search Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
                                Defocus Search Range
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Min Defocus"
                                type="number"
                                value={params.MinDefocus}
                                onChange={(e) => handleParamChange('MinDefocus', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Max Defocus"
                                type="number"
                                value={params.MaxDefocus}
                                onChange={(e) => handleParamChange('MaxDefocus', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Defocus Step"
                                type="number"
                                value={params.DefocusStep}
                                onChange={(e) => handleParamChange('DefocusStep', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Astigmatism"
                                type="number"
                                value={params.Astigmatism}
                                onChange={(e) => handleParamChange('Astigmatism', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                                helperText="Expected astigmatism"
                            />
                        </Grid>

                        {/* Resolution Parameters */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
                                Resolution Range
                            </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Min Resolution"
                                type="number"
                                value={params.MinRes}
                                onChange={(e) => handleParamChange('MinRes', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                                helperText="Lower bound"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Max Resolution"
                                type="number"
                                value={params.MaxRes}
                                onChange={(e) => handleParamChange('MaxRes', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">A</InputAdornment>,
                                }}
                                size="small"
                                helperText="Upper bound"
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <TextField
                                fullWidth
                                variant="filled"
                                label="Spectrum Size"
                                type="number"
                                value={params.SpectrumSize}
                                onChange={(e) => handleParamChange('SpectrumSize', e.target.value)}
                                InputProps={{
                                    endAdornment: <InputAdornment position="end">px</InputAdornment>,
                                }}
                                size="small"
                                helperText="Power of 2"
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
                    startIcon={jobStatus === 'processing' ? <CircularProgress size={18} color="inherit" /> : <Focus size={18} />}
                >
                    {jobStatus === 'processing' ? 'Submitting...' : 'Run CTF Estimation'}
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

export default CTFForm;
