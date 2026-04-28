import React from "react";
import {
    Box,
    Button,
    Card,
    CardContent,
    Typography,
    Stack,
    IconButton,
    Alert,
    Skeleton,
    Chip,
    Divider,
    useTheme,
    Tooltip,
    ButtonGroup,
    alpha,
} from "@mui/material";
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import {
    Analytics,
    InfoOutlined as MuiInfoOutlined,
} from "@mui/icons-material";
import RefreshIcon from "@mui/icons-material/Refresh";
import DownloadIcon from "@mui/icons-material/Download";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import {
    Target,
    BarChart3,
    AlertCircle,
} from "lucide-react";
import { Timeline } from "@mui/icons-material";

export interface CTFAnalysisPanelProps {
    ctfData: any;
    isLoading: boolean;
    error: any;
    onRefresh: () => void;
    powerspecUrl: string | null;
    isPowerspecLoading: boolean;
    plotsUrl: string | null;
    isPlotsLoading: boolean;
    isMobile: boolean;
}

export const CTFAnalysisPanel: React.FC<CTFAnalysisPanelProps> = ({
    ctfData,
    isLoading,
    error,
    onRefresh,
    powerspecUrl,
    isPowerspecLoading,
    plotsUrl,
    isPlotsLoading,
    isMobile,
}) => {
    const theme = useTheme();
    const ImageCtfData = ctfData;
    const isCtfInfoError = error;

    return (
        <Stack spacing={4}>
            {isLoading ? (
                <Stack spacing={3}>
                    {/* Loading skeleton for metrics */}
                    <Grid container spacing={3}>
                        {[1, 2, 3, 4].map((item) => (
                            <Grid
                                key={item}
                                size={{
                                    xs: 12,
                                    sm: 6,
                                    md: 3
                                }}>
                                <Skeleton
                                    variant="rounded"
                                    height={160}
                                    sx={{
                                        borderRadius: 3,
                                        background: `linear-gradient(90deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(theme.palette.primary.main, 0.1)} 50%, ${alpha(theme.palette.primary.main, 0.05)} 100%)`
                                    }}
                                />
                            </Grid>
                        ))}
                    </Grid>

                    {/* Loading skeleton for images */}
                    <Grid container spacing={3}>
                        <Grid
                            size={{
                                xs: 12,
                                lg: 6
                            }}>
                            <Skeleton variant="rounded" height={450} sx={{ borderRadius: 3 }} />
                        </Grid>
                        <Grid
                            size={{
                                xs: 12,
                                lg: 6
                            }}>
                            <Skeleton variant="rounded" height={450} sx={{ borderRadius: 3 }} />
                        </Grid>
                    </Grid>
                </Stack>
            ) : isCtfInfoError ? (
                <Alert
                    severity="error"
                    icon={<AlertCircle size={20} />}
                    sx={{
                        borderRadius: 2,
                        backgroundColor: alpha(theme.palette.error.main, 0.08),
                        border: `1px solid ${alpha(theme.palette.error.main, 0.2)}`,
                    }}
                    action={
                        <Button
                            color="inherit"
                            size="small"
                            onClick={onRefresh}
                            startIcon={<RefreshIcon />}
                        >
                            Retry
                        </Button>
                    }
                >
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        Error loading CTF data
                    </Typography>
                    <Typography variant="body2" sx={{
                        color: "text.secondary"
                    }}>
                        {isCtfInfoError.message || 'Unable to fetch CTF analysis results'}
                    </Typography>
                </Alert>
            ) : ImageCtfData && ImageCtfData.defocus1 !== null ? (
                <>
                    {/* Header Section */}
                    <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box
                                    sx={{
                                        width: 48,
                                        height: 48,
                                        borderRadius: 2,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                                        color: 'white',
                                        boxShadow: `0 4px 12px ${alpha(theme.palette.primary.main, 0.3)}`,
                                    }}
                                >
                                    <Analytics />
                                </Box>
                                <Box>
                                    <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                                        CTF Analysis Results
                                    </Typography>
                                    <Typography variant="body2" sx={{
                                        color: "text.secondary"
                                    }}>
                                        Contrast Transfer Function parameters
                                    </Typography>
                                </Box>
                            </Box>

                            {!isMobile && (
                                <ButtonGroup variant="outlined" size="small">
                                    <Button startIcon={<RefreshIcon />} onClick={onRefresh}>
                                        Refresh
                                    </Button>
                                    <Button startIcon={<DownloadIcon />}>
                                        Export
                                    </Button>
                                </ButtonGroup>
                            )}
                        </Box>

                        <Divider sx={{ backgroundColor: alpha(theme.palette.divider, 0.08) }} />
                    </Box>

                    {/* Metrics Cards with modern design */}
                    <Grid container spacing={3}>
                        {/* Defocus 1 Card */}
                        <Grid
                            size={{
                                xs: 12,
                                sm: 6,
                                md: 3
                            }}>
                            <Card
                                elevation={0}
                                sx={{
                                    height: '100%',
                                    background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.08)}, ${alpha(theme.palette.primary.main, 0.02)})`,
                                    border: `1px solid ${alpha(theme.palette.primary.main, 0.15)}`,
                                    borderRadius: 3,
                                    position: 'relative',
                                    overflow: 'hidden',
                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: `0 12px 24px ${alpha(theme.palette.primary.main, 0.15)}`,
                                        borderColor: alpha(theme.palette.primary.main, 0.3),
                                    }
                                }}
                            >
                                <CardContent sx={{ p: 3 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                        <Box
                                            sx={{
                                                width: 44,
                                                height: 44,
                                                borderRadius: 2,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                color: theme.palette.primary.main,
                                            }}
                                        >
                                            <Target size={20} />
                                        </Box>
                                        {ImageCtfData.defocus1 >= 0.5 && ImageCtfData.defocus1 <= 3.0 && (
                                            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
                                        )}
                                    </Box>

                                    <Typography
                                        variant="h4"
                                        sx={{
                                            fontWeight: 700,
                                            color: theme.palette.primary.main,
                                            mb: 0.5,
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        {ImageCtfData.defocus1?.toFixed(2)}
                                        <Typography
                                            component="span"
                                            variant="body1"
                                            sx={{
                                                ml: 0.5,
                                                fontWeight: 400,
                                                color: 'text.secondary',
                                            }}
                                        >
                                            μm
                                        </Typography>
                                    </Typography>

                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: "text.secondary",
                                            fontWeight: 600
                                        }}>
                                        Defocus 1
                                    </Typography>
                                </CardContent>

                                {/* Decorative element */}
                                <Box
                                    sx={{
                                        position: 'absolute',
                                        bottom: -20,
                                        right: -20,
                                        width: 80,
                                        height: 80,
                                        borderRadius: '50%',
                                        backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                    }}
                                />
                            </Card>
                        </Grid>

                        {/* Defocus 2 Card */}
                        <Grid
                            size={{
                                xs: 12,
                                sm: 6,
                                md: 3
                            }}>
                            <Card
                                elevation={0}
                                sx={{
                                    height: '100%',
                                    background: `linear-gradient(135deg, ${alpha(theme.palette.secondary.main, 0.08)}, ${alpha(theme.palette.secondary.main, 0.02)})`,
                                    border: `1px solid ${alpha(theme.palette.secondary.main, 0.15)}`,
                                    borderRadius: 3,
                                    position: 'relative',
                                    overflow: 'hidden',
                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: `0 12px 24px ${alpha(theme.palette.secondary.main, 0.15)}`,
                                        borderColor: alpha(theme.palette.secondary.main, 0.3),
                                    }
                                }}
                            >
                                <CardContent sx={{ p: 3 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                        <Box
                                            sx={{
                                                width: 44,
                                                height: 44,
                                                borderRadius: 2,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                                color: theme.palette.secondary.main,
                                            }}
                                        >
                                            <Target size={20} />
                                        </Box>
                                        {ImageCtfData.defocus2 >= 0.5 && ImageCtfData.defocus2 <= 3.0 && (
                                            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
                                        )}
                                    </Box>

                                    <Typography
                                        variant="h4"
                                        sx={{
                                            fontWeight: 700,
                                            color: theme.palette.secondary.main,
                                            mb: 0.5,
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        {ImageCtfData.defocus2?.toFixed(2)}
                                        <Typography
                                            component="span"
                                            variant="body1"
                                            sx={{
                                                ml: 0.5,
                                                fontWeight: 400,
                                                color: 'text.secondary',
                                            }}
                                        >
                                            μm
                                        </Typography>
                                    </Typography>

                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: "text.secondary",
                                            fontWeight: 600
                                        }}>
                                        Defocus 2
                                    </Typography>
                                </CardContent>

                                <Box
                                    sx={{
                                        position: 'absolute',
                                        bottom: -20,
                                        right: -20,
                                        width: 80,
                                        height: 80,
                                        borderRadius: '50%',
                                        backgroundColor: alpha(theme.palette.secondary.main, 0.05),
                                    }}
                                />
                            </Card>
                        </Grid>

                        {/* Angle Astigmatism Card */}
                        <Grid
                            size={{
                                xs: 12,
                                sm: 6,
                                md: 3
                            }}>
                            <Card
                                elevation={0}
                                sx={{
                                    height: '100%',
                                    background: `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.08)}, ${alpha(theme.palette.warning.main, 0.02)})`,
                                    border: `1px solid ${alpha(theme.palette.warning.main, 0.15)}`,
                                    borderRadius: 3,
                                    position: 'relative',
                                    overflow: 'hidden',
                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: `0 12px 24px ${alpha(theme.palette.warning.main, 0.15)}`,
                                        borderColor: alpha(theme.palette.warning.main, 0.3),
                                    }
                                }}
                            >
                                <CardContent sx={{ p: 3 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                        <Box
                                            sx={{
                                                width: 44,
                                                height: 44,
                                                borderRadius: 2,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                backgroundColor: alpha(theme.palette.warning.main, 0.1),
                                                color: theme.palette.warning.main,
                                            }}
                                        >
                                            <Timeline />
                                        </Box>
                                    </Box>

                                    <Typography
                                        variant="h4"
                                        sx={{
                                            fontWeight: 700,
                                            color: theme.palette.warning.main,
                                            mb: 0.5,
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        {ImageCtfData.angleAstigmatism?.toFixed(1)}
                                        <Typography
                                            component="span"
                                            variant="body1"
                                            sx={{
                                                ml: 0.5,
                                                fontWeight: 400,
                                                color: 'text.secondary',
                                            }}
                                        >
                                            °
                                        </Typography>
                                    </Typography>

                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: "text.secondary",
                                            fontWeight: 600
                                        }}>
                                        Angle Astigmatism
                                    </Typography>
                                </CardContent>

                                <Box
                                    sx={{
                                        position: 'absolute',
                                        bottom: -20,
                                        right: -20,
                                        width: 80,
                                        height: 80,
                                        borderRadius: '50%',
                                        backgroundColor: alpha(theme.palette.warning.main, 0.05),
                                    }}
                                />
                            </Card>
                        </Grid>

                        {/* Resolution Card */}
                        <Grid
                            size={{
                                xs: 12,
                                sm: 6,
                                md: 3
                            }}>
                            <Card
                                elevation={0}
                                sx={{
                                    height: '100%',
                                    background: `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.08)}, ${alpha(theme.palette.success.main, 0.02)})`,
                                    border: `1px solid ${alpha(theme.palette.success.main, 0.15)}`,
                                    borderRadius: 3,
                                    position: 'relative',
                                    overflow: 'hidden',
                                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: `0 12px 24px ${alpha(theme.palette.success.main, 0.15)}`,
                                        borderColor: alpha(theme.palette.success.main, 0.3),
                                    }
                                }}
                            >
                                <CardContent sx={{ p: 3 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                                        <Box
                                            sx={{
                                                width: 44,
                                                height: 44,
                                                borderRadius: 2,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                backgroundColor: alpha(theme.palette.success.main, 0.1),
                                                color: theme.palette.success.main,
                                            }}
                                        >
                                            <BarChart3 size={20} />
                                        </Box>
                                        {ImageCtfData.resolution <= 3.5 && (
                                            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
                                        )}
                                    </Box>

                                    <Typography
                                        variant="h4"
                                        sx={{
                                            fontWeight: 700,
                                            color: theme.palette.success.main,
                                            mb: 0.5,
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        {ImageCtfData.resolution?.toFixed(2)}
                                        <Typography
                                            component="span"
                                            variant="body1"
                                            sx={{
                                                ml: 0.5,
                                                fontWeight: 400,
                                                color: 'text.secondary',
                                            }}
                                        >
                                            Å
                                        </Typography>
                                    </Typography>

                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: "text.secondary",
                                            fontWeight: 600
                                        }}>
                                        Resolution 50%
                                    </Typography>
                                </CardContent>

                                <Box
                                    sx={{
                                        position: 'absolute',
                                        bottom: -20,
                                        right: -20,
                                        width: 80,
                                        height: 80,
                                        borderRadius: '50%',
                                        backgroundColor: alpha(theme.palette.success.main, 0.05),
                                    }}
                                />
                            </Card>
                        </Grid>
                    </Grid>

                    {/* CTF Images Section */}
                    <Grid container spacing={3}>
                        {/* Power Spectrum */}
                        <Grid
                            size={{
                                xs: 12,
                                lg: 6
                            }}>
                            <Paper
                                elevation={0}
                                sx={{
                                    borderRadius: 3,
                                    overflow: 'hidden',
                                    backgroundColor: 'background.paper',
                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    position: 'relative',
                                }}
                            >
                                <Box
                                    sx={{
                                        p: 2.5,
                                        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                        background: `linear-gradient(to bottom, ${alpha(theme.palette.background.paper, 0.9)}, transparent)`,
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                            Power Spectrum
                                        </Typography>
                                        <ButtonGroup size="small" variant="text">
                                            <Tooltip title="Download">
                                                <IconButton size="small">
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Fullscreen">
                                                <IconButton size="small">
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </ButtonGroup>
                                    </Box>
                                </Box>

                                <Box
                                    sx={{
                                        backgroundColor: '#000',
                                        minHeight: 400,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        p: 2,
                                    }}
                                >
                                    {isPowerspecLoading ? (
                                        <Skeleton variant="rectangular" width={400} height={400} />
                                    ) : powerspecUrl ? (
                                        <img
                                            src={powerspecUrl}
                                            alt="CTF power spectrum"
                                            style={{
                                                maxWidth: '100%',
                                                height: 'auto',
                                                borderRadius: '8px',
                                            }}
                                        />
                                    ) : (
                                        <Typography sx={{
                                            color: "text.secondary"
                                        }}>Image not available</Typography>
                                    )}
                                </Box>
                            </Paper>
                        </Grid>

                        {/* CTF Plots */}
                        <Grid
                            size={{
                                xs: 12,
                                lg: 6
                            }}>
                            <Paper
                                elevation={0}
                                sx={{
                                    borderRadius: 3,
                                    overflow: 'hidden',
                                    backgroundColor: 'background.paper',
                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    position: 'relative',
                                }}
                            >
                                <Box
                                    sx={{
                                        p: 2.5,
                                        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                        background: `linear-gradient(to bottom, ${alpha(theme.palette.background.paper, 0.9)}, transparent)`,
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                            CTF Fit Plots
                                        </Typography>
                                        <ButtonGroup size="small" variant="text">
                                            <Tooltip title="Download">
                                                <IconButton size="small">
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Fullscreen">
                                                <IconButton size="small">
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </ButtonGroup>
                                    </Box>
                                </Box>

                                <Box
                                    sx={{
                                        backgroundColor: '#000',
                                        minHeight: 400,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        p: 2,
                                    }}
                                >
                                    {isPlotsLoading ? (
                                        <Skeleton variant="rectangular" width={400} height={400} />
                                    ) : plotsUrl ? (
                                        <img
                                            src={plotsUrl}
                                            alt="CTF plots"
                                            style={{
                                                maxWidth: '100%',
                                                height: 'auto',
                                                borderRadius: '8px',
                                            }}
                                        />
                                    ) : (
                                        <Typography sx={{
                                            color: "text.secondary"
                                        }}>Image not available</Typography>
                                    )}
                                </Box>
                            </Paper>
                        </Grid>
                    </Grid>

                    {/* Additional Analysis Info */}
                    <Card
                        elevation={0}
                        sx={{
                            borderRadius: 3,
                            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                            backgroundColor: alpha(theme.palette.primary.main, 0.02),
                            overflow: 'hidden',
                        }}
                    >
                        <CardContent sx={{ p: 3 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
                                <Box
                                    sx={{
                                        width: 32,
                                        height: 32,
                                        borderRadius: 1.5,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                        color: theme.palette.primary.main,
                                    }}
                                >
                                    <MuiInfoOutlined fontSize="small" />
                                </Box>
                                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                    Detailed Analysis
                                </Typography>
                            </Box>

                            <Grid container spacing={3}>
                                <Grid
                                    size={{
                                        xs: 12,
                                        sm: 6,
                                        md: 3
                                    }}>
                                    <Box>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: "text.secondary",
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.5
                                            }}>
                                            Defocus Difference
                                        </Typography>
                                        <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                            {Math.abs(ImageCtfData.defocus1 - ImageCtfData.defocus2)?.toFixed(3)} μm
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid
                                    size={{
                                        xs: 12,
                                        sm: 6,
                                        md: 3
                                    }}>
                                    <Box>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: "text.secondary",
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.5
                                            }}>
                                            Average Defocus
                                        </Typography>
                                        <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                            {((ImageCtfData.defocus1 + ImageCtfData.defocus2) / 2)?.toFixed(3)} μm
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid
                                    size={{
                                        xs: 12,
                                        sm: 6,
                                        md: 3
                                    }}>
                                    <Box>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: "text.secondary",
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.5
                                            }}>
                                            Astigmatism Ratio
                                        </Typography>
                                        <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                                            {(Math.abs(ImageCtfData.defocus1 - ImageCtfData.defocus2) /
                                                ((ImageCtfData.defocus1 + ImageCtfData.defocus2) / 2) * 100)?.toFixed(1)}%
                                        </Typography>
                                    </Box>
                                </Grid>
                                <Grid
                                    size={{
                                        xs: 12,
                                        sm: 6,
                                        md: 3
                                    }}>
                                    <Box>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: "text.secondary",
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.5
                                            }}>
                                            Quality Assessment
                                        </Typography>
                                        <Box sx={{ mt: 0.5 }}>
                                            <Chip
                                                label="Good Quality"
                                                size="small"
                                                color="success"
                                                icon={<CheckCircleIcon />}
                                                sx={{
                                                    fontWeight: 600,
                                                    '& .MuiChip-icon': { fontSize: 16 }
                                                }}
                                            />
                                        </Box>
                                    </Box>
                                </Grid>
                            </Grid>
                        </CardContent>
                    </Card>
                </>
            ) : (
                <Alert
                    severity="info"
                    icon={<MuiInfoOutlined />}
                    sx={{
                        borderRadius: 3,
                        backgroundColor: alpha(theme.palette.info.main, 0.08),
                        border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
                    }}
                >
                    <Typography variant="body1" sx={{ fontWeight: 600, mb: 1 }}>
                        No CTF data available
                    </Typography>
                    <Typography variant="body2" sx={{
                        color: "text.secondary"
                    }}>
                        CTF analysis has not been performed for this image yet. Please run CTF estimation to view results.
                    </Typography>
                </Alert>
            )}
        </Stack>
    );
};

export default CTFAnalysisPanel;
