import React, { useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Stack,
    Tab,
    Tabs,
    TextField,
    Typography,
} from '@mui/material';
import { Plus, Upload, X } from 'lucide-react';
import {
    useInstallPlugin,
    useInstallPluginArchive,
    type InstallVolume,
} from '../api/PluginApi.ts';

type InstallMode = 'image' | 'archive';

interface InstallPluginDialogProps {
    open: boolean;
    onClose: () => void;
}

interface EnvRow {
    key: string;
    value: string;
}

/**
 * Minimal install dialog — the operator supplies what ``docker run``
 * needs (image ref, env, volumes, network) and CoreService spawns the
 * container. Config *inside* the plugin (queue names, RMQ credentials)
 * still comes from the image's baked-in settings YAML; this dialog
 * doesn't try to patch that surface.
 */
export const InstallPluginDialog: React.FC<InstallPluginDialogProps> = ({ open, onClose }) => {
    const install = useInstallPlugin();
    const installArchive = useInstallPluginArchive();
    const [mode, setMode] = useState<InstallMode>('image');
    const [imageRef, setImageRef] = useState('');
    const [network, setNetwork] = useState('');
    const [envRows, setEnvRows] = useState<EnvRow[]>([]);
    const [volumes, setVolumes] = useState<InstallVolume[]>([]);
    const [archive, setArchive] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const archiveInputRef = useRef<HTMLInputElement | null>(null);

    const busy = install.isLoading || installArchive.isLoading;

    const reset = () => {
        setMode('image');
        setImageRef('');
        setNetwork('');
        setEnvRows([]);
        setVolumes([]);
        setArchive(null);
        setError(null);
    };

    const handleClose = () => {
        if (busy) return;
        reset();
        onClose();
    };

    const handleSubmit = async () => {
        setError(null);
        try {
            if (mode === 'archive') {
                if (!archive) {
                    setError('Select a .magplugin archive to upload.');
                    return;
                }
                await installArchive.mutateAsync(archive);
            } else {
                if (!imageRef.trim()) {
                    setError('Image ref is required.');
                    return;
                }
                const env: Record<string, string> = {};
                for (const row of envRows) {
                    if (row.key.trim()) env[row.key.trim()] = row.value;
                }
                await install.mutateAsync({
                    image_ref: imageRef.trim(),
                    env,
                    volumes,
                    network: network.trim() || null,
                });
            }
            reset();
            onClose();
        } catch (err: any) {
            setError(err?.response?.data?.detail ?? err?.message ?? 'Install failed.');
        }
    };

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
            <DialogTitle>Install plugin</DialogTitle>
            <DialogContent dividers>
                <Tabs
                    value={mode}
                    onChange={(_, v: InstallMode) => {
                        setMode(v);
                        setError(null);
                    }}
                    sx={{ mb: 2 }}
                >
                    <Tab value="image" label="From image ref" />
                    <Tab value="archive" label="From archive (.magplugin)" />
                </Tabs>

                {mode === 'archive' ? (
                    <Stack spacing={2}>
                        <Alert severity="info">
                            Upload a <code>.magplugin</code> archive produced by{' '}
                            <code>magellon-sdk plugin pack &lt;dir&gt;</code>. The archive's
                            manifest supplies the image ref, env, volumes, and network
                            automatically.
                        </Alert>
                        <input
                            ref={archiveInputRef}
                            type="file"
                            accept=".magplugin,.zip"
                            style={{ display: 'none' }}
                            onChange={(e) => setArchive(e.target.files?.[0] ?? null)}
                        />
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Button
                                variant="outlined"
                                startIcon={<Upload size={16} />}
                                onClick={() => archiveInputRef.current?.click()}
                            >
                                Choose archive
                            </Button>
                            <Typography variant="body2" color="text.secondary">
                                {archive ? archive.name : 'No file selected.'}
                            </Typography>
                        </Stack>
                        {error && <Alert severity="error">{error}</Alert>}
                    </Stack>
                ) : (
                <Stack spacing={2}>
                    <TextField
                        label="Docker image ref"
                        placeholder="ghcr.io/org/plugin:tag"
                        value={imageRef}
                        onChange={(e) => setImageRef(e.target.value)}
                        required
                        fullWidth
                        autoFocus
                    />
                    <TextField
                        label="Docker network (optional)"
                        placeholder="magellon_default"
                        helperText="Network RMQ is on so the plugin can reach it by hostname."
                        value={network}
                        onChange={(e) => setNetwork(e.target.value)}
                        fullWidth
                    />

                    <Box>
                        <Stack direction="row" alignItems="center" justifyContent="space-between">
                            <Typography variant="subtitle2">Environment variables</Typography>
                            <Button
                                size="small"
                                startIcon={<Plus size={16} />}
                                onClick={() => setEnvRows((r) => [...r, { key: '', value: '' }])}
                            >
                                Add
                            </Button>
                        </Stack>
                        {envRows.length === 0 && (
                            <Typography variant="caption" color="text.secondary">
                                None. Add entries if the image needs runtime overrides.
                            </Typography>
                        )}
                        <Stack spacing={1} sx={{ mt: 1 }}>
                            {envRows.map((row, idx) => (
                                <Stack key={idx} direction="row" spacing={1}>
                                    <TextField
                                        label="KEY"
                                        value={row.key}
                                        onChange={(e) => {
                                            const copy = [...envRows];
                                            copy[idx] = { ...copy[idx], key: e.target.value };
                                            setEnvRows(copy);
                                        }}
                                        size="small"
                                        sx={{ flex: 1 }}
                                    />
                                    <TextField
                                        label="value"
                                        value={row.value}
                                        onChange={(e) => {
                                            const copy = [...envRows];
                                            copy[idx] = { ...copy[idx], value: e.target.value };
                                            setEnvRows(copy);
                                        }}
                                        size="small"
                                        sx={{ flex: 2 }}
                                    />
                                    <IconButton
                                        size="small"
                                        aria-label="remove env row"
                                        onClick={() => setEnvRows((r) => r.filter((_, i) => i !== idx))}
                                    >
                                        <X size={16} />
                                    </IconButton>
                                </Stack>
                            ))}
                        </Stack>
                    </Box>

                    <Box>
                        <Stack direction="row" alignItems="center" justifyContent="space-between">
                            <Typography variant="subtitle2">Volume mounts</Typography>
                            <Button
                                size="small"
                                startIcon={<Plus size={16} />}
                                onClick={() =>
                                    setVolumes((v) => [
                                        ...v,
                                        { host_path: '', container_path: '', read_only: false },
                                    ])
                                }
                            >
                                Add
                            </Button>
                        </Stack>
                        {volumes.length === 0 && (
                            <Typography variant="caption" color="text.secondary">
                                None. Plugin images typically mount /gpfs and /jobs.
                            </Typography>
                        )}
                        <Stack spacing={1} sx={{ mt: 1 }}>
                            {volumes.map((vol, idx) => (
                                <Stack key={idx} direction="row" spacing={1}>
                                    <TextField
                                        label="host path"
                                        value={vol.host_path}
                                        onChange={(e) => {
                                            const copy = [...volumes];
                                            copy[idx] = { ...copy[idx], host_path: e.target.value };
                                            setVolumes(copy);
                                        }}
                                        size="small"
                                        sx={{ flex: 1 }}
                                    />
                                    <TextField
                                        label="container path"
                                        value={vol.container_path}
                                        onChange={(e) => {
                                            const copy = [...volumes];
                                            copy[idx] = { ...copy[idx], container_path: e.target.value };
                                            setVolumes(copy);
                                        }}
                                        size="small"
                                        sx={{ flex: 1 }}
                                    />
                                    <IconButton
                                        size="small"
                                        aria-label="remove volume"
                                        onClick={() => setVolumes((v) => v.filter((_, i) => i !== idx))}
                                    >
                                        <X size={16} />
                                    </IconButton>
                                </Stack>
                            ))}
                        </Stack>
                    </Box>

                    {error && <Alert severity="error">{error}</Alert>}
                </Stack>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={busy}>
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={
                        busy ||
                        (mode === 'image' && !imageRef.trim()) ||
                        (mode === 'archive' && !archive)
                    }
                >
                    {busy ? 'Installing…' : 'Install'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
