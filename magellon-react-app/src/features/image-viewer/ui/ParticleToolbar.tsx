import React, { useState } from 'react';
import {
    Box,
    Paper,
    IconButton,
    ToggleButton,
    ToggleButtonGroup,
    Chip,
    Divider,
    FormControl,
    Select,
    MenuItem,
    SelectChangeEvent,
    Tooltip,
    CircularProgress,
    Menu,
} from '@mui/material';
import {
    Add as AddIcon,
    Remove as RemoveIcon,
    Delete as DeleteIcon,
    Save as SaveIcon,
    Undo as UndoIcon,
    Redo as RedoIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
    CenterFocusStrong as CenterFocusStrongIcon,
    GridOn as GridOnIcon,
    AutoFixHigh as AutoFixHighIcon,
    Settings as SettingsIcon,
    Help as HelpIcon,
    Refresh as RefreshIcon,
    ContentCopy as CopyIcon,
    ContentPaste as PasteIcon,
    Download as DownloadIcon,
    SelectAll as SelectAllIcon,
    Brush as BrushIcon,
    CropFree as CropFreeIcon,
    PanTool as PanToolIcon,
    TouchApp as TouchAppIcon,
    MoreVert,
} from '@mui/icons-material';
import { Move } from 'lucide-react';
import { Tool } from '../lib/useParticleOperations.ts';
import { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';

export interface ParticleToolbarProps {
    selectedParticlePicking: ParticlePickingDto | null;
    ImageParticlePickings: ParticlePickingDto[] | null;
    isIPPLoading: boolean;
    OnIppSelected: (event: SelectChangeEvent) => void;
    onRefresh: () => void;
    onCreateNew: () => void;
    onSave: () => void;
    onExportCoco: () => void;
    tool: Tool;
    onToolChange: (tool: Tool) => void;
    onUndo: () => void;
    onRedo: () => void;
    canUndo: boolean;
    canRedo: boolean;
    onSelectAll: () => void;
    onCopy: () => void;
    onPaste: () => void;
    onDelete: () => void;
    hasSelection: boolean;
    hasCopied: boolean;
    zoom: number;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onZoomReset: () => void;
    showGrid: boolean;
    onToggleGrid: () => void;
    onAutoPickRun: () => void;
    isAutoPickingRunning: boolean;
    onSettingsOpen: () => void;
    onHelpOpen: () => void;
    isMobile: boolean;
    isFullscreen: boolean;
    onToggleFullscreen: () => void;
}

export const ParticleToolbar: React.FC<ParticleToolbarProps> = ({
    selectedParticlePicking,
    ImageParticlePickings,
    isIPPLoading,
    OnIppSelected,
    onRefresh,
    onCreateNew,
    onSave,
    onExportCoco,
    tool,
    onToolChange,
    onUndo,
    onRedo,
    canUndo,
    canRedo,
    onSelectAll,
    onCopy,
    onPaste,
    onDelete,
    hasSelection,
    hasCopied,
    zoom,
    onZoomIn,
    onZoomOut,
    onZoomReset,
    showGrid,
    onToggleGrid,
    onAutoPickRun,
    isAutoPickingRunning,
    onSettingsOpen,
    onHelpOpen,
}) => {
    const [actionsAnchor, setActionsAnchor] = useState<null | HTMLElement>(null);

    return (
        <Paper elevation={1} sx={{ px: 1, py: 0.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>

                {/* Picking-record dropdown — each entry is one saved set of
                    particle picks (manual or auto) for this image. */}
                <Tooltip title="Particle-picking records for this image (manual or auto)">
                    <FormControl size="small" sx={{ minWidth: 160, maxWidth: 220 }}>
                        <Select
                            displayEmpty
                            value={selectedParticlePicking?.oid || ""}
                            onChange={OnIppSelected}
                            sx={{
                                height: 28, fontSize: '0.75rem',
                                '& .MuiSelect-select': { py: 0.25 },
                            }}
                            startAdornment={isIPPLoading ? <CircularProgress size={14} sx={{ mr: 0.5 }} /> : null}
                        >
                            <MenuItem value=""><em>Picking record…</em></MenuItem>
                            {Array.isArray(ImageParticlePickings) && ImageParticlePickings?.map((ipp) => (
                                <MenuItem key={ipp.oid} value={ipp.oid} sx={{ fontSize: '0.8rem' }}>
                                    {ipp.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Tooltip>

                {/* Picking-record actions dropdown */}
                <Tooltip title="Picking record actions">
                    <IconButton size="small" onClick={(e) => setActionsAnchor(e.currentTarget)} sx={{ p: 0.25 }}>
                        <MoreVert sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
                <Menu
                    anchorEl={actionsAnchor}
                    open={Boolean(actionsAnchor)}
                    onClose={() => setActionsAnchor(null)}
                    slotProps={{ paper: { sx: { minWidth: 180 } } }}
                >
                    <MenuItem onClick={() => { onRefresh(); setActionsAnchor(null); }}>
                        <RefreshIcon sx={{ fontSize: 18, mr: 1 }} /> Refresh
                    </MenuItem>
                    <MenuItem onClick={() => { onCreateNew(); setActionsAnchor(null); }}>
                        <AddIcon sx={{ fontSize: 18, mr: 1 }} /> New picking record
                    </MenuItem>
                    <MenuItem onClick={() => { onSave(); setActionsAnchor(null); }} disabled={!selectedParticlePicking}>
                        <SaveIcon sx={{ fontSize: 18, mr: 1 }} /> Save
                    </MenuItem>
                    <MenuItem onClick={() => { onExportCoco(); setActionsAnchor(null); }} disabled={!selectedParticlePicking}>
                        <DownloadIcon sx={{ fontSize: 18, mr: 1 }} /> Export as COCO
                    </MenuItem>
                    <MenuItem disabled={!selectedParticlePicking}>
                        <DeleteIcon sx={{ fontSize: 18, mr: 1 }} /> Delete
                    </MenuItem>
                </Menu>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

                {/* Tool toggles */}
                <ToggleButtonGroup
                    value={tool}
                    exclusive
                    onChange={(_, v) => v && onToolChange(v)}
                    size="small"
                    sx={{ height: 28, '& .MuiToggleButton-root': { px: 0.75 } }}
                >
                    <ToggleButton value="add"><Tooltip title="Add (1)"><AddIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                    <ToggleButton value="remove"><Tooltip title="Remove (2)"><RemoveIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                    <ToggleButton value="select"><Tooltip title="Select (3)"><TouchAppIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                    <ToggleButton value="move"><Tooltip title="Move (4)"><Move size={14} /></Tooltip></ToggleButton>
                    <ToggleButton value="box"><Tooltip title="Box (5)"><CropFreeIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                    <ToggleButton value="brush"><Tooltip title="Brush (6)"><BrushIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                    <ToggleButton value="pan"><Tooltip title="Pan"><PanToolIcon sx={{ fontSize: 16 }} /></Tooltip></ToggleButton>
                </ToggleButtonGroup>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

                {/* Undo / Redo */}
                <Tooltip title="Undo"><span><IconButton size="small" onClick={onUndo} disabled={!canUndo} sx={{ p: 0.25 }}><UndoIcon sx={{ fontSize: 16 }} /></IconButton></span></Tooltip>
                <Tooltip title="Redo"><span><IconButton size="small" onClick={onRedo} disabled={!canRedo} sx={{ p: 0.25 }}><RedoIcon sx={{ fontSize: 16 }} /></IconButton></span></Tooltip>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

                {/* Clipboard */}
                <Tooltip title="Select All"><IconButton size="small" onClick={onSelectAll} sx={{ p: 0.25 }}><SelectAllIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Copy"><span><IconButton size="small" onClick={onCopy} disabled={!hasSelection} sx={{ p: 0.25 }}><CopyIcon sx={{ fontSize: 16 }} /></IconButton></span></Tooltip>
                <Tooltip title="Paste"><span><IconButton size="small" onClick={onPaste} disabled={!hasCopied} sx={{ p: 0.25 }}><PasteIcon sx={{ fontSize: 16 }} /></IconButton></span></Tooltip>
                <Tooltip title="Delete"><span><IconButton size="small" onClick={onDelete} disabled={!hasSelection} sx={{ p: 0.25 }}><DeleteIcon sx={{ fontSize: 16 }} /></IconButton></span></Tooltip>

                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

                {/* Zoom */}
                <Tooltip title="Zoom In"><IconButton size="small" onClick={onZoomIn} sx={{ p: 0.25 }}><ZoomInIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Zoom Out"><IconButton size="small" onClick={onZoomOut} sx={{ p: 0.25 }}><ZoomOutIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Reset"><IconButton size="small" onClick={onZoomReset} sx={{ p: 0.25 }}><CenterFocusStrongIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Chip label={`${(zoom * 100).toFixed(0)}%`} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.65rem' }} />

                <Box sx={{ flex: 1 }} />

                {/* Right side */}
                <Tooltip title="Grid (G)"><IconButton size="small" onClick={onToggleGrid} color={showGrid ? "primary" : "default"} sx={{ p: 0.25 }}><GridOnIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Auto-pick"><IconButton size="small" onClick={onAutoPickRun} disabled={isAutoPickingRunning} color="primary" sx={{ p: 0.25 }}><AutoFixHighIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Settings"><IconButton size="small" onClick={onSettingsOpen} sx={{ p: 0.25 }}><SettingsIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                <Tooltip title="Help (H)"><IconButton size="small" onClick={onHelpOpen} sx={{ p: 0.25 }}><HelpIcon sx={{ fontSize: 16 }} /></IconButton></Tooltip>
            </Box>
        </Paper>
    );
};
