import React, { useState } from 'react';
import { Box, Typography, IconButton, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { ChevronRight } from 'lucide-react';

// Import your existing components (adjust these import paths)
import MicroscopeColumn from './MicroscopeColumn';
import PropertyExplorer from './PropertyExplorer';

export const TestIdeaPageView: React.FC = () => {
    const theme = useTheme();
    const [isPropertyPanelOpen, setIsPropertyPanelOpen] = useState(true);

    return (
        <Box sx={{ minHeight: '100vh', backgroundColor: 'grey.100' }}>
            {/* Header */}
            <Box sx={{ p: 2, pb: 0 }}>
                <Typography
                    variant="h4"
                    sx={{
                        fontWeight: 'bold',
                        color: 'text.primary',
                        mb: 1
                    }}
                >
                    Microscope Control Interface
                </Typography>
                <Typography variant="body1" sx={{ color: 'text.secondary' }}>
                    Interactive microscope configuration and property management
                </Typography>
            </Box>

            {/* Main layout container */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'row',
                width: '100%',
                height: 'calc(100vh - 120px)',
                position: 'relative'
            }}>
                {/* Microscope Column - Left 70% */}
                <Box sx={{
                    width: '70%',
                    height: '100%',
                    flexShrink: 0
                }}>
                    <MicroscopeColumn />
                </Box>

                {/* Property Panel - Right 30% */}
                <Box sx={{
                    width: isPropertyPanelOpen ? '30%' : '0%',
                    height: '100%',
                    flexShrink: 0,
                    borderLeft: isPropertyPanelOpen ? `1px solid ${theme.palette.divider}` : 'none',
                    overflow: 'hidden',
                    backgroundColor: 'background.paper',
                    transition: theme.transitions.create(['width'], {
                        easing: theme.transitions.easing.easeInOut,
                        duration: theme.transitions.duration.standard,
                    })
                }}>
                    {isPropertyPanelOpen && (
                        <Box sx={{
                            width: '100%',
                            height: '100%',
                            p: 2,
                            overflowY: 'auto'
                        }}>
                            <PropertyExplorer />
                        </Box>
                    )}
                </Box>

                {/* Toggle Button */}
                <IconButton
                    onClick={() => setIsPropertyPanelOpen(!isPropertyPanelOpen)}
                    sx={{
                        position: 'absolute',
                        top: 2,
                        right: isPropertyPanelOpen ? 'calc(30% + 8px)' : '8px',
                        zIndex: 1000,
                        backgroundColor: 'primary.main',
                        color: 'primary.contrastText',
                        borderRadius: '8px 0 0 8px',
                        boxShadow: theme.shadows[4],
                        transition: theme.transitions.create(['right', 'background-color'], {
                            easing: theme.transitions.easing.easeInOut,
                            duration: theme.transitions.duration.standard,
                        }),
                        '&:hover': {
                            backgroundColor: 'primary.dark',
                        },
                        '& .chevron-icon': {
                            transform: isPropertyPanelOpen ? 'rotate(0deg)' : 'rotate(180deg)',
                            transition: theme.transitions.create(['transform'], {
                                easing: theme.transitions.easing.easeInOut,
                                duration: theme.transitions.duration.standard,
                            })
                        }
                    }}
                    title={isPropertyPanelOpen ? "Hide Properties" : "Show Properties"}
                    size="small"
                >
                    <ChevronRight
                        size={20}
                        className="chevron-icon"
                    />
                </IconButton>
            </Box>
        </Box>
    );
};