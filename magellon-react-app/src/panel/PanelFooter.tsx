import React from 'react';
import {
    Box,
    Typography,
    Paper,
    Chip,
    Stack,
    Divider,
    Tooltip,
    useMediaQuery,
    useTheme,
    alpha
} from '@mui/material';
import {
    Database,
    Image as ImageIcon,
    Server,
    Settings,
    Info,
    ExternalLink
} from 'lucide-react';
import { useImageViewerStore } from '../components/features/session_viewer/store/imageViewerStore.ts';
import { ImagesBreadcrumbs } from '../components/features/session_viewer/ImagesBreadcrumbs.tsx';

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

    // App info
    const appVersion = "0.1.0";
    const serverStatus = "Connected";

    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // Determine if the current theme is dark or light
    const isDarkMode = theme.palette.mode === 'dark';

    // Get session name or display "None" if not available
    const sessionName = currentSession?.name || 'None';

    // Get image name or display "None" if not available
    const imageName = currentImage?.name || 'None';

    // Get detailed image info for tooltip
    const imageTooltipContent = currentImage
        ? `Name: ${currentImage.name}
       Defocus: ${currentImage.defocus || 'N/A'} μm
       Mag: ${currentImage.mag || 'N/A'}
       Pixel Size: ${currentImage.pixelSize || 'N/A'} Å/pix`
        : 'No image selected';

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
                backdropFilter: 'blur(8px)',
                boxShadow: isDarkMode
                    ? '0px -2px 10px rgba(0, 0, 0, 0.2)'
                    : '0px -2px 10px rgba(0, 0, 0, 0.05)',
            }}
        >
            {/* Left side - Session & Image Info */}
            <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                divider={<Divider orientation="vertical" flexItem />}
            >
                <Tooltip title={`Session: ${sessionName}`}>
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
                            {isMobile ? '' : 'Session: '}{sessionName}
                        </Typography>
                    </Box>
                </Tooltip>

                {currentImage && (
                    <Tooltip
                        title={
                            <Box component="div" sx={{ whiteSpace: 'pre-line' }}>
                                {imageTooltipContent}
                            </Box>
                        }
                    >
                        <Box display="flex" alignItems="center">
                            <ImageIcon size={16} style={{ marginRight: 4 }} />
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

                {/* Show breadcrumbs on tablet and larger screens if image is available */}
                {!isMobile && currentImage && currentImage.name && (
                    <Box sx={{ display: { xs: 'none', md: 'block' } }}>
                        <ImagesBreadcrumbs name={currentImage.name} />
                    </Box>
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
                        sx={{
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            borderColor: alpha(theme.palette.primary.main, 0.2),
                            '& .MuiChip-label': {
                                fontWeight: 500,
                            }
                        }}
                    />
                    {activeTab && !isTablet && (
                        <Chip
                            label={`Tab: ${getTabName(activeTab)}`}
                            size="small"
                            variant="outlined"
                            icon={<Info size={14} />}
                            sx={{
                                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                borderColor: alpha(theme.palette.secondary.main, 0.2),
                                '& .MuiChip-label': {
                                    fontWeight: 500,
                                }
                            }}
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
                            Status: <span style={{ color: '#4ade80' }}>{serverStatus}</span>
                        </Typography>
                    </Box>
                )}
                <Typography
                    variant="body2"
                    color="textSecondary"
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5
                    }}
                >
                    <ExternalLink size={14} />
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