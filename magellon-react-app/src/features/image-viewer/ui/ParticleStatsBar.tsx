import React from 'react';
import {
    Paper,
    Stack,
    Chip,
    Divider,
    alpha,
    useTheme,
} from '@mui/material';
import {
    AutoFixHigh as AutoFixHighIcon,
    Layers as LayersIcon,
    Assessment as AssessmentIcon,
    TouchApp as TouchAppIcon,
} from '@mui/icons-material';
import { ParticleClass } from '../lib/useParticleOperations.ts';

export interface ParticleStatsBarProps {
    stats: { total: number; manual: number; auto: number; avgConfidence: number; particlesPerClass: Record<string, number> };
    particleClasses: ParticleClass[];
    activeClass: string;
    onActiveClassChange: (classId: string) => void;
    selectedCount: number;
    onDeselectAll: () => void;
}

export const ParticleStatsBar: React.FC<ParticleStatsBarProps> = ({
    stats,
    particleClasses,
    activeClass,
    onActiveClassChange,
    selectedCount,
    onDeselectAll,
}) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={0}
            sx={{
                p: 1,
                backgroundColor: alpha(theme.palette.primary.main, 0.05),
                border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
            }}
        >
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <Chip
                    icon={<LayersIcon />}
                    label={`Total: ${stats.total}`}
                    size="small"
                    variant="outlined"
                />
                <Chip
                    icon={<TouchAppIcon />}
                    label={`Manual: ${stats.manual}`}
                    size="small"
                    color="primary"
                    variant="outlined"
                />
                <Chip
                    icon={<AutoFixHighIcon />}
                    label={`Auto: ${stats.auto}`}
                    size="small"
                    color="secondary"
                    variant="outlined"
                />
                <Chip
                    icon={<AssessmentIcon />}
                    label={`Confidence: ${(stats.avgConfidence * 100).toFixed(0)}%`}
                    size="small"
                    variant="outlined"
                />

                <Divider orientation="vertical" flexItem />

                {particleClasses.map(cls => (
                    <Chip
                        key={cls.id}
                        icon={cls.icon}
                        label={`${cls.name}: ${cls.count}`}
                        size="small"
                        sx={{
                            backgroundColor: activeClass === cls.id
                                ? alpha(cls.color, 0.3)
                                : alpha(cls.color, 0.1),
                            color: cls.color,
                            fontWeight: activeClass === cls.id ? 'bold' : 'normal',
                            border: `1px solid ${cls.color}`,
                            cursor: 'pointer'
                        }}
                        onClick={() => onActiveClassChange(cls.id)}
                        variant={activeClass === cls.id ? "filled" : "outlined"}
                    />
                ))}

                {selectedCount > 0 && (
                    <>
                        <Divider orientation="vertical" flexItem />
                        <Chip
                            label={`Selected: ${selectedCount}`}
                            size="small"
                            color="info"
                            onDelete={onDeselectAll}
                        />
                    </>
                )}
            </Stack>
        </Paper>
    );
};
