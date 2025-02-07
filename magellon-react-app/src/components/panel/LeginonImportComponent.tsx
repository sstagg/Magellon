import Container from "@mui/material/Container";
import {Button, Checkbox, FormControl, FormControlLabel, FormLabel,  InputAdornment, TextField, Typography} from "@mui/material";
import {Link, useParams} from "react-router-dom";
import React from "react";
import {useForm} from "react-hook-form";
import {useTranslation} from "react-i18next";
import {Cached, CalendarMonthOutlined} from "@mui/icons-material";
import Grid from '@mui/material/Grid2';


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
}

export const LeginonImportComponent = () => {
    const { handleSubmit, register, formState: { errors } } = useForm<ILeginonImportForm>({
        mode: 'onChange',
    });
    const { t } = useTranslation(['leginon-import', 'global'], { useSuspense: false });

    const onFormSubmit = async (data: ILeginonImportForm) => {
        try {
            console.log(data);
            // Implement your form submission logic here
        } catch (error) {
            console.error("There was an error submitting the form!", error);
        }
    };

    return (
        <form onSubmit={handleSubmit(onFormSubmit)}>
            <Grid container spacing={2}>
                <Grid  size={12}>
                    <Typography variant="h6">
                        {t('leginon-importer.app.title', { ns: 'leginon-import' })}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        {t('leginon-importer.app.description', { ns: 'leginon-import' })}
                    </Typography>
                </Grid>

                <Grid  size={12}>
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

                <Grid  size={6}>
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
                            error={!!errors.magellon_session_name}
                            helperText={errors.magellon_session_name?.message}
                        />
                    </FormControl>
                </Grid>
                <Grid  size={6}>
                    <FormControl fullWidth>
                        <TextField
                            label={t('leginon-importer.form.sessionName', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            {...register('session_name')}
                            error={!!errors.session_name}
                            helperText={
                                errors.session_name &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>
                <Grid  size={6}>
                    <FormControl fullWidth>
                        {/*<FormLabel>*/}
                        {/*    {t('leginon-importer.form.cameraDirectory', {*/}
                        {/*        ns: 'leginon-import',*/}
                        {/*    })}*/}
                        {/*</FormLabel>*/}
                        <TextField
                            label={t('leginon-importer.form.cameraDirectory', {   ns: 'leginon-import',  })}
                            variant="filled"
                            margin="dense"
                            type="file"
                            webkitdirectory=""
                            {...register('camera_directory')}
                            error={!!errors.camera_directory}
                            helperText={
                                errors.camera_directory &&
                                t('leginon-importer.form.requiredFieldError', {  ns: 'leginon-import',   })
                            }
                        />
                    </FormControl>
                </Grid>
                <Grid  size={6}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.retries', {
                                ns: 'leginon-import',
                            })}
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
                            error={!!errors.retries}
                            helperText={
                                errors.retries &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>
                <Grid  size={6}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                {...register('if_do_subtasks')}
                                defaultChecked={false}
                                color="primary"
                            />
                        }
                        label={t('leginon-importer.form.ifDoSubtasks', { ns: 'leginon-import' })}
                    />
                </Grid>
                <Grid  size={6}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                {...register('copy_images')}
                                defaultChecked={false}
                                color="primary"
                            />
                        }
                        label={t('leginon-importer.form.copyImages', {
                            ns: 'leginon-import',
                        })}
                    />
                </Grid>



                <Grid  size={9}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.leginonMysqlHost', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_host')}
                            error={!!errors.leginon_mysql_host}
                            helperText={
                                errors.leginon_mysql_host &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>

                <Grid  size={3}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.leginonMysqlPort', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            type="number"
                            {...register('leginon_mysql_port')}
                            error={!!errors.leginon_mysql_port}
                            helperText={
                                errors.leginon_mysql_port &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>

                <Grid  size={12}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.leginonMysqlDb', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_db')}
                            error={!!errors.leginon_mysql_db}
                            helperText={
                                errors.leginon_mysql_db &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>

                <Grid  size={6}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.leginonMysqlUser', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            {...register('leginon_mysql_user')}
                            error={!!errors.leginon_mysql_user}
                            helperText={
                                errors.leginon_mysql_user &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>

                <Grid  size={6}>
                    <FormControl fullWidth>

                        <TextField
                            label={t('leginon-importer.form.leginonMysqlPass', {
                                ns: 'leginon-import',
                            })}
                            variant="filled"
                            margin="dense"
                            type="password"
                            {...register('leginon_mysql_pass')}
                            error={!!errors.leginon_mysql_pass}
                            helperText={
                                errors.leginon_mysql_pass &&
                                t('leginon-importer.form.requiredFieldError', {
                                    ns: 'leginon-import',
                                })
                            }
                        />
                    </FormControl>
                </Grid>

                <Grid  size={12}>
                    <Button
                        variant="contained"
                        color="primary"
                        type="submit"
                        sx={{ mr: 2 }}
                    >
                        {t('entity.action.import', { ns: 'global' })}
                    </Button>
                </Grid>
            </Grid>
        </form>
    );
};

// export default LeginonImportComponent;