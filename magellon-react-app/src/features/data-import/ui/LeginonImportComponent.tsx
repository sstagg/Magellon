import {Button, Checkbox, FormControl, FormControlLabel, Box, InputAdornment, TextField, Typography} from "@mui/material";

import {useEffect, useState} from "react";
import {useForm} from "react-hook-form";
import {Cached, CalendarMonthOutlined, AttachFile} from "@mui/icons-material";
import Grid from '@mui/material/Grid';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useImportJobProgress } from "../lib/useImportJobProgress.ts";
import { ImportProgressDialog } from "./ImportProgressDialog.tsx";
import { useSessionNameCheck } from "../lib/useSessionNameCheck.ts";
import { apiErrorMessage } from '../../../shared/api/apiError.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);


// The user gives the session's data folder (holding original/, frames/ and
// gains/) and its Leginon session name; the new Magellon session takes the
// Leginon name unless a custom name is typed (one name, one import). The Leginon DB
// connection is server config (LEGINON_DB_* in Docker/.env), not a form field.
interface ILeginonImportForm {
    magellon_project_name: string;
    data_directory: string;
    session_name: string;
    magellon_session_name: string;
    if_do_subtasks: boolean;
    copy_images: boolean;
    retries: number;
}
const defaultValues: ILeginonImportForm = {
    magellon_project_name: "Leginon",
    data_directory: "",
    session_name: "",
    magellon_session_name: "",
    if_do_subtasks: false,
    copy_images: false,
    retries: 0,
};

// Host directory the backend mounts at /gpfs (e.g. /gpfs/research/stagg).
// Users see and type host paths; the backend only accepts /gpfs/... paths.
const GPFS_HOST_ROOT = (settings.ConfigData.GPFS_HOST_ROOT || '/gpfs').replace(/\/+$/, '');

/** Path below the GPFS root, tolerating a pasted root prefix, stray slashes and
 *  spaces around slashes. Spaces inside a folder name are kept (real folders
 *  such as "New folder" exist). */
const toRelativePath = (input: string): string => {
    let path = (input || '').trim()
        .replace(/\\/g, '/')
        .replace(/\s*\/\s*/g, '/')
        .replace(/\/{2,}/g, '/');
    for (const root of [GPFS_HOST_ROOT, '/gpfs', GPFS_HOST_ROOT.replace(/^\//, ''), 'gpfs']) {
        if (path === root || path.startsWith(root + '/')) {
            path = path.slice(root.length);
            break;
        }
    }
    return path.replace(/^\/+|\/+$/g, '');
};

/** The same location as the backend sees it (always under /gpfs). */
const toServerPath = (input: string): string => {
    const relative = toRelativePath(input);
    return relative ? `/gpfs/${relative}` : '/gpfs';
};

const SESSION_NAME_RULE = (value: string) =>
    !/[\\/\s]/.test(value.trim()) || 'Use a name without slashes or spaces';

export const LeginonImportComponent = () => {
    const { handleSubmit, register, setValue, watch, formState: { errors } } = useForm<ILeginonImportForm>({
        mode: 'onChange',
        defaultValues
    });

    const [defectsFile, setDefectsFile] = useState<File | null>(null);
    const [gainsFile, setGainsFile] = useState<File | null>(null);
    // The custom name follows the Leginon name until the user changes it.
    const [magellonNameEdited, setMagellonNameEdited] = useState(false);
    const progress = useImportJobProgress();
    // Only while the request is in flight: imports queue, so more can be
    // started while others run.
    const isSubmitting = progress.status === "scheduling";
    const dataDirectory = watch('data_directory');
    const leginonName = watch('session_name');
    const magellonName = watch('magellon_session_name');
    const nameCheck = useSessionNameCheck(magellonName);

    useEffect(() => {
        if (!magellonNameEdited) setValue('magellon_session_name', leginonName, { shouldValidate: !!leginonName });
    }, [leginonName, magellonNameEdited, setValue]);

    const onFormSubmit = async (data: ILeginonImportForm) => {
        progress.scheduling();
        try {
            const formData = new FormData();
            formData.append('magellon_project_name', data.magellon_project_name);
            formData.append('magellon_session_name', data.magellon_session_name.trim());
            formData.append('session_name', data.session_name.trim());
            formData.append('data_directory', toServerPath(data.data_directory));
            formData.append('if_do_subtasks', String(data.if_do_subtasks));
            formData.append('copy_images', String(data.copy_images));
            formData.append('retries', String(data.retries));

            if (defectsFile) formData.append('defects_file', defectsFile);
            if (gainsFile) formData.append('gains_file', gainsFile);

            const response = await apiClient.post('/image/import_leginon_job', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            // The controller returns 200 even on logical failure — check.
            if (response.data?.error || response.data?.exception) {
                throw new Error(response.data.error || response.data.exception || 'Failed to submit form');
            }
            const jobId = response.data?.job_id;
            if (jobId) progress.start(jobId); else progress.succeed();
        } catch (error) {
            console.error("There was an error submitting the form!", error);
            progress.fail(apiErrorMessage(error, 'Import failed'));
        }
    };

    return (
        <form onSubmit={handleSubmit(onFormSubmit)}>
            <Grid container spacing={2}>
                <Grid size={12}>
                    <Typography variant="h6">
                        {'Leginon Import Tool'}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        {'Welcome to the Leginon Import Tool. Use this tool to import your sessions to Magellon.'}
                    </Typography>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label={"Magellon Project Name"}
                            variant="filled"
                            margin="dense"
                            {...register('magellon_project_name', { required: 'Project name is required' })}
                            error={!!errors.magellon_project_name}
                            helperText={errors.magellon_project_name?.message}
                        />
                    </FormControl>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label={"Data Folder"}
                            variant="filled"
                            margin="dense"
                            placeholder="magellon_demo/24dec03a/home"
                            {...register('data_directory', {
                                required: 'Data folder is required',
                                validate: (value) => !!toRelativePath(value) || 'Enter the folder below the GPFS root',
                            })}
                            error={!!errors.data_directory}
                            helperText={errors.data_directory?.message
                                ?? `The folder that contains original/, frames/ and gains/. Full path: ${GPFS_HOST_ROOT}/${toRelativePath(dataDirectory)}`}
                            slotProps={{
                                input: {
                                    startAdornment: (
                                        <InputAdornment position="start">{GPFS_HOST_ROOT}/</InputAdornment>
                                    ),
                                }
                            }} />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={"Leginon Session Name"}
                            variant="filled"
                            margin="dense"
                            placeholder="e.g. 24dec03a"
                            {...register('session_name', {
                                required: 'Leginon session name is required',
                                validate: SESSION_NAME_RULE,
                            })}
                            error={!!errors.session_name}
                            helperText={errors.session_name?.message ?? 'The session name in Leginon'}
                            slotProps={{
                                input: {
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <CalendarMonthOutlined />
                                        </InputAdornment>
                                    ),
                                }
                            }} />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={"Custom Session Name"}
                            variant="filled"
                            margin="dense"
                            placeholder="e.g. 24dec03a_run2"
                            {...register('magellon_session_name', {
                                required: 'Session name is required',
                                validate: SESSION_NAME_RULE,
                                onChange: (e) => setMagellonNameEdited(e.target.value !== ''),
                            })}
                            error={!!errors.magellon_session_name || !!nameCheck.problem}
                            helperText={errors.magellon_session_name?.message ?? nameCheck.problem
                                ?? 'Same as the Leginon name unless you change it; must not be used already'}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={"Retries"}
                            variant="filled"
                            margin="dense"
                            type="number"
                            {...register('retries')}
                            slotProps={{
                                input: {
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <Cached />
                                        </InputAdornment>
                                    ),
                                }
                            }} />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                {...register('if_do_subtasks')}
                                color="primary"
                            />
                        }
                        label={"If Do Subtasks"}
                    />
                </Grid>

                <Grid size={6}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                {...register('copy_images')}
                                color="primary"
                            />
                        }
                        label={"Copy Images"}
                    />
                </Grid>

                                         <Grid size={12}>
                <FormControl fullWidth>
                    <Button
                    variant="outlined"
                    component="label"
                    startIcon={<AttachFile />}
                    sx={{
                        justifyContent: 'flex-start',
                        textTransform: 'none',
                        py: 1.5,
                        mt: 1
                    }}
                    >
                    {defectsFile ? defectsFile.name : 'Defects File (Optional)'}
                    <input
                        type="file"
                        hidden
                        accept=".txt,.mrc,.mrcs,.tif,.tiff"
                        onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                            setDefectsFile(file);
                        }
                        }}
                    />
                    </Button>

                    {defectsFile && (
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            mt: 1
                        }}>
                        <Typography variant="caption" color="textSecondary">
                        Selected: {defectsFile.name}
                        </Typography>
                        <Button
                        color="error"
                        size="small"
                        onClick={() => setDefectsFile(null)}
                        sx={{ textTransform: 'none' }}
                        >
                        X
                        </Button>
                    </Box>
                    )}
                </FormControl>
                </Grid>

                            <Grid size={12}>
                <FormControl fullWidth>
                    <Button
                    variant="outlined"
                    component="label"
                    startIcon={<AttachFile />}
                    sx={{
                        justifyContent: 'flex-start',
                        textTransform: 'none',
                        py: 1.5,
                        mt: 1
                    }}
                    >
                    {gainsFile ? gainsFile.name : 'Gains File (Optional)'}
                    <input
                        type="file"
                        hidden
                        accept=".txt,.mrc,.mrcs,.tif,.tiff"
                        onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                            setGainsFile(file);
                        }
                        }}
                    />
                    </Button>

                    {gainsFile && (
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            mt: 1
                        }}>
                        <Typography variant="caption" color="textSecondary">
                        Selected: {gainsFile.name}
                        </Typography>
                        <Button
                        color="error"
                        size="small"
                        onClick={() => setGainsFile(null)}
                        sx={{ textTransform: 'none' }}
                        >
                        X
                        </Button>
                    </Box>
                    )}
                </FormControl>
                </Grid>


                <Grid size={12}>
                    <Button
                        variant="contained"
                        color="primary"
                        type="submit"
                        disabled={isSubmitting || !!nameCheck.problem}
                        sx={{ mr: 2 }}
                    >
                        {isSubmitting
                            ? 'Submitting…'
                            : 'Import'}
                    </Button>
                </Grid>
            </Grid>

            <ImportProgressDialog
                open={progress.status !== "idle" && !progress.minimized}
                onClose={progress.reset}
                status={progress.status}
                error={progress.error}
                jobId={progress.jobId}
                summary={progress.summary}
                stepCounts={progress.stepCounts}
                stepTotals={progress.stepTotals}
                elapsedMs={progress.elapsedMs}
                etaMs={progress.etaMs}
                onCancelQueued={progress.cancelQueued}
                onStop={progress.stop}
                stopping={progress.stopping}
                connectionIssue={progress.connectionIssue}
                sessionName={progress.sessionName}
                titleFallback="Leginon import"
            />
        </form>
    );
};