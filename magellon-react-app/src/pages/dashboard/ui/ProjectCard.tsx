import { Box, Chip, LinearProgress, Paper, Typography, alpha, useTheme } from "@mui/material";
import type { ProjectCardProps } from '../model/types.ts';

// Project card component
export const ProjectCard = ({ name, progress, status, lastUpdated, onClick }: ProjectCardProps) => {
    const theme = useTheme();

    const getStatusColor = () => {
        switch (status) {
            case "completed": return theme.palette.success.main;
            case "in-progress": return theme.palette.info.main;
            case "paused": return theme.palette.warning.main;
            default: return theme.palette.grey[500];
        }
    };

    const getStatusLabel = () => {
        switch (status) {
            case "completed": return "Completed";
            case "in-progress": return "In Progress";
            case "paused": return "Paused";
            default: return "Unknown";
        }
    };

    return (
        <Paper
            elevation={1}
            sx={{
                p: 2,
                borderRadius: 2,
                cursor: 'pointer',
                height: '100%',
                transition: 'all 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 2
                }
            }}
            onClick={onClick}
        >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{name}</Typography>
                <Chip
                    label={getStatusLabel()}
                    size="small"
                    sx={{
                        backgroundColor: alpha(getStatusColor(), 0.1),
                        color: getStatusColor(),
                        fontWeight: 500,
                        borderRadius: '4px'
                    }}
                />
            </Box>
            <Box sx={{ mt: 2, mb: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" sx={{
                        color: "text.secondary"
                    }}>Progress</Typography>
                    <Typography variant="caption" sx={{
                        fontWeight: 500
                    }}>{progress}%</Typography>
                </Box>
                <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: alpha(getStatusColor(), 0.1),
                        '& .MuiLinearProgress-bar': {
                            backgroundColor: getStatusColor()
                        }
                    }}
                />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                Last updated: {lastUpdated}
            </Typography>
        </Paper>
    );
};
