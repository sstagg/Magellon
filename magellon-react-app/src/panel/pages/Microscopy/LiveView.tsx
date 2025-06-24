import React from 'react';
import {
    Card,
    CardHeader,
    CardContent,
    Typography,
    Box,
    Paper,
    IconButton,
    alpha,
    useTheme
} from '@mui/material';
import {
    Camera as CameraIcon,
    Visibility as VisibilityIcon,
    VisibilityOff as VisibilityOffIcon,
    Fullscreen as FullscreenIcon
} from '@mui/icons-material';
import { useMicroscopeStore } from './microscopeStore';

export const LiveView: React.FC = () => {
    const theme = useTheme();
    const {
        lastImage,
        lastFFT,
        showFFT,
        setShowFFT
    } = useMicroscopeStore();

    return (
        <Card sx={{ flex: 1 }}>
            <CardHeader
                title={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CameraIcon />
                        <Typography variant="h6">Live View</Typography>
                    </Box>
                }
                action={
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <IconButton
                            size="small"
                            onClick={() => setShowFFT(!showFFT)}
                            color={showFFT ? "primary" : "default"}
                            title="Toggle FFT overlay"
                        >
                            {showFFT ? <VisibilityIcon /> : <VisibilityOffIcon />}
                        </IconButton>
                        <IconButton
                            size="small"
                            title="Fullscreen"
                        >
                            <FullscreenIcon />
                        </IconButton>
                    </Box>
                }
            />
            <CardContent>
                <Box sx={{
                    aspectRatio: '1',
                    backgroundColor: 'action.hover',
                    borderRadius: 1,
                    overflow: 'hidden',
                    position: 'relative',
                    minHeight: 300
                }}>
                    {lastImage ? (
                        <>
                            <img
                                src={lastImage}
                                alt="Acquired"
                                style={{
                                    width: '100%',
                                    height: '100%',
                                    objectFit: 'contain',
                                    backgroundColor: '#000'
                                }}
                            />
                            {showFFT && lastFFT && (
                                <Paper
                                    elevation={3}
                                    sx={{
                                        position: 'absolute',
                                        bottom: 8,
                                        right: 8,
                                        width: 80,
                                        height: 80,
                                        overflow: 'hidden',
                                        border: `2px solid ${theme.palette.primary.main}`,
                                        borderRadius: 1
                                    }}
                                >
                                    <img
                                        src={lastFFT}
                                        alt="FFT"
                                        style={{
                                            width: '100%',
                                            height: '100%',
                                            objectFit: 'contain'
                                        }}
                                    />
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            position: 'absolute',
                                            bottom: 0,
                                            left: 0,
                                            right: 0,
                                            backgroundColor: alpha(theme.palette.background.paper, 0.8),
                                            textAlign: 'center',
                                            fontSize: '0.6rem',
                                            py: 0.25
                                        }}
                                    >
                                        FFT
                                    </Typography>
                                </Paper>
                            )}
                        </>
                    ) : (
                        <Box sx={{
                            width: '100%',
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 2
                        }}>
                            <CameraIcon sx={{ fontSize: 48, color: 'text.secondary' }} />
                            <Typography color="text.secondary" variant="body2">
                                No image acquired yet
                            </Typography>
                            <Typography color="text.secondary" variant="caption">
                                Click "Acquire Image" to capture
                            </Typography>
                        </Box>
                    )}
                </Box>

                {lastImage && (
                    <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        <Box sx={{
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            px: 1,
                            py: 0.5,
                            borderRadius: 1
                        }}>
                            <Typography variant="caption" color="primary.main">
                                ● Live
                            </Typography>
                        </Box>
                        {showFFT && (
                            <Box sx={{
                                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                px: 1,
                                py: 0.5,
                                borderRadius: 1
                            }}>
                                <Typography variant="caption" color="secondary.main">
                                    FFT Enabled
                                </Typography>
                            </Box>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};