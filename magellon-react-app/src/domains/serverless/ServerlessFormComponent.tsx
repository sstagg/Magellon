import React, {SyntheticEvent, useState} from "react";
import Container from "@mui/material/Container";
import {
    Button,
    ButtonGroup,
    Checkbox,
    FormControl,
    FormControlLabel,
    FormLabel,
    Grid,
    InputAdornment,
    InputLabel, MenuItem, Select,
    TextField,
    Typography
} from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import {Cached, CalendarMonthOutlined, ControlPoint, HighlightOff, Palette, Straighten} from "@mui/icons-material";
import IServerlessCode from "./Serverless.Model.ts";
import Editor from '@monaco-editor/react';
import TabContext from "@mui/lab/TabContext";
import Box from "@mui/material/Box";
import TabList from "@mui/lab/TabList";
import Tab from "@mui/material/Tab";
import TabPanel from "@mui/lab/TabPanel";
import IconButton from "@mui/material/IconButton";


export const ServerlessFormComponent = () => {
    const [tabValue, setTabValue] = useState('1');
    const { lang, id } = useParams();
    const { handleSubmit, register, setError, setValue, formState: { errors, isValid } } = useForm<IServerlessCode>({
        mode: 'onChange',
    });
    const { t, i18n } = useTranslation(['serverless-code', 'global']);

    const handleChange = (event: SyntheticEvent, newValue: string) => {
        setTabValue(newValue);
    };

    const OnFormSubmit = (data) => {
        // Example: axios.post('/api/yourEndpoint', data);
    }

    return (
        <Container>
            <form onSubmit={handleSubmit(OnFormSubmit)}>
                <Grid container rowSpacing={1} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                    <Grid item xs={12}>
                        <Typography variant="h4">{t('serverless-code.app.title', { ns: 'serverless-code' })}</Typography>
                        <Typography>{t('serverless-code.app.description', { ns: 'serverless-code' })}</Typography>
                    </Grid>

                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <TextField
                                label={t('serverless-code.form.name', { ns: 'serverless-code' })}
                                variant="filled"
                                margin="dense"
                                {...register('name', { required: 'Name is required' })}
                                error={!!errors.name}
                                helperText={errors.name && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                            />
                        </FormControl>
                    </Grid>

                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <TextField
                                label={t('serverless-code.form.alias', { ns: 'serverless-code' })}
                                variant="filled"
                                margin="dense"
                                {...register('alias')}
                                error={!!errors.alias}
                                helperText={errors.alias && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                            />
                        </FormControl>
                    </Grid>
                    <Grid item xs={4}>
                        <FormControl fullWidth>

                            <InputLabel id="demo-simple-select-standard-label">Runtime</InputLabel>
                            <Select
                                labelId="demo-simple-select-standard-label"
                                id="demo-simple-select-standard"
                                variant="filled"
                                margin="dense"
                                value={1}
                                {...register('runtime_id')}
                                error={!!errors.runtime_id}
                                label={t('serverless-code.form.runtimeId', { ns: 'serverless-code' })}
                            >
                                <MenuItem value="">
                                    <em>None</em>
                                </MenuItem>
                                <MenuItem value={1}>Python 3.6</MenuItem>
                                <MenuItem value={2}>Python 2.7</MenuItem>
                                <MenuItem value={3}>Java</MenuItem>
                            </Select>

                        </FormControl>
                    </Grid>

                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <TextField
                                label={t('serverless-code.form.author', { ns: 'serverless-code' })}
                                variant="filled"
                                margin="dense"
                                {...register('author')}
                                error={!!errors.author}
                                helperText={errors.author && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                            />
                        </FormControl>
                    </Grid>

                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <InputLabel id="demo-simple-select-standard-label">Status</InputLabel>
                            <Select
                                labelId="demo-simple-select-standard-label"
                                id="demo-simple-select-standard"
                                variant="filled"
                                margin="dense"
                                value={2}
                                {...register('status_id')}
                                error={!!errors.status_id}
                                label={t('serverless-code.form.statusId', { ns: 'serverless-code' })}
                            >
                                <MenuItem value={1}>Draft</MenuItem>
                                <MenuItem value={2}>Active</MenuItem>
                                <MenuItem value={3}>InActive</MenuItem>
                            </Select>

                        </FormControl>
                    </Grid>
                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <TextField
                                label={t('serverless-code.form.version', { ns: 'serverless-code' })}
                                variant="filled"
                                margin="dense"
                                {...register('version')}
                                error={!!errors.version}
                                helperText={errors.version && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                            />
                        </FormControl>
                    </Grid>

                    <Grid item xs={12}>
                        <TabContext value={tabValue}>
                            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                                <TabList onChange={handleChange}  aria-label="lab API tabs example">
                                    <Tab label="Code" value="1" />
                                    <Tab label={t('serverless-code.form.requirements', { ns: 'serverless-code' })} value="2" />
                                    <Tab label={t('serverless-code.form.description', { ns: 'serverless-code' })} value="3" />
                                    <Tab label={t('serverless-code.form.copyright', { ns: 'serverless-code' })} value="4" />
                                </TabList>
                            </Box>
                            <TabPanel value="1">
                                <FormControl fullWidth>
                                    <Editor height="50vh" {...register('code')} theme="vs-dark" defaultLanguage="python" defaultValue="# Type your code here" />
                                </FormControl>
                            </TabPanel>

                            <TabPanel value="2">
                                <FormControl fullWidth>
                                    <TextField
                                        label={t('serverless-code.form.requirements', { ns: 'serverless-code' })}
                                        variant="filled"
                                        margin="dense"
                                        {...register('requirements')}
                                        error={!!errors.requirements}
                                        helperText={errors.requirements && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                                    />
                                </FormControl>
                            </TabPanel>

                            <TabPanel value="3">
                                <FormControl fullWidth>
                                    <TextField
                                        label={t('serverless-code.form.description', { ns: 'serverless-code' })}
                                        variant="filled"
                                        margin="dense"
                                        {...register('description')}
                                        error={!!errors.description}
                                        helperText={errors.description && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                                    />
                                </FormControl>
                            </TabPanel>

                            <TabPanel value="4">
                                <FormControl fullWidth>
                                    <TextField
                                        label={t('serverless-code.form.copyright', { ns: 'serverless-code' })}
                                        variant="filled"
                                        margin="dense"
                                        {...register('copyright')}
                                        error={!!errors.copyright}
                                        helperText={errors.copyright && t('serverless-code.form.requiredFieldError', { ns: 'serverless-code' })}
                                    />
                                </FormControl>
                            </TabPanel>
                        </TabContext>
                    </Grid>



                    <Grid item xs={6}>
                        <Button variant="contained" color="primary" type="submit"> {t('entity.action.save', { ns: 'global' })} </Button>
                        <Link to={-1}>  {t('entity.action.back', { ns: 'global' })}</Link>
                    </Grid>
                </Grid>
            </form>
        </Container>
    );
};
