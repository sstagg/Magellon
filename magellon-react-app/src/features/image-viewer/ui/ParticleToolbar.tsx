import React from 'react';
import {
    Box,
    Paper,
    Stack,
    IconButton,
    ButtonGroup,
    ToggleButton,
    ToggleButtonGroup,
    Chip,
    Divider,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent,
    Tooltip,
    CircularProgress,
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
    SelectAll as SelectAllIcon,
    Brush as BrushIcon,
    Fullscreen as FullscreenIcon,
    FullscreenExit as FullscreenExitIcon,
    CropFree as CropFreeIcon,
    PanTool as PanToolIcon,
    TouchApp as TouchAppIcon,
} from '@mui/icons-material';
import { Move } from 'lucide-react';
import { Tool } from '../lib/useParticleOperations.ts';
import { ParticlePickingDto } from '../../../entities/particle-picking/types.ts';

export interface ParticleToolbarProps {
    // Session
    selectedParticlePicking: ParticlePickingDto | null;
    ImageParticlePickings: ParticlePickingDto[] | null;
    isIPPLoading: boolean;
    OnIppSelected: (event: SelectChangeEvent) => void;
    onRefresh: () => void;
    onCreateNew: () => void;
    onSave: () => void;
    // Tools
    tool: Tool;
    onToolChange: (tool: Tool) => void;
    // Actions
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
    // View
    zoom: number;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onZoomReset: () => void;
    // Display
    showGrid: boolean;
    onToggleGrid: () => void;
    onAutoPickRun: () => void;
    isAutoPickingRunning: boolean;
    onSettingsOpen: () => void;
    onHelpOpen: () => void;
    isMobile: boolean;
    // Fullscreen
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
    isMobile,
    isFullscreen,
    onToggleFullscreen,
}) => {
    return (
        <Paper elevation={1} sx={{ p: 2 }}>
            <Stack spacing={2}>
                {/* Session and Save Controls */}
                <Stack direction={isMobile ? "column" : "row"} spacing={2} alignItems="flex-start">
                    <FormControl size="small" sx={{ minWidth: 200, flex: 1 }}>
                        <InputLabel>Particle Picking Session</InputLabel>
                        <Select
                            value={selectedParticlePicking?.oid || ""}
                            label="Particle Picking Session"
                            onChange={OnIppSelected}
                            startAdornment={
                                isIPPLoading ? (
                                    <CircularProgress size={20} sx={{ mr: 1 }} />
                                ) : null
                            }
                        >
                            <MenuItem value="">
                                <em>None</em>
                            </MenuItem>
                            {Array.isArray(ImageParticlePickings) && ImageParticlePickings?.map((ipp) => (
                                <MenuItem key={ipp.oid} value={ipp.oid}>
                                    {ipp.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <ButtonGroup size="small" variant="outlined">
                        <Tooltip title="Refresh Sessions">
                            <IconButton onClick={onRefresh}>
                                <RefreshIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Create New Session">
                            <IconButton onClick={onCreateNew}>
                                <AddIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Save Current Session">
                            <IconButton onClick={onSave} disabled={!selectedParticlePicking}>
                                <SaveIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Session">
                            <IconButton disabled={!selectedParticlePicking}>
                                <DeleteIcon />
                            </IconButton>
                        </Tooltip>
                    </ButtonGroup>

                    {!isMobile && (
                        <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
                            <IconButton onClick={onToggleFullscreen}>
                                {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
                            </IconButton>
                        </Tooltip>
                    )}
                </Stack>

                {/* Tool Selection */}
                <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                    <ToggleButtonGroup
                        value={tool}
                        exclusive
                        onChange={(e, value) => value && onToolChange(value)}
                        size="small"
                    >
                        <ToggleButton value="add" aria-label="add particles">
                            <Tooltip title="Add Particles (1)">
                                <AddIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="remove" aria-label="remove particles">
                            <Tooltip title="Remove Particles (2)">
                                <RemoveIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="select" aria-label="select particles">
                            <Tooltip title="Select Particles (3)">
                                <TouchAppIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="move" aria-label="move particles">
                            <Tooltip title="Move Particles (4)">
                                <Move size={16} />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="box" aria-label="box selection">
                            <Tooltip title="Box Selection (5)">
                                <CropFreeIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="brush" aria-label="brush tool">
                            <Tooltip title="Brush Tool (6)">
                                <BrushIcon />
                            </Tooltip>
                        </ToggleButton>
                        <ToggleButton value="pan" aria-label="pan view">
                            <Tooltip title="Pan View">
                                <PanToolIcon />
                            </Tooltip>
                        </ToggleButton>
                    </ToggleButtonGroup>

                    <Divider orientation="vertical" flexItem />

                    {/* Action Buttons */}
                    <ButtonGroup size="small">
                        <Tooltip title="Undo (Ctrl+Z)">
                            <span>
                                <IconButton
                                    onClick={onUndo}
                                    disabled={!canUndo}
                                    size="small"
                                >
                                    <UndoIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Redo (Ctrl+Shift+Z)">
                            <span>
                                <IconButton
                                    onClick={onRedo}
                                    disabled={!canRedo}
                                    size="small"
                                >
                                    <RedoIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                    </ButtonGroup>

                    <ButtonGroup size="small">
                        <Tooltip title="Select All (Ctrl+A)">
                            <IconButton onClick={onSelectAll} size="small">
                                <SelectAllIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Copy Selected (Ctrl+C)">
                            <span>
                                <IconButton
                                    onClick={onCopy}
                                    disabled={!hasSelection}
                                    size="small"
                                >
                                    <CopyIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Paste (Ctrl+V)">
                            <span>
                                <IconButton
                                    onClick={onPaste}
                                    disabled={!hasCopied}
                                    size="small"
                                >
                                    <PasteIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Delete Selected (Delete)">
                            <span>
                                <IconButton
                                    onClick={onDelete}
                                    disabled={!hasSelection}
                                    size="small"
                                >
                                    <DeleteIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                    </ButtonGroup>

                    <Divider orientation="vertical" flexItem />

                    {/* View Controls */}
                    <ButtonGroup size="small">
                        <Tooltip title="Zoom In (+)">
                            <IconButton onClick={onZoomIn} size="small">
                                <ZoomInIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Zoom Out (-)">
                            <IconButton onClick={onZoomOut} size="small">
                                <ZoomOutIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Reset View">
                            <IconButton onClick={onZoomReset} size="small">
                                <CenterFocusStrongIcon />
                            </IconButton>
                        </Tooltip>
                    </ButtonGroup>

                    <Chip
                        label={`Zoom: ${(zoom * 100).toFixed(0)}%`}
                        size="small"
                        variant="outlined"
                    />

                    <Box sx={{ flex: 1 }} />

                    {/* Right side controls */}
                    <Tooltip title="Toggle Grid (G)">
                        <IconButton
                            onClick={onToggleGrid}
                            color={showGrid ? "primary" : "default"}
                            size="small"
                        >
                            <GridOnIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Run Auto-picking">
                        <IconButton
                            onClick={onAutoPickRun}
                            disabled={isAutoPickingRunning}
                            color="primary"
                            size="small"
                        >
                            <AutoFixHighIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Settings">
                        <IconButton onClick={onSettingsOpen} size="small">
                            <SettingsIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Help (H)">
                        <IconButton onClick={onHelpOpen} size="small">
                            <HelpIcon />
                        </IconButton>
                    </Tooltip>
                </Stack>
            </Stack>
        </Paper>
    );
};
