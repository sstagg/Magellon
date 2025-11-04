import Container from "@mui/material/Container";
import {Button, Checkbox, FormControl, FormControlLabel, FormLabel,  InputAdornment, TextField, Typography} from "@mui/material";

import React, {useState} from "react";
import {useForm} from "react-hook-form";
import {useTranslation} from "react-i18next";
import {Cached, CalendarMonthOutlined, AttachFile} from "@mui/icons-material";
import Grid from '@mui/material/Grid';


interface ILeginonImportForm {
    magellon_project_name: string;
    magellon_session_name: string;
    camera_directory: string;
    session_name: string;
    if_do_subtasks: boolean;
    copy_images: boolean;
    retries: number;
    leginon_mysql_host: string;
    leginon_mysql_port: number;
    leginon_mysql_db: string;
    leginon_mysql_user: string;
    leginon_mysql_pass: string;
    replace_type?: string;
    replace_pattern?: string;
    replace_with?: string;
}
const defaultValues: ILeginonImportForm = {
    session_name: "24DEC03A",
    magellon_project_name: "Leginon",
    magellon_session_name: "24DEC03A",
    camera_directory: "/gpfs/24dec03a/home/frames",
    if_do_subtasks: false,
    copy_images: false,
    retries: 0,
    leginon_mysql_user: "usr_object",
    leginon_mysql_pass: "ThPHMn3m39Ds",
    leginon_mysql_host: "localhost",
    leginon_mysql_port: 3310,
    leginon_mysql_db: "dbemdata",
    replace_type: "standard",
    replace_pattern: "/gpfs/research/secm4/leginondata/",
    replace_with: "C:/temp/magellon/"
};

export const LeginonImportComponent = () => {
    const { handleSubmit, register, formState: { errors } } = useForm<ILeginonImportForm>({
        mode: 'onChange',
        defaultValues
    });
    const { t } = useTranslation(['leginon-import', 'global'], { useSuspense: false });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [defectsFile, setDefectsFile] = useState<File | null>(null);

    const onFormSubmit = async (data: ILeginonImportForm) => {
        try {
            setIsSubmitting(true);
            setSubmitError(null);

            // Create FormData for multipart/form-data upload
            const formData = new FormData();

            // Add all form fields
            formData.append('magellon_project_name', data.magellon_project_name);
            formData.append('magellon_session_name', data.magellon_session_name);
            formData.append('camera_directory', data.camera_directory);
            formData.append('session_name', data.session_name);
            formData.append('if_do_subtasks', String(data.if_do_subtasks));
            formData.append('copy_images', String(data.copy_images));
            formData.append('retries', String(data.retries));
            formData.append('leginon_mysql_host', data.leginon_mysql_host);
            formData.append('leginon_mysql_port', String(data.leginon_mysql_port));
            formData.append('leginon_mysql_db', data.leginon_mysql_db);
            formData.append('leginon_mysql_user', data.leginon_mysql_user);
            formData.append('leginon_mysql_pass', data.leginon_mysql_pass);
            formData.append('replace_type', 'none');
            formData.append('replace_pattern', '');
            formData.append('replace_with', '');

            // Add optional defects file if selected
            if (defectsFile) {
                formData.append('defects_file', defectsFile);
            }

            const response = await fetch('http://localhost:8000/image/import_leginon_job', {
                method: 'POST',
                headers: {
                    'accept': 'application/json'
                    // Note: Don't set Content-Type header - browser will set it with boundary
                },
                body: formData
            });
            const result = await response.json();

            // Check for error in response even if HTTP status is 200
            if (!response.ok || result.error || result.exception) {
                const errorMessage = result.error || result.exception || 'Failed to submit form';
                throw new Error(errorMessage);
            }

            console.log('Success:', result);
        } catch (error) {
            console.error("There was an error submitting the form!", error);
            const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
            // Clean up the error message by removing unnecessary characters and quotes
            const cleanErrorMessage = errorMessage
                .replace(/[()\\'"]/g, '') // Remove parentheses, backslashes, and quotes
                .replace(/\[Errno \d+\]/, '') // Remove errno references
                .trim();
            setSubmitError(cleanErrorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit(onFormSubmit)}>
            <Grid container spacing={2}>
                {submitError && (
                    <Grid size={12}>
                        <Typography color="error" variant="body2">
                            {submitError}
                        </Typography>
                    </Grid>
                )}

                <Grid size={12}>
                    <Typography variant="h6">
                        {t('leginon-importer.app.title', { ns: 'leginon-import' })}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        {t('leginon-importer.app.description', { ns: 'leginon-import' })}
                    </Typography>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.magellonProjectName', { ns: 'leginon-import' })}
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
                            label={t('leginon-importer.form.magellonSessionName', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <CalendarMonthOutlined />
                                    </InputAdornment>
                                ),
                            }}
                            {...register('magellon_session_name')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.sessionName', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            {...register('session_name')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.cameraDirectory', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            {...register('camera_directory')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.retries', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            type="number"
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <Cached />
                                    </InputAdornment>
                                ),
                            }}
                            {...register('retries')}
                        />
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
                        label={t('leginon-importer.form.ifDoSubtasks', { ns: 'leginon-import' })}
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
                        label={t('leginon-importer.form.copyImages', { ns: 'leginon-import' })}
                    />
                </Grid>

                <Grid size={9}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.leginonMysqlHost', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_host')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={3}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.leginonMysqlPort', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            type="number"
                            {...register('leginon_mysql_port')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.leginonMysqlDb', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_db')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.leginonMysqlUser', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_user')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.leginonMysqlPass', { ns: 'leginon-import' })}
                            variant="filled"
                            margin="dense"
                            type="password"
                            {...register('leginon_mysql_pass')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label="Replace Type"
                            variant="filled"
                            margin="dense"
                            {...register('replace_type')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label="Replace Pattern"
                            variant="filled"
                            margin="dense"
                            {...register('replace_pattern')}
                        />
                    </FormControl>
                </Grid>

                <Grid size={12}>
                    <FormControl fullWidth>
                        <TextField
                            label="Replace With"
                            variant="filled"
                            margin="dense"
                            {...register('replace_with')}
                        />
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
                            {defectsFile ? defectsFile.name : 'Defects File (Optional)'}
                            <input
                                type="file"
                                hidden
                                accept=".txt"
                                onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) {
                                        setDefectsFile(file);
                                    }
                                }}
                            />
                        </Button>
                        {defectsFile && (
                            <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5 }}>
                                Selected: {defectsFile.name}
                            </Typography>
                        )}
                    </FormControl>
                </Grid>

                <Grid size={12}>
                    <Button
                        variant="contained"
                        color="primary"
                        type="submit"
                        disabled={isSubmitting}
                        sx={{ mr: 2 }}
                    >
                        {isSubmitting
                            ? t('global.loading', { ns: 'global' })
                            : t('entity.action.import', { ns: 'global' })}
                    </Button>
                </Grid>
            </Grid>
        </form>
    );
};