import React from 'react';
import {
    Box,
    Container,
    Typography,
    Paper,
    FormControl,
    FormLabel,
    RadioGroup,
    FormControlLabel,
    Radio,
    Divider,
    Stack,
    useTheme
} from '@mui/material';
import { Moon, Sun } from 'lucide-react';
import { useThemeContext } from '../../../themes';
import ThemeDemo from '../components/ThemeDemo';

const SettingsView = () => {
    const { themeName, setTheme } = useThemeContext();
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';

    const handleThemeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setTheme(event.target.value as 'dark' | 'light');
    };

    return (
        <Container maxWidth="lg">
            <Box sx={{ mt: 4, mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Application Settings
                </Typography>
                <Typography variant="body1" paragraph>
                    Configure your application preferences here.
                </Typography>

                <Paper
                    sx={{
                        p: 3,
                        mt: 3,
                        mb: 4,
                        borderLeft: '4px solid',
                        borderLeftColor: 'primary.main'
                    }}
                >
                    <Typography variant="h5" component="h2" gutterBottom>
                        Theme Settings
                    </Typography>
                    <Divider sx={{ mb: 2 }} />

                    <FormControl component="fieldset">
                        <FormLabel component="legend">Theme Mode</FormLabel>
                        <RadioGroup
                            aria-label="theme"
                            name="theme-mode"
                            value={themeName}
                            onChange={handleThemeChange}
                        >
                            <Stack direction="row" spacing={2}>
                                <Paper
                                    elevation={themeName === 'light' ? 3 : 1}
                                    sx={{
                                        p: 2,
                                        borderRadius: 2,
                                        border: '1px solid',
                                        borderColor: themeName === 'light'
                                            ? 'primary.main'
                                            : isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
                                        width: 200
                                    }}
                                >
                                    <FormControlLabel
                                        value="light"
                                        control={<Radio />}
                                        label={
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Sun size={16} />
                                                <Typography>Light Mode</Typography>
                                            </Stack>
                                        }
                                    />
                                    <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                                        Light interface with dark navigation
                                    </Typography>
                                </Paper>

                                <Paper
                                    elevation={themeName === 'dark' ? 3 : 1}
                                    sx={{
                                        p: 2,
                                        borderRadius: 2,
                                        border: '1px solid',
                                        borderColor: themeName === 'dark'
                                            ? 'primary.main'
                                            : isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
                                        width: 200
                                    }}
                                >
                                    <FormControlLabel
                                        value="dark"
                                        control={<Radio />}
                                        label={
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Moon size={16} />
                                                <Typography>Dark Mode</Typography>
                                            </Stack>
                                        }
                                    />
                                    <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                                        Full dark interface
                                    </Typography>
                                </Paper>
                            </Stack>
                        </RadioGroup>
                    </FormControl>
                </Paper>

                <Paper
                    sx={{
                        p: 3,
                        borderLeft: '4px solid',
                        borderLeftColor: 'secondary.main'
                    }}
                >
                    <Typography variant="h5" component="h2" gutterBottom>
                        Theme Preview
                    </Typography>
                    <Divider sx={{ mb: 2 }} />
                    <ThemeDemo />
                </Paper>
            </Box>
        </Container>
    );
};

export default SettingsView;