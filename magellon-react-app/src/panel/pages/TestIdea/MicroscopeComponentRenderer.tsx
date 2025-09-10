import React from 'react';
import { motion } from 'framer-motion';
import {
    Box,
    Paper,
    Typography,
    useTheme,
    Chip,
    alpha
} from '@mui/material';
import { MicroscopeComponent } from './MicroscopeComponentConfig.ts';
import ElectronParticle from './ElectronParticle';

interface MicroscopeComponentRendererProps {
    component: MicroscopeComponent;
    isHovered: boolean;
    isSelected: boolean;
    onHover: () => void;
    onLeave: () => void;
    onSelect: () => void;
    index: number;
}

const MicroscopeComponentRenderer: React.FC<MicroscopeComponentRendererProps> = ({
                                                                                     component,
                                                                                     isHovered,
                                                                                     isSelected,
                                                                                     onHover,
                                                                                     onLeave,
                                                                                     onSelect,
                                                                                     index
                                                                                 }) => {
    const theme = useTheme();

    const getShapeStyles = () => {
        const baseWidth = 140; // Consistent base width
        const minHeight = 70;  // Increased minimum height for better text readability
        const maxHeight = 90;  // Increased maximum height

        // Calculate height based on component type for visual hierarchy
        const heightMap: Record<string, number> = {
            'source': maxHeight,
            'lens': 78,
            'aperture': minHeight,
            'detector': 80,
            'camera': maxHeight,
            'sample': minHeight + 4,
            'electrode': 76,
            'coils': 76
        };

        return {
            width: baseWidth,
            height: heightMap[component.type] || 78,
            borderRadius: component.shape === 'lens' || component.shape === 'source' ? '50%' : theme.shape.borderRadius
        };
    };

    const renderComponentIcon = () => {
        const iconStyle = {
            width: 24,
            height: 24,
            opacity: 0.7
        };

        switch (component.shape) {
            case 'source':
                return (
                    <Box sx={{ ...iconStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Box
                            sx={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                bgcolor: '#FDE047',
                                boxShadow: `0 0 8px ${alpha('#FDE047', 0.6)}`
                            }}
                        />
                    </Box>
                );
            case 'lens':
                return (
                    <Box sx={{ ...iconStyle, border: `2px solid ${alpha(theme.palette.common.white, 0.6)}`, borderRadius: '50%' }} />
                );
            case 'aperture':
                return (
                    <Box sx={{
                        ...iconStyle,
                        border: `2px solid ${alpha(theme.palette.common.white, 0.6)}`,
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: alpha(theme.palette.common.black, 0.4) }} />
                    </Box>
                );
            case 'detector':
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha('#10B981', 0.2),
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{ width: 8, height: 8, bgcolor: '#10B981', borderRadius: '50%' }} />
                    </Box>
                );
            case 'camera':
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha('#3B82F6', 0.2),
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Box sx={{
                            width: 12,
                            height: 8,
                            border: `1px solid ${alpha('#3B82F6', 0.8)}`,
                            borderRadius: 0.5
                        }} />
                    </Box>
                );
            default:
                return (
                    <Box sx={{
                        ...iconStyle,
                        bgcolor: alpha(component.baseColor, 0.3),
                        borderRadius: 1
                    }} />
                );
        }
    };

    const shapeStyles = getShapeStyles();

    return (
        <>
            <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.08 }}
                whileHover={{ scale: 1.02 }}
                style={{ marginBottom: theme.spacing(2) }}
                onMouseEnter={onHover}
                onMouseLeave={onLeave}
                onClick={onSelect}
            >
                <Paper
                    elevation={isHovered ? 8 : isSelected ? 6 : 2}
                    sx={{
                        ...shapeStyles,
                        position: 'relative',
                        cursor: 'pointer',
                        overflow: 'hidden',
                        background: `linear-gradient(135deg, ${component.baseColor}, ${alpha(component.baseColor, 0.8)})`,
                        border: isSelected ? `2px solid ${theme.palette.primary.main}` : `1px solid ${alpha(theme.palette.common.white, 0.2)}`,
                        transition: theme.transitions.create(['transform', 'box-shadow', 'border-color'], {
                            duration: theme.transitions.duration.short,
                        }),
                        '&::before': {
                            content: '""',
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            height: '30%',
                            background: `linear-gradient(to bottom, ${alpha(theme.palette.common.white, 0.3)}, transparent)`,
                            pointerEvents: 'none'
                        }
                    }}
                >
                    {/* Content Container */}
                    <Box
                        sx={{
                            position: 'relative',
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            p: 2,
                            zIndex: 1
                        }}
                    >
                        {/* Icon */}
                        <Box sx={{ mb: 1 }}>
                            {renderComponentIcon()}
                        </Box>

                        {/* Component Name */}
                        <Typography
                            variant="body2"
                            sx={{
                                color: theme.palette.common.white,
                                fontWeight: 600,
                                textAlign: 'center',
                                textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                                mb: 0.5,
                                lineHeight: 1.2
                            }}
                        >
                            {component.name}
                        </Typography>

                        {/* Type Chip */}
                        <Chip
                            label={component.type}
                            size="small"
                            sx={{
                                bgcolor: alpha(theme.palette.common.white, 0.2),
                                color: theme.palette.common.white,
                                fontSize: '0.7rem',
                                height: 20,
                                '& .MuiChip-label': {
                                    px: 1
                                }
                            }}
                        />

                        {/* Status indicators for specific types */}
                        {(component.type === 'camera' || component.type === 'detector') && (
                            <Box
                                sx={{
                                    position: 'absolute',
                                    top: 8,
                                    right: 8,
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    bgcolor: '#10B981',
                                    boxShadow: `0 0 8px ${alpha('#10B981', 0.6)}`,
                                    '@keyframes pulse': {
                                        '0%': {
                                            opacity: 0.4,
                                            transform: 'scale(0.8)'
                                        },
                                        '50%': {
                                            opacity: 1,
                                            transform: 'scale(1.2)'
                                        },
                                        '100%': {
                                            opacity: 0.4,
                                            transform: 'scale(0.8)'
                                        }
                                    },
                                    animation: 'pulse 2s infinite'
                                }}
                            />
                        )}

                        {/* Voltage indicator for source */}
                        {component.type === 'source' && component.specifications?.voltage && (
                            <Typography
                                variant="caption"
                                sx={{
                                    position: 'absolute',
                                    bottom: 4,
                                    right: 8,
                                    color: alpha(theme.palette.common.white, 0.8),
                                    fontSize: '0.6rem',
                                    fontWeight: 500
                                }}
                            >
                                {component.specifications.voltage}
                            </Typography>
                        )}
                    </Box>

                    {/* Hover overlay */}
                    <Box
                        sx={{
                            position: 'absolute',
                            inset: 0,
                            bgcolor: alpha(theme.palette.primary.main, 0.1),
                            opacity: isHovered ? 1 : 0,
                            transition: theme.transitions.create('opacity', {
                                duration: theme.transitions.duration.shorter,
                            })
                        }}
                    />

                    {/* Selection indicator */}
                    {isSelected && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            style={{
                                position: 'absolute',
                                inset: -2,
                                border: `2px solid ${theme.palette.primary.main}`,
                                borderRadius: shapeStyles.borderRadius,
                                boxShadow: `0 0 12px ${alpha(theme.palette.primary.main, 0.4)}`
                            }}
                        />
                    )}
                </Paper>
            </motion.div>

            {/* Electron beam visualization */}
            <Box
                sx={{
                    position: 'relative',
                    width: 2,
                    height: 24,
                    mx: 'auto',
                    overflow: 'hidden',
                    mt: 1
                }}
            >
                {/* Beam path */}
                <Box
                    sx={{
                        position: 'absolute',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 1,
                        height: '100%',
                        background: `linear-gradient(to bottom, ${alpha('#FDE047', 0.8)}, ${alpha('#F59E0B', 0.6)}, ${alpha('#FDE047', 0.4)})`,
                    }}
                />

                {/* Animated particles */}
                {[...Array(3)].map((_, i) => (
                    <ElectronParticle key={i} delay={i * 0.4} />
                ))}
            </Box>
        </>
    );
};

export default MicroscopeComponentRenderer;