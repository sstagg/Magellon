import React, { useState, useCallback } from 'react';
import {
    Box,
    Typography,
    Slider,
    FormControlLabel,
    Switch,
    Drawer,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Stack,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    TextField,
    IconButton,
    Chip,
    Tooltip,
    alpha,
    useTheme,
    InputAdornment,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
    Add as AddIcon,
    Delete as DeleteIcon,
    CloudUpload as CloudUploadIcon,
    InsertDriveFile as FileIcon,
} from '@mui/icons-material';
import { ParticleClass } from '../lib/useParticleOperations.ts';

export interface ParticleSettingsDrawerProps {
    open: boolean;
    onClose: () => void;
    particleRadius: number;
    onRadiusChange: (v: number) => void;
    particleOpacity: number;
    onOpacityChange: (v: number) => void;
    showCrosshair: boolean;
    onCrosshairToggle: (v: boolean) => void;
    showGrid: boolean;
    onGridToggle: (v: boolean) => void;
    showStats: boolean;
    onStatsToggle: (v: boolean) => void;
    particleClasses: ParticleClass[];
    onClassVisibilityChange: (classId: string, visible: boolean) => void;
    autoPickingThreshold: number;
    onThresholdChange: (v: number) => void;
    templatePaths: string[];
    onTemplatePathsChange: (paths: string[]) => void;
    imagePixelSize: number;
    onImagePixelSizeChange: (v: number) => void;
    templatePixelSize: number;
    onTemplatePixelSizeChange: (v: number) => void;
    diameterAngstrom: number;
    onDiameterAngstromChange: (v: number) => void;
}

export const ParticleSettingsDrawer: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    onClose,
    particleRadius,
    onRadiusChange,
    particleOpacity,
    onOpacityChange,
    showCrosshair,
    onCrosshairToggle,
    showGrid,
    onGridToggle,
    showStats,
    onStatsToggle,
    particleClasses,
    onClassVisibilityChange,
    autoPickingThreshold,
    onThresholdChange,
    templatePaths,
    onTemplatePathsChange,
    imagePixelSize,
    onImagePixelSizeChange,
    templatePixelSize,
    onTemplatePixelSizeChange,
    diameterAngstrom,
    onDiameterAngstromChange,
}) => {
    const theme = useTheme();
    const [newPath, setNewPath] = useState('');
    const [isDragOver, setIsDragOver] = useState(false);

    const addTemplate = useCallback((path: string) => {
        const trimmed = path.trim();
        if (trimmed && !templatePaths.includes(trimmed)) {
            onTemplatePathsChange([...templatePaths, trimmed]);
        }
    }, [templatePaths, onTemplatePathsChange]);

    const handleAddPath = () => {
        if (newPath.trim()) {
            addTemplate(newPath);
            setNewPath('');
        }
    };

    const handleRemovePath = (path: string) => {
        onTemplatePathsChange(templatePaths.filter(p => p !== path));
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleAddPath();
        }
    };

    // Handle drag-and-drop of files — extract their names as server paths
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const newPaths: string[] = [];
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                // Use the file name — the backend resolves the full path
                const name = file.name;
                if (name.endsWith('.mrc') || name.endsWith('.mrcs')) {
                    newPaths.push(name);
                }
            }
            if (newPaths.length > 0) {
                onTemplatePathsChange([...templatePaths, ...newPaths.filter(p => !templatePaths.includes(p))]);
            }
        }

        // Also handle plain text drag (e.g., dragging a path from a file manager)
        const text = e.dataTransfer.getData('text/plain');
        if (text) {
            text.split('\n').forEach(line => {
                const trimmed = line.trim();
                if (trimmed) addTemplate(trimmed);
            });
        }
    };

    const getFileName = (path: string) => {
        const parts = path.replace(/\\/g, '/').split('/');
        return parts[parts.length - 1];
    };

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
        >
            <Box sx={{ width: 340, p: 3 }}>
                <Typography variant="h6" gutterBottom>
                    Particle Picking Settings
                </Typography>

                {/* Templates section — first, since it's the most important for auto-pick */}
                <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography>Templates</Typography>
                            <Chip
                                label={templatePaths.length}
                                size="small"
                                color={templatePaths.length > 0 ? 'primary' : 'default'}
                                sx={{ height: 20, fontSize: '0.7rem' }}
                            />
                        </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Stack spacing={2}>
                            {/* Drop zone */}
                            <Box
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                sx={{
                                    border: `2px dashed ${isDragOver
                                        ? theme.palette.primary.main
                                        : alpha(theme.palette.text.secondary, 0.3)}`,
                                    borderRadius: 2,
                                    p: 2,
                                    textAlign: 'center',
                                    backgroundColor: isDragOver
                                        ? alpha(theme.palette.primary.main, 0.08)
                                        : 'transparent',
                                    transition: 'all 0.2s',
                                    cursor: 'pointer',
                                }}
                            >
                                <CloudUploadIcon sx={{
                                    fontSize: 32,
                                    color: isDragOver ? 'primary.main' : 'text.secondary',
                                    mb: 0.5,
                                }} />
                                <Typography variant="caption" color="text.secondary" display="block">
                                    Drag & drop .mrc template files here
                                </Typography>
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.65rem' }}>
                                    or type a server path below
                                </Typography>
                            </Box>

                            {/* Manual path input */}
                            <TextField
                                size="small"
                                placeholder="/path/to/template.mrc"
                                value={newPath}
                                onChange={(e) => setNewPath(e.target.value)}
                                onKeyDown={handleKeyDown}
                                fullWidth
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton
                                                size="small"
                                                onClick={handleAddPath}
                                                disabled={!newPath.trim()}
                                            >
                                                <AddIcon fontSize="small" />
                                            </IconButton>
                                        </InputAdornment>
                                    ),
                                    sx: { fontSize: '0.8rem' },
                                }}
                            />

                            {/* Template list */}
                            {templatePaths.length > 0 && (
                                <List dense sx={{ py: 0 }}>
                                    {templatePaths.map((path, idx) => (
                                        <ListItem
                                            key={idx}
                                            sx={{
                                                px: 1,
                                                py: 0.25,
                                                borderRadius: 1,
                                                '&:hover': {
                                                    backgroundColor: alpha(theme.palette.primary.main, 0.04),
                                                },
                                            }}
                                        >
                                            <ListItemIcon sx={{ minWidth: 28 }}>
                                                <FileIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                                            </ListItemIcon>
                                            <Tooltip title={path} placement="left">
                                                <ListItemText
                                                    primary={getFileName(path)}
                                                    primaryTypographyProps={{
                                                        variant: 'caption',
                                                        noWrap: true,
                                                        fontFamily: 'monospace',
                                                    }}
                                                />
                                            </Tooltip>
                                            <ListItemSecondaryAction>
                                                <IconButton
                                                    edge="end"
                                                    size="small"
                                                    onClick={() => handleRemovePath(path)}
                                                >
                                                    <DeleteIcon sx={{ fontSize: 14 }} />
                                                </IconButton>
                                            </ListItemSecondaryAction>
                                        </ListItem>
                                    ))}
                                </List>
                            )}

                            {templatePaths.length === 0 && (
                                <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                    No templates added. Auto-pick needs at least one template.
                                </Typography>
                            )}
                        </Stack>
                    </AccordionDetails>
                </Accordion>

                {/* Auto-picking Settings */}
                <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>Auto-picking Settings</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Stack spacing={3}>
                            <Box>
                                <Typography gutterBottom>Detection Threshold</Typography>
                                <Slider
                                    value={autoPickingThreshold}
                                    onChange={(e, v) => onThresholdChange(v as number)}
                                    min={0.1}
                                    max={1}
                                    step={0.1}
                                    valueLabelDisplay="auto"
                                    marks={[
                                        { value: 0.3, label: 'Low' },
                                        { value: 0.7, label: 'Medium' },
                                        { value: 0.9, label: 'High' }
                                    ]}
                                />
                            </Box>

                            <Box>
                                <Typography gutterBottom>Particle Diameter (&#x212B;)</Typography>
                                <Slider
                                    value={diameterAngstrom}
                                    onChange={(e, v) => onDiameterAngstromChange(v as number)}
                                    min={10}
                                    max={500}
                                    step={5}
                                    valueLabelDisplay="auto"
                                    marks={[
                                        { value: 50, label: '50' },
                                        { value: 200, label: '200' },
                                        { value: 500, label: '500' }
                                    ]}
                                />
                            </Box>

                            <TextField
                                size="small"
                                label="Image pixel size (&#x212B;/px)"
                                type="number"
                                value={imagePixelSize}
                                onChange={(e) => onImagePixelSizeChange(parseFloat(e.target.value) || 1.0)}
                                inputProps={{ step: 0.1, min: 0.1 }}
                                fullWidth
                            />

                            <TextField
                                size="small"
                                label="Template pixel size (&#x212B;/px)"
                                type="number"
                                value={templatePixelSize}
                                onChange={(e) => onTemplatePixelSizeChange(parseFloat(e.target.value) || 1.0)}
                                inputProps={{ step: 0.1, min: 0.1 }}
                                fullWidth
                            />
                        </Stack>
                    </AccordionDetails>
                </Accordion>

                {/* Display Settings */}
                <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>Display Settings</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Stack spacing={3}>
                            <Box>
                                <Typography gutterBottom>Particle Size</Typography>
                                <Slider
                                    value={particleRadius}
                                    onChange={(e, v) => onRadiusChange(v as number)}
                                    min={5}
                                    max={50}
                                    valueLabelDisplay="auto"
                                    marks={[
                                        { value: 5, label: '5' },
                                        { value: 25, label: '25' },
                                        { value: 50, label: '50' }
                                    ]}
                                />
                            </Box>

                            <Box>
                                <Typography gutterBottom>Particle Opacity</Typography>
                                <Slider
                                    value={particleOpacity}
                                    onChange={(e, v) => onOpacityChange(v as number)}
                                    min={0.1}
                                    max={1}
                                    step={0.1}
                                    valueLabelDisplay="auto"
                                    marks={[
                                        { value: 0.1, label: '10%' },
                                        { value: 0.5, label: '50%' },
                                        { value: 1, label: '100%' }
                                    ]}
                                />
                            </Box>

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={showCrosshair}
                                        onChange={(e) => onCrosshairToggle(e.target.checked)}
                                    />
                                }
                                label="Show Crosshairs"
                            />

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={showGrid}
                                        onChange={(e) => onGridToggle(e.target.checked)}
                                    />
                                }
                                label="Show Grid"
                            />

                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={showStats}
                                        onChange={(e) => onStatsToggle(e.target.checked)}
                                    />
                                }
                                label="Show Statistics Bar"
                            />
                        </Stack>
                    </AccordionDetails>
                </Accordion>

                {/* Particle Classes */}
                <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>Particle Classes</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <List>
                            {particleClasses.map(cls => (
                                <ListItem key={cls.id}>
                                    <ListItemIcon>
                                        {cls.icon}
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={cls.name}
                                        secondary={`${cls.count} particles`}
                                    />
                                    <ListItemSecondaryAction>
                                        <Switch
                                            checked={cls.visible}
                                            onChange={(e) => {
                                                onClassVisibilityChange(cls.id, e.target.checked);
                                            }}
                                        />
                                    </ListItemSecondaryAction>
                                </ListItem>
                            ))}
                        </List>
                    </AccordionDetails>
                </Accordion>
            </Box>
        </Drawer>
    );
};
