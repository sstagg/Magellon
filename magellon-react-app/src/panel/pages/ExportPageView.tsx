import React, { useState, useEffect } from 'react';
import {
    Box,
    useTheme,
    useMediaQuery,
    Typography,
    Card,
    CardContent,
    Tab
} from '@mui/material';
import { RelionExportComponent } from '../components/RelionExportComponent.tsx';
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import { DownloadIcon } from "lucide-react";
// Import other export components as needed
// import { CryoSparcExportComponent } from '../../components/features/export/CryoSparcExportComponent.tsx';
// import { StarFileExportComponent } from '../../components/features/export/StarFileExportComponent.tsx';

const DRAWER_WIDTH = 240;

export const ExportPageView = () => {
    // Theme and responsive breakpoints
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Tab state
    const [value, setValue] = useState('1');

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

    const handleChange = (event: React.SyntheticEvent, newValue: string) => {
        setValue(newValue);
    };

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return (
        <Box sx={{
            position: 'fixed',
            top: 64, // Account for header
            left: leftMargin,
            right: 0,
            bottom: 0,
            zIndex: 1050, // Below drawer but above content
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Scrollable Content Container */}
            <Box sx={{
                flex: 1,
                overflow: 'auto',
                p: { xs: 2, sm: 3, md: 4 }
            }}>
                {/* Header Section */}
                <Box sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    alignItems: { xs: 'flex-start', sm: 'center' },
                    gap: { xs: 1, sm: 2 },
                    mb: { xs: 2, sm: 3, md: 4 }
                }}>
                    <DownloadIcon
                        width={isMobile ? 36 : 48}
                        height={isMobile ? 36 : 48}
                        color="#0000FF"
                        className="large-blue-icon"
                    />
                    <Box>
                        <Typography
                            variant={isMobile ? "h5" : "h4"}
                            sx={{
                                fontWeight: 600,
                                fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' }
                            }}
                        >
                            Magellon Data Exporter
                        </Typography>
                        <Typography
                            variant="body1"
                            color="textSecondary"
                            sx={{
                                mt: 0.5,
                                fontSize: { xs: '0.875rem', sm: '1rem' }
                            }}
                        >
                            Export your session data to various external formats for analysis
                        </Typography>
                    </Box>
                </Box>

                {/* Main Content Area */}
                <Box sx={{
                    width: '100%',
                    maxWidth: '100%',
                    mx: 'auto'
                }}>
                    <TabContext value={value}>
                        {/* Tab Navigation */}
                        <Box sx={{
                            borderBottom: 1,
                            borderColor: 'divider',
                            mb: { xs: 2, sm: 3 }
                        }}>
                            <TabList
                                onChange={handleChange}
                                aria-label="export options"
                                variant={isMobile ? "scrollable" : "standard"}
                                scrollButtons={isMobile ? "auto" : false}
                                sx={{
                                    '& .MuiTab-root': {
                                        fontSize: { xs: '0.875rem', sm: '1rem' },
                                        minHeight: { xs: 40, sm: 48 },
                                        textTransform: 'none',
                                        fontWeight: 500
                                    }
                                }}
                            >
                                <Tab label="RELION" value="1"/>
                                {/* Add more export types as needed */}
                                {/* <Tab label="CryoSPARC" value="2"/>
                                <Tab label="Star File" value="3"/> */}
                            </TabList>
                        </Box>

                        {/* Tab Content Panels */}
                        <Box sx={{
                            width: '100%',
                            '& .MuiTabPanel-root': {
                                p: 0
                            }
                        }}>
                            <TabPanel value="1">
                                <Card
                                    elevation={1}
                                    sx={{
                                        borderRadius: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        overflow: 'hidden'
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 2, sm: 3, md: 4 },
                                        '&:last-child': { pb: { xs: 2, sm: 3, md: 4 } }
                                    }}>
                                        <RelionExportComponent />
                                    </CardContent>
                                </Card>
                            </TabPanel>

                            {/* Add more tab panels as needed */}
                            {/* <TabPanel value="2">
                                <Card
                                    elevation={1}
                                    sx={{
                                        borderRadius: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        overflow: 'hidden'
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 2, sm: 3, md: 4 },
                                        '&:last-child': { pb: { xs: 2, sm: 3, md: 4 } }
                                    }}>
                                        <CryoSparcExportComponent />
                                    </CardContent>
                                </Card>
                            </TabPanel> */}
                        </Box>
                    </TabContext>
                </Box>
            </Box>
        </Box>
    );
};