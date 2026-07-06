import React from 'react';
import { Avatar, Box, IconButton, Tooltip, Typography, alpha, useMediaQuery, useTheme } from "@mui/material";
import { ChevronRight } from 'lucide-react';
import type { ActivityItemProps } from '../model/types.ts';

// Activity item component
export const ActivityItem = ({ icon, text, time, status = "default" }: ActivityItemProps) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const getStatusColor = () => {
        switch (status) {
            case "success": return theme.palette.success.main;
            case "warning": return theme.palette.warning.main;
            case "error": return theme.palette.error.main;
            case "info": return theme.palette.info.main;
            default: return theme.palette.primary.main;
        }
    };

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            py: 1.5,
            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`
        }}>
            <Avatar
                sx={{
                    width: 32,
                    height: 32,
                    backgroundColor: alpha(getStatusColor(), 0.1),
                }}
            >
                {React.cloneElement(icon, {
                    size: 16,
                    color: getStatusColor()
                })}
            </Avatar>

            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 500,
                        color: 'text.primary',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                    }}
                >
                    {text}
                </Typography>
                <Typography
                    variant="caption"
                    sx={{
                        color: 'text.secondary',
                        display: 'block'
                    }}
                >
                    {time}
                </Typography>
            </Box>

            {!isMobile && (
                <Tooltip title="View details">
                    <IconButton size="small">
                        <ChevronRight size={16} />
                    </IconButton>
                </Tooltip>
            )}
        </Box>
    );
};
