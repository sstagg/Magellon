import React from 'react';
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
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
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
}) => {
    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
        >
            <Box sx={{ width: 320, p: 3 }}>
                <Typography variant="h6" gutterBottom>
                    Particle Picking Settings
                </Typography>

                <Accordion defaultExpanded>
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

                <Accordion>
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
                        </Stack>
                    </AccordionDetails>
                </Accordion>
            </Box>
        </Drawer>
    );
};
