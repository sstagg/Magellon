import React, { useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Breadcrumbs,
    Button,
    Checkbox,
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

type ImagePickerDialogProps =
    | {
          open: boolean;
          onClose: () => void;
          multiple?: false;
          onPick: (absolutePath: string) => void;
          onPathChange?: (path: string) => void;
          title?: string;
          initialPath?: string;
          storageKey?: string;
      }
    | {
          open: boolean;
          onClose: () => void;
          multiple: true;
          onPick: (absolutePaths: string[]) => void;
          onPathChange?: (path: string) => void;
          title?: string;
          initialPath?: string;
          storageKey?: string;
      };

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

const isImageFile = (name: string) =>
    IMAGE_EXTS.some((ext) => name.toLowerCase().endsWith(ext));

const splitPath = (p: string): string[] => {
    const normalized = p.replace(/\\/g, '/');
    return normalized.split('/').filter(Boolean);
};

const parentOf = (p: string): string | null => {
    const normalized = p.replace(/\\/g, '/');
    const idx = normalized.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = normalized.slice(0, idx);
    if (/^[A-Za-z]:$/.test(parent)) return parent + '/';
    return parent || '/';
};

export const ImagePickerDialog: React.FC<ImagePickerDialogProps> = (props) => {
    const { open, onClose, title, initialPath = 'C:/', onPathChange, storageKey } = props;
    const multiple = 'multiple' in props && props.multiple === true;

    const effectiveKey = storageKey ?? `imagePicker:lastPath:${title ?? (multiple ? 'multi' : 'single')}`;
    const readStoredPath = () => {
        try {
            return localStorage.getItem(effectiveKey) || initialPath;
        } catch {
            return initialPath;
        }
    };

    const [pathInput, setPathInput] = useState(readStoredPath);
    const [currentPath, setCurrentPath] = useState(readStoredPath);
    const [items, setItems] = useState<BrowseItem[]>([]);
    const [selected, setSelected] = useState<string[]>([]);
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
            setSelected([]);
            try { localStorage.setItem(effectiveKey, path); } catch { /* noop */ }
            onPathChange?.(path);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Failed to browse');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) fetchDir(readStoredPath());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    const toggleSelected = (path: string) => {
        setSelected((prev) => {
            if (multiple) {
                return prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path];
            }
            return [path];
        });
    };

    const handleItemClick = (item: BrowseItem) => {
        if (item.is_directory) {
            fetchDir(item.path);
        } else if (isImageFile(item.name)) {
            toggleSelected(item.path);
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
        if (selected.length === 0) return;
        if (multiple) {
            (props.onPick as (paths: string[]) => void)(selected);
        } else {
            (props.onPick as (path: string) => void)(selected[0]);
        }
        onClose();
    };

    const visible = items.filter((it) => it.is_directory || isImageFile(it.name));
    const parts = splitPath(currentPath);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>{title ?? (multiple ? 'Pick files' : 'Pick test image')}</DialogTitle>
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
                        {visible.map((it) => {
                            const isSelected = selected.includes(it.path);
                            return (
                                <ListItemButton
                                    key={it.path}
                                    onClick={() => handleItemClick(it)}
                                    selected={isSelected}
                                >
                                    {multiple && !it.is_directory && (
                                        <Checkbox
                                            edge="start"
                                            size="small"
                                            checked={isSelected}
                                            tabIndex={-1}
                                            disableRipple
                                        />
                                    )}
                                    <ListItemIcon>
                                        {it.is_directory ? <FolderIcon size={18} /> : <FileIcon size={18} />}
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={it.name}
                                        secondary={!it.is_directory && it.size != null ? `${it.size} bytes` : undefined}
                                    />
                                </ListItemButton>
                            );
                        })}
                    </List>
                )}

                {selected.length > 0 && (
                    <Typography variant="caption" color="success.main" sx={{ mt: 1, display: 'block' }}>
                        {multiple ? `${selected.length} file(s) selected` : `Selected: ${selected[0]}`}
                    </Typography>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" disabled={selected.length === 0} onClick={handleConfirm}>
                    {multiple ? `Use ${selected.length || ''} file(s)` : 'Use this image'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
