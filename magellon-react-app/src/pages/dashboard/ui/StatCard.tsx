import React from 'react';
import { Box, Paper, Typography, alpha, useMediaQuery, useTheme } from "@mui/material";
import type { StatCardProps } from '../model/types.ts';
import { MetricChart } from './MetricChart.tsx';

// Dashboard stat card component with sparkline chart
export const StatCard = ({ title, value, subtitle, icon, color, chartData = [] }: StatCardProps) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    return (
        <Paper
            elevation={1}
            sx={{
                p: { xs: 1.5, sm: 2, md: 2.5 },
                height: '100%',
                width: '100%',
                background: `linear-gradient(135deg, ${alpha(color, 0.12)}, ${alpha(color, 0.05)})`,
                border: `1px solid ${alpha(color, 0.15)}`,
                borderRadius: 2,
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3,
                }
            }}
        >
            <Box
                sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start"
                }}>
                <Box>
                    <Typography
                        variant="body2"
                        component="div"
                        gutterBottom
                        sx={{
                            fontWeight: 500,
                            color: 'text.secondary',
                            fontSize: { xs: '0.75rem', sm: '0.875rem' },
                            mb: 0.5
                        }}
                    >
                        {title}
                    </Typography>
                    <Typography
                        variant={isMobile ? "h6" : "h5"}
                        component="div"
                        sx={{
                            fontWeight: 'bold',
                            color: theme.palette.text.primary,
                            lineHeight: 1.2,
                            fontSize: { xs: '1.25rem', sm: '1.5rem', md: '1.75rem' }
                        }}
                    >
                        {value}
                    </Typography>
                    {subtitle && (
                        <Typography
                            variant="caption"
                            sx={{
                                color: 'text.secondary',
                                display: 'block',
                                mt: 0.5,
                                fontSize: { xs: '0.7rem', sm: '0.75rem' }
                            }}
                        >
                            {subtitle}
                        </Typography>
                    )}
                </Box>
                <Box sx={{
                    backgroundColor: alpha(color, 0.15),
                    p: { xs: 0.75, sm: 1 },
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                }}>
                    {React.cloneElement(icon, {
                        size: isMobile ? 16 : isTablet ? 18 : 20,
                        color
                    })}
                </Box>
            </Box>
            {chartData.length > 0 && (
                <Box sx={{ mt: 'auto', pt: 1 }}>
                    <MetricChart data={chartData} color={color} />
                </Box>
            )}
        </Paper>
    );
};
