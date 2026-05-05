/**
 * GPFS file picker — dialog that browses the data plane, selects one or
 * more files, and (optionally) drops new files onto the current directory
 * for upload.
 *
 * Reads from ``GET /web/files/browse``; uploads via ``POST /web/files/upload``.
 * Last-seen path is persisted in localStorage so re-opening the picker
 * lands the operator in the same place they left off.
 *
 * **Path contract.** The picker only ever traffics in canonical
 * ``/gpfs/...`` paths — that's what the backend accepts and returns,
 * and that's what flows through plugin task DTOs. Host-absolute paths
 * (``C:/magellon/gpfs/...`` on Windows direct-run) never appear in the
 * UI; all entry points (``initialPath``, the path text input, the "Up"
 * button, breadcrumbs) clamp to ``/gpfs``. A stale localStorage entry
 * left over from before this contract migrates back to ``/gpfs``
 * automatically on read.
 *
 * Future iterations could grow this into a generic GPFS explorer (rename
 * / delete / mkdir, drag-rearrange between dirs). For now the surface is:
 * browse, multi-select, drop-to-upload.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Breadcrumbs,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    LinearProgress,
    Link,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Stack,
    TextField,
    Tooltip,
    Typography,
    alpha,
    useTheme,
} from '@mui/material';
import {
    ArrowUp,
    CloudUpload,
    File as FileIcon,
    Folder as FolderIcon,
    Home,
    RefreshCw,
    X as XIcon,
} from 'lucide-react';
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
          /** Canonical /gpfs/... initial path. Anything else is clamped. */
          initialPath?: string;
          storageKey?: string;
          /** Override the file-extension filter; default = IMAGE_EXTS. */
          allowedExts?: string[];
          /** Disable the upload drop-zone (e.g. read-only views). */
          disableUpload?: boolean;
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
          allowedExts?: string[];
          disableUpload?: boolean;
      };

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

const GPFS_ROOT = '/gpfs';

/** Coerce any input to a canonical ``/gpfs/...`` path. Anything that
 *  already looks canonical passes through; anything else collapses to
 *  the GPFS root. Keeps stale localStorage values (host-absolute paths
 *  from before the canonical migration) from breaking the picker. */
const clampToGpfs = (raw: string | undefined | null): string => {
    if (!raw) return GPFS_ROOT;
    const norm = raw.replace(/\\/g, '/');
    if (norm === GPFS_ROOT) return GPFS_ROOT;
    if (norm.startsWith(`${GPFS_ROOT}/`)) {
        // Strip a trailing slash for tidiness, except at the root.
        return norm.replace(/\/+$/, '') || GPFS_ROOT;
    }
    return GPFS_ROOT;
};

const splitPath = (p: string): string[] => {
    const normalized = clampToGpfs(p);
    if (normalized === GPFS_ROOT) return [];
    // Trim the leading "/gpfs/" so breadcrumb segments are the
    // sub-directory names, with the root rendered separately.
    return normalized.slice(GPFS_ROOT.length + 1).split('/').filter(Boolean);
};

const parentOf = (p: string): string | null => {
    const normalized = clampToGpfs(p);
    if (normalized === GPFS_ROOT) return null;
    const idx = normalized.lastIndexOf('/');
    if (idx <= 0) return null;
    const parent = normalized.slice(0, idx);
    return clampToGpfs(parent);
};

const formatBytes = (bytes: number | null): string => {
    if (bytes == null) return '';
    if (bytes < 1024) return `${bytes} B`;
    const units = ['KB', 'MB', 'GB', 'TB'];
    let n = bytes / 1024;
    let u = 0;
    while (n >= 1024 && u < units.length - 1) {
        n /= 1024;
        u += 1;
    }
    return `${n.toFixed(1)} ${units[u]}`;
};

export const ImagePickerDialog: React.FC<ImagePickerDialogProps> = (props) => {
    const theme = useTheme();
    const {
        open, onClose, title, initialPath = GPFS_ROOT, onPathChange, storageKey,
        allowedExts, disableUpload,
    } = props;
    const multiple = 'multiple' in props && props.multiple === true;
    const exts = allowedExts ?? IMAGE_EXTS;

    const isAcceptedFile = useCallback(
        (name: string) => exts.some((ext) => name.toLowerCase().endsWith(ext)),
        [exts],
    );

    const effectiveKey = storageKey ?? `imagePicker:lastPath:${title ?? (multiple ? 'multi' : 'single')}`;
    const readStoredPath = () => {
        // Always clamp to canonical /gpfs/...; localStorage may still
        // hold a host-absolute path from the pre-canonical era.
        try {
            return clampToGpfs(localStorage.getItem(effectiveKey) || initialPath);
        } catch {
            return clampToGpfs(initialPath);
        }
    };

    const [pathInput, setPathInput] = useState(readStoredPath);
    const [currentPath, setCurrentPath] = useState(readStoredPath);
    const [items, setItems] = useState<BrowseItem[]>([]);
    const [selected, setSelected] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Upload state
    const [isDragOver, setIsDragOver] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<number | null>(null);
    const [uploadConflict, setUploadConflict] = useState<{
        files: File[];
        message: string;
    } | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const fetchDir = async (path: string) => {
        const canonical = clampToGpfs(path);
        setLoading(true);
        setError(null);
        try {
            const res = await api.get('/web/files/browse', { params: { path: canonical } });
            setItems(res.data ?? []);
            setCurrentPath(canonical);
            setPathInput(canonical);
            setSelected([]);
            try { localStorage.setItem(effectiveKey, canonical); } catch { /* noop */ }
            onPathChange?.(canonical);
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

    const selectAllVisible = () => {
        setSelected(visible.filter((it) => !it.is_directory).map((it) => it.path));
    };

    const clearSelection = () => setSelected([]);

    const handleItemClick = (item: BrowseItem) => {
        if (item.is_directory) {
            fetchDir(item.path);
        } else if (isAcceptedFile(item.name)) {
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

    // ---- Upload ----------------------------------------------------------

    const performUpload = async (files: File[], overwrite: boolean) => {
        setUploading(true);
        setUploadProgress(0);
        setUploadConflict(null);
        setError(null);
        try {
            const form = new FormData();
            form.append('path', currentPath);
            if (overwrite) form.append('overwrite', 'true');
            for (const f of files) form.append('files', f, f.name);
            await api.post('/web/files/upload', form, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (e) => {
                    if (e.total) {
                        setUploadProgress(Math.round((e.loaded / e.total) * 100));
                    }
                },
            });
            await fetchDir(currentPath);
        } catch (err: any) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail || err.message || 'Upload failed';
            if (status === 409) {
                // Surface the conflict so the operator can decide.
                setUploadConflict({ files, message: detail });
            } else {
                setError(detail);
            }
        } finally {
            setUploading(false);
            setUploadProgress(null);
        }
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        if (disableUpload) return;
        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) return;
        await performUpload(files, false);
    };

    const handlePickerSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files ? Array.from(e.target.files) : [];
        e.target.value = '';
        if (files.length === 0) return;
        await performUpload(files, false);
    };

    const visible = items.filter((it) => it.is_directory || isAcceptedFile(it.name));
    const visibleFileCount = visible.filter((v) => !v.is_directory).length;
    const parts = splitPath(currentPath);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <Box sx={{ flex: 1 }}>{title ?? (multiple ? 'Pick files' : 'Pick test image')}</Box>
                    {!disableUpload && (
                        <Tooltip title="Upload from your computer">
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={uploading}
                                >
                                    <CloudUpload size={18} />
                                </IconButton>
                            </span>
                        </Tooltip>
                    )}
                    <Tooltip title="Refresh">
                        <span>
                            <IconButton
                                size="small"
                                onClick={() => fetchDir(currentPath)}
                                disabled={loading || uploading}
                            >
                                <RefreshCw size={16} />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            </DialogTitle>
            <DialogContent
                dividers
                sx={{ position: 'relative' }}
                onDragOver={(e) => {
                    if (disableUpload) return;
                    e.preventDefault();
                    setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    style={{ display: 'none' }}
                    onChange={handlePickerSelect}
                />

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
                    <Link
                        component="button"
                        onClick={() => fetchDir('/gpfs')}
                        sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                    >
                        <Home size={12} /> gpfs
                    </Link>
                    {parts.map((p, i) => (
                        <Link
                            key={i}
                            component="button"
                            onClick={() => {
                                // Walk back into a sub-directory of /gpfs.
                                // ``parts`` excludes the /gpfs prefix; rebuild it.
                                fetchDir(`${GPFS_ROOT}/${parts.slice(0, i + 1).join('/')}`);
                            }}
                        >
                            {p}
                        </Link>
                    ))}
                </Breadcrumbs>

                <Divider sx={{ mb: 1 }} />

                {error && <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError(null)}>{error}</Alert>}

                {uploadConflict && (
                    <Alert
                        severity="warning"
                        sx={{ mb: 1 }}
                        action={
                            <>
                                <Button
                                    size="small"
                                    color="inherit"
                                    onClick={() => performUpload(uploadConflict.files, true)}
                                >
                                    Overwrite
                                </Button>
                                <Button
                                    size="small"
                                    color="inherit"
                                    onClick={() => setUploadConflict(null)}
                                >
                                    Cancel
                                </Button>
                            </>
                        }
                    >
                        {uploadConflict.message}
                    </Alert>
                )}

                {uploading && (
                    <Box sx={{ mb: 1 }}>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                            <CloudUpload size={14} />
                            <Typography variant="caption" sx={{ flex: 1 }}>
                                Uploading…
                            </Typography>
                            {uploadProgress != null && (
                                <Typography variant="caption">{uploadProgress}%</Typography>
                            )}
                        </Stack>
                        <LinearProgress
                            variant={uploadProgress != null ? 'determinate' : 'indeterminate'}
                            value={uploadProgress ?? undefined}
                        />
                    </Box>
                )}

                {/* Drop overlay — shown only while a drag is active. We let
                    the entire DialogContent be the drop target so users can
                    drop anywhere in the picker, not just on a small zone. */}
                {isDragOver && !disableUpload && (
                    <Box
                        sx={{
                            position: 'absolute',
                            inset: 0,
                            zIndex: 5,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: `2px dashed ${theme.palette.primary.main}`,
                            backgroundColor: alpha(theme.palette.primary.main, 0.08),
                            borderRadius: 1,
                            pointerEvents: 'none',
                        }}
                    >
                        <Stack spacing={1} sx={{ alignItems: 'center' }}>
                            <CloudUpload size={36} color={theme.palette.primary.main} />
                            <Typography variant="subtitle1" color="primary">
                                Drop to upload to {currentPath}
                            </Typography>
                        </Stack>
                    </Box>
                )}

                {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                        <CircularProgress size={28} />
                    </Box>
                ) : (
                    <List dense sx={{ maxHeight: 360, overflowY: 'auto' }}>
                        {visible.length === 0 && !error && (
                            <Box sx={{ p: 3, textAlign: 'center' }}>
                                <CloudUpload
                                    size={28}
                                    style={{ opacity: 0.4 }}
                                />
                                <Typography
                                    variant="body2"
                                    sx={{ color: 'text.secondary', mt: 1 }}
                                >
                                    No folders or matching files here.
                                </Typography>
                                {!disableUpload && (
                                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                        Drop files anywhere in this dialog to upload them here.
                                    </Typography>
                                )}
                            </Box>
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
                                        secondary={
                                            !it.is_directory && it.size != null
                                                ? formatBytes(it.size)
                                                : undefined
                                        }
                                    />
                                </ListItemButton>
                            );
                        })}
                    </List>
                )}

                {/* Selection summary + batch controls */}
                {multiple && visibleFileCount > 0 && (
                    <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                            alignItems: 'center',
                            mt: 1,
                            pt: 1,
                            borderTop: '1px solid',
                            borderColor: 'divider',
                        }}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    size="small"
                                    checked={selected.length === visibleFileCount && visibleFileCount > 0}
                                    indeterminate={selected.length > 0 && selected.length < visibleFileCount}
                                    onChange={(e) =>
                                        e.target.checked ? selectAllVisible() : clearSelection()
                                    }
                                />
                            }
                            label={
                                <Typography variant="caption">
                                    Select all {visibleFileCount} file{visibleFileCount === 1 ? '' : 's'}
                                </Typography>
                            }
                            sx={{ m: 0 }}
                        />
                        <Box sx={{ flex: 1 }} />
                        {selected.length > 0 && (
                            <Chip
                                size="small"
                                color="success"
                                label={`${selected.length} selected`}
                                onDelete={clearSelection}
                                deleteIcon={<XIcon size={14} />}
                            />
                        )}
                    </Stack>
                )}
                {!multiple && selected.length > 0 && (
                    <Typography
                        variant="caption"
                        sx={{
                            color: 'success.main',
                            mt: 1,
                            display: 'block',
                        }}
                    >
                        Selected: {selected[0]}
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
