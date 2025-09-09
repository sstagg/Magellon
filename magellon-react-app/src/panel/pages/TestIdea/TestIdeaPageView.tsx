import React, { useState, useEffect } from 'react';
import { Box, Typography, IconButton, useTheme } from '@mui/material';
import { ChevronRight } from 'lucide-react';
import MicroscopeColumn from './MicroscopeColumn';
import PropertyExplorer from './PropertyExplorer';
import { MicroscopeComponent } from './MicroscopeComponentConfig';

const DRAWER_WIDTH = 240;

export const TestIdeaPageView: React.FC = () => {
    const theme = useTheme();
    const [isPropertyPanelOpen, setIsPropertyPanelOpen] = useState(true);
    const [selectedComponent, setSelectedComponent] = useState<MicroscopeComponent | null>(null);

    // Track drawer state from localStorage to adjust layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Listen for drawer state changes
    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    const handleComponentSelect = (component: MicroscopeComponent | null) => {
        setSelectedComponent(component);
        // Auto-open property panel when a component is selected
        if (component && !isPropertyPanelOpen) {
            setIsPropertyPanelOpen(true);
        }
    };

    const handleComponentUpdate = (updatedComponent: MicroscopeComponent) => {
        setSelectedComponent(updatedComponent);
        // You could also emit this update back to the MicroscopeColumn if needed
    };

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return (
        <Box sx={{
            minHeight: '100vh',
            backgroundColor: 'background.default',
            // Compensate for drawer margin and remove parent padding
            marginLeft: `-${leftMargin}px`,
            marginTop: '-24px', // Remove parent top padding
            marginBottom: '-24px', // Remove parent bottom padding
            marginRight: '-24px', // Remove parent right padding
            paddingLeft: `${leftMargin}px`, // Add back the drawer spacing
            width: `calc(100vw - ${leftMargin}px)`, // Full viewport width minus drawer
            maxWidth: 'none' // Override any max-width constraints
        }}>
            {/* Header */}
            <Box sx={{ p: 3, pb: 1 }}>
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
                height: 'calc(100vh - 140px)',
                position: 'relative'
            }}>
                {/* Microscope Column - Left side */}
                <Box sx={{
                    width: isPropertyPanelOpen ? '70%' : '100%',
                    height: '100%',
                    flexShrink: 0,
                    transition: theme.transitions.create(['width'], {
                        easing: theme.transitions.easing.easeInOut,
                        duration: theme.transitions.duration.standard,
                    })
                }}>
                    <MicroscopeColumn
                        selectedComponent={selectedComponent}
                        onComponentSelect={handleComponentSelect}
                    />
                </Box>

                {/* Property Panel - Right side */}
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
                            p: 2
                        }}>
                            <PropertyExplorer
                                component={selectedComponent}
                                onUpdate={handleComponentUpdate}
                            />
                        </Box>
                    )}
                </Box>

                {/* Toggle Button */}
                <IconButton
                    onClick={() => setIsPropertyPanelOpen(!isPropertyPanelOpen)}
                    sx={{
                        position: 'absolute',
                        top: 16,
                        right: isPropertyPanelOpen ? 'calc(30% - 20px)' : '16px',
                        zIndex: 1000,
                        backgroundColor: 'primary.main',
                        color: 'primary.contrastText',
                        width: 40,
                        height: 40,
                        borderRadius: '20px',
                        boxShadow: theme.shadows[4],
                        transition: theme.transitions.create(['right', 'background-color'], {
                            easing: theme.transitions.easing.easeInOut,
                            duration: theme.transitions.duration.standard,
                        }),
                        '&:hover': {
                            backgroundColor: 'primary.dark',
                            boxShadow: theme.shadows[6],
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
                >
                    <ChevronRight
                        size={20}
                        className="chevron-icon"
                    />
                </IconButton>

                {/* Status indicator for selected component */}
                {selectedComponent && (
                    <Box sx={{
                        position: 'absolute',
                        bottom: 16,
                        right: isPropertyPanelOpen ? 'calc(30% + 16px)' : '16px',
                        zIndex: 1000,
                        backgroundColor: selectedComponent.baseColor,
                        color: 'white',
                        px: 2,
                        py: 1,
                        borderRadius: 1,
                        boxShadow: theme.shadows[2],
                        transition: theme.transitions.create(['right'], {
                            easing: theme.transitions.easing.easeInOut,
                            duration: theme.transitions.duration.standard,
                        })
                    }}>
                        <Typography variant="caption" sx={{ fontWeight: 500 }}>
                            Selected: {selectedComponent.name}
                        </Typography>
                    </Box>
                )}
            </Box>
        </Box>
    );
};