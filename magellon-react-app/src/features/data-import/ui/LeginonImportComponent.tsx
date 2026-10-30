import {Alert, Button, Checkbox, FormControl, FormControlLabel, Box, InputAdornment, TextField, Typography} from "@mui/material";

import {useEffect, useRef, useState} from "react";
import {useForm, UseFormRegisterReturn} from "react-hook-form";
import {Cached, CalendarMonthOutlined, AttachFile, FolderOpen} from "@mui/icons-material";
import Grid from '@mui/material/Grid';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';
import { useImportJobProgress } from "../lib/useImportJobProgress.ts";
import { ImportProgressDialog } from "./ImportProgressDialog.tsx";
import { PathBrowseDialog } from "./PathBrowseDialog.tsx";
import { useSessionNameCheck } from "../lib/useSessionNameCheck.ts";
import { apiErrorMessage } from '../../../shared/api/apiError.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);


// The user gives the session's images folder, its frames (movies) folder and
// gain file (a path, or uploaded), and its Leginon session name; the new Magellon session takes the
// Leginon name unless a custom name is typed (one name, one import). The Leginon DB
// connection is server config (LEGINON_DB_* in Docker/.env), not a form field.
interface ILeginonImportForm {
    magellon_project_name: string;
    images_directory: string;
    frames_directory: string;
    gain_path: string;
    session_name: string;
    magellon_session_name: string;
    if_do_subtasks: boolean;
    copy_images: boolean;
    copy_frames: boolean;
    retries: number;
}
const defaultValues: ILeginonImportForm = {
    magellon_project_name: "Leginon",
    images_directory: "",
    frames_directory: "",
    gain_path: "",
    session_name: "",
    magellon_session_name: "",
    if_do_subtasks: false,
    copy_images: false,
    copy_frames: false,
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

/** A path below the GPFS root, typed or chosen with Browse; the root is shown
 *  in front and the full path below. */
const PathField = ({ label, placeholder, help, value, error, disabled, mode, onBrowse, registration }: {
    label: string;
    placeholder: string;
    help: string;
    value: string;
    error?: string;
    disabled?: boolean;
    mode: "folder" | "file";
    onBrowse: (relativePath: string) => void;
    registration: UseFormRegisterReturn;
}) => {
    const [browsing, setBrowsing] = useState(false);
    const current = toServerPath(value);
    return (
        <FormControl fullWidth>
            <TextField
                label={label}
                variant="filled"
                margin="dense"
                placeholder={placeholder}
                disabled={disabled}
                {...registration}
                error={!!error}
                helperText={error ?? (toRelativePath(value) ? `${help}. Full path: ${GPFS_HOST_ROOT}/${toRelativePath(value)}` : help)}
                slotProps={{
                    inputLabel: { shrink: true },
                    input: {
                        startAdornment: (
                            <InputAdornment position="start">{GPFS_HOST_ROOT}/</InputAdornment>
                        ),
                        endAdornment: (
                            <InputAdornment position="end">
                                <Button size="small" startIcon={<FolderOpen />} disabled={disabled}
                                        onClick={() => setBrowsing(true)}>
                                    Browse
                                </Button>
                            </InputAdornment>
                        ),
                    }
                }} />
            <PathBrowseDialog
                open={browsing}
                mode={mode}
                title={`Choose the ${label.replace(/ \(optional\)$/i, '').toLowerCase()}`}
                startPath={mode === "file" && toRelativePath(value) ? current.split('/').slice(0, -1).join('/') : current}
                onClose={() => setBrowsing(false)}
                onChoose={(path) => onBrowse(toRelativePath(path))} />
        </FormControl>
    );
};

const FOLDER_FIELDS = ['images_directory', 'frames_directory', 'gain_path'] as const;
type FolderField = typeof FOLDER_FIELDS[number];

const FOLDER_LABELS: Record<FolderField, string> = {
    images_directory: 'images folder',
    frames_directory: 'frames folder',
    gain_path: 'gain file',
};

const SESSION_NAME_RULE = (value: string) =>
    !/[\\/\s]/.test(value.trim()) || 'Use a name without slashes or spaces';

export const LeginonImportComponent = () => {
    const { handleSubmit, register, getValues, setValue, trigger, watch, formState: { errors } } = useForm<ILeginonImportForm>({
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
    const imagesDirectory = watch('images_directory');
    const framesDirectory = watch('frames_directory');
    const gainPath = watch('gain_path');
    const leginonName = watch('session_name');
    const magellonName = watch('magellon_session_name');
    const nameCheck = useSessionNameCheck(magellonName);
    // Import stays off until every required field has a value.
    const allFilled = !!leginonName.trim() && !!magellonName.trim() && !!watch('magellon_project_name').trim()
        && !!toRelativePath(imagesDirectory) && !!toRelativePath(framesDirectory)
        && (!!gainsFile || !!toRelativePath(gainPath));

    useEffect(() => {
        if (!magellonNameEdited) setValue('magellon_session_name', leginonName, { shouldValidate: !!leginonName });
    }, [leginonName, magellonNameEdited, setValue]);

    // The folders and gain file are filled in from the Leginon name, where the
    // lab keeps them; a field the user changed keeps their value.
    const suggested = useRef<Partial<Record<FolderField, string>>>({});
    // Fields the lookup couldn't fill, for the note asking the user to.
    const [notFound, setNotFound] = useState<{ session: string; fields: FolderField[] } | null>(null);
    useEffect(() => {
        const name = leginonName.trim();
        setNotFound(null);
        if (!name || /[\\/\s]/.test(name)) return;
        let stale = false;
        const timer = setTimeout(async () => {
            try {
                const { data } = await apiClient.get('/image/leginon_folders', { params: { session_name: name } });
                if (stale) return;
                const missing: FolderField[] = [];
                for (const field of FOLDER_FIELDS) {
                    const current = getValues(field);
                    if (current && current !== suggested.current[field]) continue;
                    const value: string = data?.[field] ?? '';
                    suggested.current[field] = value;
                    setValue(field, value, { shouldValidate: !!value });
                    if (!value) missing.push(field);
                }
                setNotFound(missing.length ? { session: name, fields: missing } : null);
            } catch { /* nothing suggested: the user fills the fields in */ }
        }, 400);
        return () => { stale = true; clearTimeout(timer); };
    }, [leginonName, getValues, setValue]);

    // An uploaded gain file stands in for the path.
    useEffect(() => {
        if (gainsFile) trigger('gain_path');
    }, [gainsFile, trigger]);

    const onFormSubmit = async (data: ILeginonImportForm) => {
        progress.scheduling();
        try {
            const formData = new FormData();
            formData.append('magellon_project_name', data.magellon_project_name);
            formData.append('magellon_session_name', data.magellon_session_name.trim());
            formData.append('session_name', data.session_name.trim());
            formData.append('images_directory', toServerPath(data.images_directory));
            formData.append('frames_directory', toServerPath(data.frames_directory));
            if (!gainsFile && toRelativePath(data.gain_path)) {
                formData.append('gain_path', toServerPath(data.gain_path));
            }
            formData.append('if_do_subtasks', String(data.if_do_subtasks));
            formData.append('copy_images', String(data.copy_images));
            formData.append('copy_frames', String(data.copy_frames));
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
                            helperText={errors.session_name?.message ?? 'The session name in Leginon; fills in the folders and gain file below'}
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
                            // Filled in from the Leginon name by code, which the label can't see.
                            slotProps={{ inputLabel: { shrink: !!magellonName || undefined } }}
                        />
                    </FormControl>
                </Grid>

                {notFound && (
                    <Grid size={12}>
                        <Alert severity="warning">
                            {`Couldn't find the ${notFound.fields.map((f) => FOLDER_LABELS[f]).join(', ').replace(/, ([^,]*)$/, ' or $1')} `
                                + `for ${notFound.session} in ${GPFS_HOST_ROOT}/leginondata or ${GPFS_HOST_ROOT}/framesdata. `
                                + 'All three are needed: please fill them in below, or use Browse.'}
                        </Alert>
                    </Grid>
                )}

                <Grid size={12}>
                    <PathField
                        label="Images Folder"
                        placeholder="leginondata/24dec03a"
                        help="The session's images folder (subfolders such as rawdata are searched too), filled in from the session name"
                        value={imagesDirectory}
                        error={errors.images_directory?.message}
                        mode="folder"
                        onBrowse={(path) => setValue('images_directory', path, { shouldValidate: true, shouldDirty: true })}
                        registration={register('images_directory', {
                            required: 'Images folder is required',
                            validate: (value) => !!toRelativePath(value) || 'Enter the folder below the GPFS root',
                        })} />
                </Grid>

                <Grid size={12}>
                    <PathField
                        label="Frames Folder"
                        placeholder="framesdata/24dec03a"
                        help="The session's movies folder (subfolders are searched too), filled in from the session name"
                        value={framesDirectory}
                        error={errors.frames_directory?.message}
                        mode="folder"
                        onBrowse={(path) => setValue('frames_directory', path, { shouldValidate: true, shouldDirty: true })}
                        registration={register('frames_directory', {
                            required: 'Frames folder is required',
                            validate: (value) => !!toRelativePath(value) || 'Enter the folder below the GPFS root',
                        })} />
                </Grid>

                <Grid size={12}>
                    <PathField
                        label="Gain File"
                        placeholder="framesdata/24dec03a/20241202_53597_gain_multi_ref.tif"
                        help={gainsFile
                            ? `Using the uploaded file ${gainsFile.name} instead`
                            : 'The gain reference for the movies, filled in from the session name, or upload it below'}
                        value={gainPath}
                        disabled={!!gainsFile}
                        error={errors.gain_path?.message}
                        mode="file"
                        onBrowse={(path) => setValue('gain_path', path, { shouldValidate: true, shouldDirty: true })}
                        registration={register('gain_path', {
                            validate: (value) => !!gainsFile || !!toRelativePath(value)
                                || 'Give the gain file, or upload it below',
                        })} />
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

                <Grid size={12}>
                    <FormControlLabel
                        control={<Checkbox {...register('copy_images')} color="primary" />}
                        label="Copy images into the session (only to export it, e.g. back to another site; uses space)"
                    />
                </Grid>

                <Grid size={12}>
                    <FormControlLabel
                        control={<Checkbox {...register('copy_frames')} color="primary" />}
                        label="Copy movies into the session (only to export it, e.g. back to another site; slow and uses space)"
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
                    {gainsFile ? gainsFile.name : 'Upload Gain File (instead of a path)'}
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
                        disabled={isSubmitting || !!nameCheck.problem || !allFilled}
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