import React, { useEffect, useState } from 'react';
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
    CircularProgress,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { ParticleClass } from '../lib/useParticleOperations.ts';
import { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import { settings } from '../../../shared/config/settings.ts';

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
    // Algorithm params — managed as a flat dict driven by schema
    pickerParams: Record<string, any>;
    onPickerParamsChange: (params: Record<string, any>) => void;
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
    pickerParams,
    onPickerParamsChange,
}) => {
    const [schema, setSchema] = useState<any>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);

    // Fetch the input schema from the backend once
    useEffect(() => {
        if (!open || schema) return;

        setSchemaLoading(true);
        fetch(`${settings.ConfigData.SERVER_API_URL}/plugins/pp/template-pick/schema/input`)
            .then((res) => {
                if (!res.ok) throw new Error(`${res.status}`);
                return res.json();
            })
            .then((data) => {
                setSchema(data);
                setSchemaError(null);
            })
            .catch((err) => {
                setSchemaError(`Failed to load picker schema: ${err.message}`);
            })
            .finally(() => setSchemaLoading(false));
    }, [open, schema]);

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

                {/* Schema-driven algorithm settings */}
                {schemaLoading && (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <CircularProgress size={24} />
                        <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                            Loading picker settings...
                        </Typography>
                    </Box>
                )}

                {schemaError && (
                    <Typography variant="caption" color="error" sx={{ display: 'block', mb: 2 }}>
                        {schemaError}
                    </Typography>
                )}

                {schema && (
                    <SchemaForm
                        schema={schema}
                        values={pickerParams}
                        onChange={onPickerParamsChange}
                        defaultExpanded={['Templates', 'Auto-picking Settings']}
                        collapseAdvanced
                    />
                )}

                {/* Display Settings — these are UI-only, not part of the algorithm */}
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
