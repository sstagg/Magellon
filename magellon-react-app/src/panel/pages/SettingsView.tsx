import React, { useState } from 'react';
import {
    Box,
    Container,
    Paper,
    Typography,
    Tabs,
    Tab,
    Switch,
    FormControlLabel,
    FormControl,
    FormLabel,
    RadioGroup,
    Radio,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Button,
    Divider,
    Grid,
    Slider,
    Alert,
    Card,
    CardContent,
    CardHeader,
    InputAdornment,
    IconButton,
    Tooltip,
    Stack,
    useTheme
} from '@mui/material';
import {
    Palette,
    Storage,
    Security,
    Notifications,
    Language,
    Science,
    Download,
    Upload,
    Save,
    RestoreFromTrash,
    Speed,
    FolderOpen,
    BugReport
} from '@mui/icons-material';
import { Moon, Sun } from 'lucide-react';
import { useThemeContext } from '../../themes';
import ThemeDemo from '../components/ThemeDemo.tsx';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`settings-tabpanel-${index}`}
            aria-labelledby={`settings-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
        </div>
    );
}

const SettingsView = () => {
    const { themeName, setTheme } = useThemeContext();
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';

    const [currentTab, setCurrentTab] = useState(0);
    const [settings, setSettings] = useState({
        // Display & Performance
        thumbnailSize: 150,
        cacheSize: 1000,
        maxConcurrentLoads: 5,
        autoRefreshInterval: 30,
        enableHardwareAcceleration: true,

        // Data Management
        defaultImportPath: '/gpfs',
        autoBackup: true,
        backupInterval: 24,
        dataRetentionPeriod: 30,
        compressionEnabled: true,

        // Import/Export
        copyImagesOnImport: true,
        validateImportsOnLoad: true,
        defaultSessionNaming: 'timestamp',
        enableSubtasks: true,
        maxRetries: 3,

        // Processing
        defaultProcessingPipeline: 'standard',
        maxParallelJobs: 4,
        autoStartProcessing: false,
        notifyOnCompletion: true,

        // Security & Privacy
        sessionTimeout: 60,
        enableAuditLog: true,
        requireConfirmationForDelete: true,
        encryptSensitiveData: true,

        // Notifications
        enableNotifications: true,
        notifyOnImportComplete: true,
        notifyOnErrors: true,
        soundEnabled: false,

        // Advanced
        debugMode: false,
        enableBetaFeatures: false,
        logLevel: 'info',
        apiTimeout: 30
    });

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    const handleThemeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setTheme(event.target.value as 'dark' | 'light');
    };

    const handleSettingChange = (key: string, value: any) => {
        setSettings(prev => ({
            ...prev,
            [key]: value
        }));
    };

    const handleSaveSettings = () => {
        console.log('Saving settings:', settings);
    };

    const handleResetSettings = () => {
        console.log('Resetting settings to defaults');
    };

    const tabs = [
        { label: 'Appearance', icon: <Palette /> },
        { label: 'Display & Performance', icon: <Speed /> },
        { label: 'Data Management', icon: <Storage /> },
        { label: 'Import/Export', icon: <Upload /> },
        { label: 'Processing', icon: <Science /> },
        { label: 'Security', icon: <Security /> },
        { label: 'Notifications', icon: <Notifications /> },
        { label: 'Advanced', icon: <BugReport /> }
    ];

    return (
        <Container maxWidth="lg">
            <Box sx={{ mt: 4, mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Application Settings
                </Typography>
                <Typography variant="body1" paragraph>
                    Configure Magellon to match your workflow and preferences
                </Typography>

                {/* Settings Content */}
                <Box sx={{ mt: 3, display: 'flex' }}>
                    {/* Tabs */}
                    <Paper sx={{ width: 280, mr: 2 }}>
                        <Tabs
                            orientation="vertical"
                            variant="scrollable"
                            value={currentTab}
                            onChange={handleTabChange}
                            sx={{ borderRight: 1, borderColor: 'divider' }}
                        >
                            {tabs.map((tab, index) => (
                                <Tab
                                    key={index}
                                    icon={tab.icon}
                                    label={tab.label}
                                    iconPosition="start"
                                    sx={{ justifyContent: 'flex-start', minHeight: 48 }}
                                />
                            ))}
                        </Tabs>
                    </Paper>

                    {/* Tab Content */}
                    <Box sx={{ flexGrow: 1 }}>
                        {/* Appearance Tab */}
                        <TabPanel value={currentTab} index={0}>
                            <Paper
                                sx={{
                                    p: 3,
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
                                    mt: 3,
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
                        </TabPanel>

                        {/* Display & Performance Tab */}
                        <TabPanel value={currentTab} index={1}>
                            <Card>
                                <CardHeader title="Display Settings" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12}>
                                            <Typography gutterBottom>Thumbnail Size: {settings.thumbnailSize}px</Typography>
                                            <Slider
                                                value={settings.thumbnailSize}
                                                onChange={(_, value) => handleSettingChange('thumbnailSize', value)}
                                                min={100}
                                                max={300}
                                                step={25}
                                                marks
                                                valueLabelDisplay="auto"
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Cache Size (MB)"
                                                type="number"
                                                value={settings.cacheSize}
                                                onChange={(e) => handleSettingChange('cacheSize', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Max Concurrent Image Loads"
                                                type="number"
                                                value={settings.maxConcurrentLoads}
                                                onChange={(e) => handleSettingChange('maxConcurrentLoads', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.enableHardwareAcceleration}
                                                        onChange={(e) => handleSettingChange('enableHardwareAcceleration', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Hardware Acceleration"
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Data Management Tab */}
                        <TabPanel value={currentTab} index={2}>
                            <Card>
                                <CardHeader title="Data Storage & Backup" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12}>
                                            <TextField
                                                fullWidth
                                                label="Default Import Path"
                                                value={settings.defaultImportPath}
                                                onChange={(e) => handleSettingChange('defaultImportPath', e.target.value)}
                                                InputProps={{
                                                    endAdornment: (
                                                        <InputAdornment position="end">
                                                            <IconButton>
                                                                <FolderOpen />
                                                            </IconButton>
                                                        </InputAdornment>
                                                    )
                                                }}
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.autoBackup}
                                                        onChange={(e) => handleSettingChange('autoBackup', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Automatic Backups"
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Backup Interval (hours)"
                                                type="number"
                                                value={settings.backupInterval}
                                                onChange={(e) => handleSettingChange('backupInterval', parseInt(e.target.value))}
                                                disabled={!settings.autoBackup}
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Data Retention (days)"
                                                type="number"
                                                value={settings.dataRetentionPeriod}
                                                onChange={(e) => handleSettingChange('dataRetentionPeriod', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Import/Export Tab */}
                        <TabPanel value={currentTab} index={3}>
                            <Card>
                                <CardHeader title="Import/Export Settings" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.copyImagesOnImport}
                                                        onChange={(e) => handleSettingChange('copyImagesOnImport', e.target.checked)}
                                                    />
                                                }
                                                label="Copy Images on Import (vs. Reference)"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.validateImportsOnLoad}
                                                        onChange={(e) => handleSettingChange('validateImportsOnLoad', e.target.checked)}
                                                    />
                                                }
                                                label="Validate Imports on Load"
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <FormControl fullWidth>
                                                <InputLabel>Default Session Naming</InputLabel>
                                                <Select
                                                    value={settings.defaultSessionNaming}
                                                    onChange={(e) => handleSettingChange('defaultSessionNaming', e.target.value)}
                                                >
                                                    <MenuItem value="timestamp">Timestamp</MenuItem>
                                                    <MenuItem value="custom">Custom</MenuItem>
                                                    <MenuItem value="original">Original Name</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Max Import Retries"
                                                type="number"
                                                value={settings.maxRetries}
                                                onChange={(e) => handleSettingChange('maxRetries', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Processing Tab */}
                        <TabPanel value={currentTab} index={4}>
                            <Card>
                                <CardHeader title="Processing Configuration" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12} md={6}>
                                            <FormControl fullWidth>
                                                <InputLabel>Default Processing Pipeline</InputLabel>
                                                <Select
                                                    value={settings.defaultProcessingPipeline}
                                                    onChange={(e) => handleSettingChange('defaultProcessingPipeline', e.target.value)}
                                                >
                                                    <MenuItem value="standard">Standard</MenuItem>
                                                    <MenuItem value="fast">Fast</MenuItem>
                                                    <MenuItem value="high-quality">High Quality</MenuItem>
                                                    <MenuItem value="custom">Custom</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Max Parallel Jobs"
                                                type="number"
                                                value={settings.maxParallelJobs}
                                                onChange={(e) => handleSettingChange('maxParallelJobs', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.autoStartProcessing}
                                                        onChange={(e) => handleSettingChange('autoStartProcessing', e.target.checked)}
                                                    />
                                                }
                                                label="Auto-start Processing on Import"
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Security Tab */}
                        <TabPanel value={currentTab} index={5}>
                            <Card>
                                <CardHeader title="Security & Privacy" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="Session Timeout (minutes)"
                                                type="number"
                                                value={settings.sessionTimeout}
                                                onChange={(e) => handleSettingChange('sessionTimeout', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.enableAuditLog}
                                                        onChange={(e) => handleSettingChange('enableAuditLog', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Audit Logging"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.requireConfirmationForDelete}
                                                        onChange={(e) => handleSettingChange('requireConfirmationForDelete', e.target.checked)}
                                                    />
                                                }
                                                label="Require Confirmation for Deletions"
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Notifications Tab */}
                        <TabPanel value={currentTab} index={6}>
                            <Card>
                                <CardHeader title="Notification Preferences" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.enableNotifications}
                                                        onChange={(e) => handleSettingChange('enableNotifications', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Notifications"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.notifyOnImportComplete}
                                                        onChange={(e) => handleSettingChange('notifyOnImportComplete', e.target.checked)}
                                                        disabled={!settings.enableNotifications}
                                                    />
                                                }
                                                label="Notify on Import Completion"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.notifyOnErrors}
                                                        onChange={(e) => handleSettingChange('notifyOnErrors', e.target.checked)}
                                                        disabled={!settings.enableNotifications}
                                                    />
                                                }
                                                label="Notify on Errors"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.soundEnabled}
                                                        onChange={(e) => handleSettingChange('soundEnabled', e.target.checked)}
                                                        disabled={!settings.enableNotifications}
                                                    />
                                                }
                                                label="Enable Sound Notifications"
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>

                        {/* Advanced Tab */}
                        <TabPanel value={currentTab} index={7}>
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                Advanced settings can affect application performance and stability.
                                Modify only if you understand the implications.
                            </Alert>
                            <Card>
                                <CardHeader title="Advanced Configuration" />
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.debugMode}
                                                        onChange={(e) => handleSettingChange('debugMode', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Debug Mode"
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <FormControlLabel
                                                control={
                                                    <Switch
                                                        checked={settings.enableBetaFeatures}
                                                        onChange={(e) => handleSettingChange('enableBetaFeatures', e.target.checked)}
                                                    />
                                                }
                                                label="Enable Beta Features"
                                            />
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <FormControl fullWidth>
                                                <InputLabel>Log Level</InputLabel>
                                                <Select
                                                    value={settings.logLevel}
                                                    onChange={(e) => handleSettingChange('logLevel', e.target.value)}
                                                >
                                                    <MenuItem value="error">Error</MenuItem>
                                                    <MenuItem value="warn">Warning</MenuItem>
                                                    <MenuItem value="info">Info</MenuItem>
                                                    <MenuItem value="debug">Debug</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <TextField
                                                fullWidth
                                                label="API Timeout (seconds)"
                                                type="number"
                                                value={settings.apiTimeout}
                                                onChange={(e) => handleSettingChange('apiTimeout', parseInt(e.target.value))}
                                            />
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        </TabPanel>
                    </Box>
                </Box>

                {/* Action Buttons */}
                <Paper sx={{ p: 2, mt: 2, display: 'flex', justifyContent: 'space-between' }}>
                    <Button
                        variant="outlined"
                        startIcon={<RestoreFromTrash />}
                        onClick={handleResetSettings}
                        color="warning"
                    >
                        Reset to Defaults
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<Save />}
                        onClick={handleSaveSettings}
                        color="primary"
                    >
                        Save Settings
                    </Button>
                </Paper>
            </Box>
        </Container>
    );
};

export default SettingsView;