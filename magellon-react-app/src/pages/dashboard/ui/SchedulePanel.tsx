import { Box, Button, Paper, Typography, alpha, useTheme } from "@mui/material";
import { Calendar, ChevronRight, Clock } from 'lucide-react';

// Calendar Card
export const SchedulePanel = () => {
    const theme = useTheme();

    return (
        <Paper elevation={1} sx={{ borderRadius: 2, mb: 3, overflow: 'hidden' }}>
            <Box sx={{
                p: 2,
                backgroundColor: alpha(theme.palette.primary.main, 0.05),
                borderBottom: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
            }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                        Today's Schedule
                    </Typography>
                    <Calendar size={18} color={theme.palette.primary.main} />
                </Box>
                <Typography
                    variant="caption"
                    sx={{
                        color: "text.secondary",
                        display: 'block',
                        mt: 0.5
                    }}>
                    Wednesday, May 21, 2025
                </Typography>
            </Box>

            <Box sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                    <Box sx={{
                        width: 36,
                        height: 36,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 1,
                        backgroundColor: alpha(theme.palette.primary.main, 0.1)
                    }}>
                        <Clock size={16} color={theme.palette.primary.main} />
                    </Box>
                    <Box>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            Team Progress Meeting
                        </Typography>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            11:00 AM - 12:00 PM
                        </Typography>
                    </Box>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{
                        width: 36,
                        height: 36,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 1,
                        backgroundColor: alpha(theme.palette.info.main, 0.1)
                    }}>
                        <Clock size={16} color={theme.palette.info.main} />
                    </Box>
                    <Box>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            Data Processing Review
                        </Typography>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            3:30 PM - 4:30 PM
                        </Typography>
                    </Box>
                </Box>

                <Button
                    fullWidth
                    variant="text"
                    size="small"
                    endIcon={<ChevronRight size={16} />}
                    sx={{ mt: 2 }}
                >
                    View Calendar
                </Button>
            </Box>
        </Paper>
    );
};
