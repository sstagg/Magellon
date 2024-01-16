import Container from "@mui/material/Container";
import {Button, Checkbox, FormControl, FormControlLabel, FormLabel, Grid, InputAdornment, TextField, Typography} from "@mui/material";
import {Link, useParams} from "react-router-dom";
import React from "react";
import {useForm} from "react-hook-form";
import {IBlog} from "../../../domains/blog/Blog.Model.ts";
import {useTranslation} from "react-i18next";
import {Cached, CalendarMonthOutlined} from "@mui/icons-material";



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


export const LeginonImportPageView = () => {

    const {lang,id} = useParams();
    const {handleSubmit, register,setError,setValue, formState: {errors, isValid}} = useForm<ILeginonImportForm>({
        mode: 'onChange',
    });
    const { t, i18n } = useTranslation(['leginon-import', 'global']);

    const OnFormSubmit = (data) => {
        // Example: axios.post('/api/yourEndpoint', data);
    }

    return (
        <Container>
            <form onSubmit={handleSubmit(OnFormSubmit)}>


                <Grid container rowSpacing={1} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                    <Grid item xs={12}  >
                        <Typography variant="h4">{t('leginon-importer.app.title',{ ns: 'leginon-import' })}</Typography>
                        <Typography>{t('leginon-importer.app.description',{ ns: 'leginon-import' })}</Typography>
                    </Grid>

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>{t('leginon-importer.form.magellonProjectName',{ ns: 'leginon-import' })}</FormLabel>*/}
                            <TextField
                                label={t('leginon-importer.form.magellonProjectName',{ ns: 'leginon-import' })}
                                variant="filled"
                                margin="dense"

                                {...register('magellon_project_name',{required: 'project name is required'})}
                                error={!!errors.magellon_project_name}
                                helperText={!!errors.magellon_project_name }
                            />
                        </FormControl>
                    </Grid>

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>{t('leginon-importer.form.magellonSessionName',{ ns: 'leginon-import' })}</FormLabel>*/}
                            <TextField
                                label={t('leginon-importer.form.magellonSessionName',{ ns: 'leginon-import' })}
                                variant="filled"
                                margin="dense"
                                InputProps={{
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <CalendarMonthOutlined />
                                        </InputAdornment>
                                    ),
                                }}
                                {...register('magellon_project_name')}
                                error={!!errors.magellon_session_name}
                                helperText={!!errors.magellon_session_name }
                            />
                        </FormControl>
                    </Grid>
                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.sessionName', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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
                    <Grid item xs={8}>
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
                    <Grid item xs={8}>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    {...register('if_do_subtasks')}
                                    defaultChecked={false}
                                    color="primary"
                                />
                            }
                            label={t('leginon-importer.form.ifDoSubtasks', {
                                ns: 'leginon-import',
                            })}
                        />
                    </Grid>
                    <Grid item xs={8}>
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
                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.retries', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.leginonMysqlHost', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.leginonMysqlPort', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.leginonMysqlDb', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.leginonMysqlUser', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            {/*<FormLabel>*/}
                            {/*    {t('leginon-importer.form.leginonMysqlPass', {*/}
                            {/*        ns: 'leginon-import',*/}
                            {/*    })}*/}
                            {/*</FormLabel>*/}
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


                    <Grid item xs={6}>
                        <Button variant="contained" color="primary" type="submit"> {t('entity.action.save', { ns: 'global' })} </Button>
                        <Link to={-1}>  {t('entity.action.back', { ns: 'global' })}</Link>
                        {/*<Button variant="contained" color="secondary"  onClick={()=> navigate(-1)}> Back </Button>*/}
                    </Grid>

                </Grid>

            </form>

        </Container>
    );
};
