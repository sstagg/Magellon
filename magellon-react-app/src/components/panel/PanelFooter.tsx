import React from 'react';
import { Box, Typography, Paper, Chip, Stack, Divider } from '@mui/material';
import { useImageViewerStore } from './features/imageviewer/store/imageViewerStore';
import { Database, Image, Server, Settings } from 'lucide-react';

const PanelFooter = () => {
    // Get store state
    const {
        currentSession,
        currentImage,
        viewMode,
        activeTab
    } = useImageViewerStore();

    // Get app info
    const appVersion = "0.1.0"; // This should come from your app configuration
    const serverStatus = "Connected"; // This could be determined dynamically

    return (
        <Paper
            elevation={3}
            sx={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                padding: '8px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                zIndex: 1100, // Ensure it's above other content
                borderTop: '1px solid rgba(0, 0, 0, 0.12)'
            }}
        >
            {/* Left side - Session & Image Info */}
            <Stack direction="row" spacing={2} alignItems="center" divider={<Divider orientation="vertical" flexItem />}>
                <Box display="flex" alignItems="center">
                    <Database size={18} style={{ marginRight: 8 }} />
                    <Typography variant="body2">
                        Session: {currentSession?.name || 'None'}
                    </Typography>
                </Box>

                {currentImage && (
                    <Box display="flex" alignItems="center">
                        <Image size={18} style={{ marginRight: 8 }} />
                        <Typography variant="body2" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            Image: {currentImage.name}
                        </Typography>
                    </Box>
                )}
            </Stack>

            {/* Center - View Information */}
            <Stack direction="row" spacing={1}>
                <Chip
                    label={`View: ${viewMode}`}
                    size="small"
                    variant="outlined"
                    icon={<Settings size={16} />}
                />
                {activeTab && (
                    <Chip
                        label={`Tab: ${getTabName(activeTab)}`}
                        size="small"
                        variant="outlined"
                    />
                )}
            </Stack>

            {/* Right side - App Status */}
            <Stack direction="row" spacing={2} alignItems="center">
                <Box display="flex" alignItems="center">
                    <Server size={18} style={{ marginRight: 8 }} />
                    <Typography variant="body2">
                        Status: {serverStatus}
                    </Typography>
                </Box>
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