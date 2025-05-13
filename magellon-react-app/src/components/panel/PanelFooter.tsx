import React from 'react';
import { Box, Typography, Paper, Chip, Stack, Divider, Tooltip, useMediaQuery, useTheme } from '@mui/material';
import { useImageViewerStore } from '../features/session_viewer/store/imageViewerStore';
import { Database, Image, Server, Settings } from 'lucide-react';

interface PanelFooterProps {
    drawerOpen: boolean;
    drawerWidth: number;
}

const PanelFooter: React.FC<PanelFooterProps> = ({ drawerOpen, drawerWidth }) => {
    // Get store state
    const {
        currentSession,
        currentImage,
        viewMode,
        activeTab
    } = useImageViewerStore();

    // Get app info
    const appVersion = "0.1.0";
    const serverStatus = "Connected";

    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Determine if the current theme is dark or light
    const isDarkMode = theme.palette.mode === 'dark';

    return (
        <Paper
            elevation={3}
            sx={{
                position: 'fixed',
                bottom: 0,
                left: drawerOpen ? drawerWidth : 0,
                right: 0,
                height: 56,
                padding: '8px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                zIndex: theme.zIndex.drawer - 1,
                borderTop: '1px solid',
                borderTopColor: isDarkMode
                    ? 'rgba(255, 255, 255, 0.12)'
                    : 'rgba(0, 0, 0, 0.12)',
                backgroundColor: isDarkMode
                    ? theme.palette.background.paper
                    : '#ffffff',
                transition: theme.transitions.create(['left', 'width'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.leavingScreen,
                }),
            }}
        >
            {/* Left side - Session & Image Info */}
            <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                divider={<Divider orientation="vertical" flexItem />}
            >
                <Tooltip title={`Session: ${currentSession?.name || 'None'}`}>
                    <Box display="flex" alignItems="center">
                        <Database size={16} style={{ marginRight: 4 }} />
                        <Typography
                            variant="body2"
                            sx={{
                                maxWidth: isMobile ? 60 : 150,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap'
                            }}
                        >
                            {isMobile ? '' : 'Session: '}{currentSession?.name || 'None'}
                        </Typography>
                    </Box>
                </Tooltip>

                {currentImage && (
                    <Tooltip title={`Image: ${currentImage.name}`}>
                        <Box display="flex" alignItems="center">
                            <Image size={16} style={{ marginRight: 4 }} />
                            <Typography
                                variant="body2"
                                sx={{
                                    maxWidth: isMobile ? 60 : 150,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap'
                                }}
                            >
                                {isMobile ? '' : 'Image: '}{currentImage.name}
                            </Typography>
                        </Box>
                    </Tooltip>
                )}
            </Stack>

            {/* Center - View Information (only show on tablet and above) */}
            {!isMobile && (
                <Stack direction="row" spacing={1}>
                    <Chip
                        label={`View: ${viewMode}`}
                        size="small"
                        variant="outlined"
                        icon={<Settings size={14} />}
                    />
                    {activeTab && !isTablet && (
                        <Chip
                            label={`Tab: ${getTabName(activeTab)}`}
                            size="small"
                            variant="outlined"
                        />
                    )}
                </Stack>
            )}

            {/* Right side - App Status */}
            <Stack direction="row" spacing={2} alignItems="center">
                {!isMobile && (
                    <Box display="flex" alignItems="center">
                        <Server size={16} style={{ marginRight: 4 }} />
                        <Typography variant="body2">
                            Status: {serverStatus}
                        </Typography>
                    </Box>
                )}
                <Typography variant="body2" color="textSecondary">
                    v{appVersion}
                </Typography>
            </Stack>
        </Paper>
    );
};

// Helper function to convert tab IDs to readable names
const getTabName = (tabId: string): string => {
    const tabNames: Record<string, string> = {
        '1': 'Image',
        '2': 'FFT',
        '3': 'Particle Picking',
        '5': 'CTF',
        '6': 'Frame Alignment',
        '7': 'Metadata'
    };
    return tabNames[tabId] || 'Unknown';
};

export default PanelFooter;