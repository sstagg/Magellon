import React, { useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Breadcrumbs,
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    Link,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import { File as FileIcon, Folder as FolderIcon, ArrowUp } from 'lucide-react';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const IMAGE_EXTS = [
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tif', '.tiff',
    '.mrc', '.mrcs', '.map',
];

interface BrowseItem {
    id: number;
    name: string;
    is_directory: boolean;
    path: string;
    size: number | null;
    mime_type: string | null;
}

interface ImagePickerDialogProps {
    open: boolean;
    onClose: () => void;
    onPick: (absolutePath: string) => void;
    initialPath?: string;
}

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

const isImageFile = (name: string) =>
    IMAGE_EXTS.some((ext) => name.toLowerCase().endsWith(ext));

const splitPath = (p: string): string[] => {
    // Handle both POSIX and Windows drive paths.
    const normalized = p.replace(/\\/g, '/');
    const parts = normalized.split('/').filter(Boolean);
    return parts;
};

const parentOf = (p: string): string | null => {
    const normalized = p.replace(/\\/g, '/');
    const idx = normalized.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = normalized.slice(0, idx);
    if (/^[A-Za-z]:$/.test(parent)) return parent + '/';
    return parent || '/';
};

export const ImagePickerDialog: React.FC<ImagePickerDialogProps> = ({
    open,
    onClose,
    onPick,
    initialPath = 'C:/',
}) => {
    const [pathInput, setPathInput] = useState(initialPath);
    const [currentPath, setCurrentPath] = useState(initialPath);
    const [items, setItems] = useState<BrowseItem[]>([]);
    const [selected, setSelected] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchDir = async (path: string) => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get('/web/files/browse', { params: { path } });
            setItems(res.data ?? []);
            setCurrentPath(path);
            setPathInput(path);
            setSelected(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Failed to browse');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) fetchDir(initialPath);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    const handleItemClick = (item: BrowseItem) => {
        if (item.is_directory) {
            fetchDir(item.path);
        } else if (isImageFile(item.name)) {
            setSelected(item.path);
        }
    };

    const handleGoUp = () => {
        const parent = parentOf(currentPath);
        if (parent) fetchDir(parent);
    };

    const handleGoToPath = () => {
        if (pathInput.trim()) fetchDir(pathInput.trim());
    };

    const handleConfirm = () => {
        if (selected) {
            onPick(selected);
            onClose();
        }
    };

    const visible = items.filter((it) => it.is_directory || isImageFile(it.name));
    const parts = splitPath(currentPath);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>Pick test image</DialogTitle>
            <DialogContent dividers>
                <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                    <TextField
                        size="small"
                        fullWidth
                        label="Path"
                        value={pathInput}
                        onChange={(e) => setPathInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleGoToPath();
                        }}
                    />
                    <Button variant="outlined" onClick={handleGoToPath}>Go</Button>
                    <Button
                        variant="outlined"
                        startIcon={<ArrowUp size={14} />}
                        onClick={handleGoUp}
                    >
                        Up
                    </Button>
                </Stack>

                <Breadcrumbs sx={{ mb: 1 }}>
                    <Link component="button" onClick={() => fetchDir('/')}>root</Link>
                    {parts.map((p, i) => (
                        <Link
                            key={i}
                            component="button"
                            onClick={() => {
                                const prefix = /^[A-Za-z]:$/.test(parts[0]) ? '' : '/';
                                fetchDir(prefix + parts.slice(0, i + 1).join('/'));
                            }}
                        >
                            {p}
                        </Link>
                    ))}
                </Breadcrumbs>

                <Divider sx={{ mb: 1 }} />

                {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

                {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                        <CircularProgress size={28} />
                    </Box>
                ) : (
                    <List dense sx={{ maxHeight: 360, overflowY: 'auto' }}>
                        {visible.length === 0 && !error && (
                            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                                No folders or images here.
                            </Typography>
                        )}
                        {visible.map((it) => (
                            <ListItemButton
                                key={it.path}
                                onClick={() => handleItemClick(it)}
                                selected={selected === it.path}
                            >
                                <ListItemIcon>
                                    {it.is_directory ? <FolderIcon size={18} /> : <FileIcon size={18} />}
                                </ListItemIcon>
                                <ListItemText
                                    primary={it.name}
                                    secondary={!it.is_directory && it.size != null ? `${it.size} bytes` : undefined}
                                />
                            </ListItemButton>
                        ))}
                    </List>
                )}

                {selected && (
                    <Typography variant="caption" color="success.main" sx={{ mt: 1, display: 'block' }}>
                        Selected: {selected}
                    </Typography>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" disabled={!selected} onClick={handleConfirm}>
                    Use this image
                </Button>
            </DialogActions>
        </Dialog>
    );
};
