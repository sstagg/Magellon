import React from 'react';
import {
    Box,
    Typography,
    Paper,
    Button,
    Chip,
    Divider,
    TextField,
    Switch,
    FormControlLabel,
    Stack,
    Grid,
    Card,
    CardContent,
    CardActions,
    Alert,
    useTheme
} from '@mui/material';
import { useThemeContext } from '../../../themes';


const ThemeDemo = () => {
    const { themeName } = useThemeContext();
    const theme = useTheme();

    return (
        <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h5" gutterBottom>
                Theme Preview - {themeName.charAt(0).toUpperCase() + themeName.slice(1)} Mode
            </Typography>
            <Divider sx={{ mb: 3 }} />

            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Typography</Typography>
                    <Box sx={{ mb: 3 }}>
                        <Typography variant="h1">Heading 1</Typography>
                        <Typography variant="h2">Heading 2</Typography>
                        <Typography variant="h3">Heading 3</Typography>
                        <Typography variant="h4">Heading 4</Typography>
                        <Typography variant="h5">Heading 5</Typography>
                        <Typography variant="h6">Heading 6</Typography>
                        <Typography variant="subtitle1">Subtitle 1</Typography>
                        <Typography variant="subtitle2">Subtitle 2</Typography>
                        <Typography variant="body1">Body 1: Standard text appears like this</Typography>
                        <Typography variant="body2">Body 2: Smaller text appears like this</Typography>
                        <Typography variant="button">BUTTON TEXT</Typography>
                        <Typography variant="caption" display="block">Caption text</Typography>
                        <Typography variant="overline" display="block">OVERLINE TEXT</Typography>
                    </Box>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Colors & Surfaces</Typography>

                    <Stack spacing={2} sx={{ mb: 3 }}>
                        <Paper sx={{ p: 2, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
                            Primary Main Color
                        </Paper>
                        <Paper sx={{ p: 2, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
                            Primary Light Color
                        </Paper>
                        <Paper sx={{ p: 2, bgcolor: 'primary.dark', color: 'primary.contrastText' }}>
                            Primary Dark Color
                        </Paper>
                        <Paper sx={{ p: 2, bgcolor: 'secondary.main', color: 'secondary.contrastText' }}>
                            Secondary Main Color
                        </Paper>
                        <Paper sx={{ p: 2, bgcolor: 'background.default', border: 1, borderColor: 'divider' }}>
                            Background Default Color
                        </Paper>
                        <Paper sx={{ p: 2 }}>
                            Background Paper Color
                        </Paper>
                    </Stack>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Components</Typography>

                    <Box sx={{ mb: 3 }}>
                        <Typography variant="subtitle1" gutterBottom>Buttons</Typography>
                        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                            <Button variant="contained">Contained</Button>
                            <Button variant="outlined">Outlined</Button>
                            <Button variant="text">Text</Button>
                        </Stack>

                        <Typography variant="subtitle1" gutterBottom>Inputs</Typography>
                        <Stack spacing={2} sx={{ mb: 2 }}>
                            <TextField label="Text Field" size="small" />
                            <FormControlLabel control={<Switch />} label="Switch" />
                        </Stack>

                        <Typography variant="subtitle1" gutterBottom>Chips</Typography>
                        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                            <Chip label="Default" />
                            <Chip label="Primary" color="primary" />
                            <Chip label="Secondary" color="secondary" />
                        </Stack>
                    </Box>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Compound Components</Typography>

                    <Card sx={{ mb: 2 }}>
                        <CardContent>
                            <Typography variant="h5" component="div">
                                Card Title
                            </Typography>
                            <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                Subtitle
                            </Typography>
                            <Typography variant="body2">
                                Cards contain content and actions about a single subject.
                            </Typography>
                        </CardContent>
                        <CardActions>
                            <Button size="small">Learn More</Button>
                        </CardActions>
                    </Card>

                    <Alert severity="info" sx={{ mb: 2 }}>
                        This is an information alert — check it out!
                    </Alert>

                    <Alert severity="success" sx={{ mb: 2 }}>
                        This is a success alert — check it out!
                    </Alert>
                </Grid>
            </Grid>
        </Paper>
    );
};

export default ThemeDemo;