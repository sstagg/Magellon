import { Box, Button, Chip, Divider, LinearProgress, Paper, Typography, alpha, useTheme } from "@mui/material";
import { CheckCircle, Info, Server } from 'lucide-react';
import { systemResources } from '../model/dashboardData.tsx';

// System Status
export const SystemStatusPanel = () => {
    const theme = useTheme();

    return (
        <Paper elevation={1} sx={{ borderRadius: 2, overflow: 'hidden' }}>
            <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                        System Status
                    </Typography>
                    <Chip
                        label="Healthy"
                        size="small"
                        icon={<CheckCircle size={12} />}
                        sx={{
                            backgroundColor: alpha(theme.palette.success.main, 0.1),
                            color: theme.palette.success.main,
                            fontWeight: 500,
                            '& .MuiChip-icon': {
                                color: theme.palette.success.main
                            }
                        }}
                    />
                </Box>
            </Box>

            <Box sx={{ p: 2 }}>
                {systemResources.map((resource, index) => (
                    <Box key={index} sx={{ mb: 2.5 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                {resource.name} Usage
                            </Typography>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                {resource.usage}%
                            </Typography>
                        </Box>
                        <LinearProgress
                            variant="determinate"
                            value={resource.usage}
                            sx={{
                                height: 6,
                                borderRadius: 3,
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                '& .MuiLinearProgress-bar': {
                                    backgroundColor: resource.usage > 80
                                        ? theme.palette.error.main
                                        : resource.usage > 60
                                            ? theme.palette.warning.main
                                            : theme.palette.primary.main
                                }
                            }}
                        />
                    </Box>
                ))}

                <Divider sx={{ my: 2 }} />

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Server size={16} color={theme.palette.info.main} />
                    <Typography variant="body2">
                        Last maintenance: 2 days ago
                    </Typography>
                </Box>

                <Button
                    fullWidth
                    variant="outlined"
                    size="small"
                    startIcon={<Info size={16} />}
                    sx={{ mt: 2 }}
                >
                    System Details
                </Button>
            </Box>
        </Paper>
    );
};
