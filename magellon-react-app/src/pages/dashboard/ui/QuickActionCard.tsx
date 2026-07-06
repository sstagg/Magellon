import React from 'react';
import { Box, Paper, Typography, alpha, useTheme } from "@mui/material";
import type { QuickActionCardProps } from '../model/types.ts';

// Quick action card component
export const QuickActionCard = ({ title, icon, color, onClick, featured = false }: QuickActionCardProps) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={featured ? 2 : 1}
            sx={{
                p: { xs: 1, sm: 1.5 },
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                borderRadius: 2,
                cursor: 'pointer',
                height: '100%',
                background: featured
                    ? `linear-gradient(135deg, ${alpha(color, 0.2)}, ${alpha(color, 0.1)})`
                    : alpha(theme.palette.background.paper, 0.7),
                border: `1px solid ${featured ? alpha(color, 0.3) : alpha(theme.palette.divider, 0.8)}`,
                transition: 'all 0.2s ease',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 2,
                    background: featured
                        ? `linear-gradient(135deg, ${alpha(color, 0.25)}, ${alpha(color, 0.15)})`
                        : alpha(theme.palette.background.paper, 0.9),
                }
            }}
            onClick={onClick}
        >
            <Box sx={{
                backgroundColor: alpha(color, featured ? 0.2 : 0.1),
                p: 0.7,
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                {React.cloneElement(icon, {
                    size: 18,
                    color
                })}
            </Box>
            <Typography
                variant="body2"
                sx={{
                    fontWeight: featured ? 600 : 500,
                    color: featured ? color : 'text.primary',
                }}
            >
                {title}
            </Typography>
        </Paper>
    );
};
