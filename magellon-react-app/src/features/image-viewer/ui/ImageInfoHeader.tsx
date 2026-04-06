import React from "react";
import {
    Box,
    Card,
    CardContent,
    CardHeader,
    Typography,
    Skeleton,
    Divider,
    useTheme,
    Collapse,
    LinearProgress,
    Stack,
    alpha,
} from "@mui/material";
import {
    FileImage,
    Zap,
    Database,
    Layers,
    Target,
    BarChart3,
} from "lucide-react";
import ImageInfoDto from "../../../entities/image/types.ts";

export interface ImageInfoHeaderProps {
    selectedImage: ImageInfoDto;
    sessionName: string;
    isLoading: boolean;
    loadingProgress: number;
    isMobile: boolean;
    isInfoExpanded: boolean;
}

// Enhanced info component with animation and better styling
const InfoItem: React.FC<{
    label: string;
    value: string | number | undefined | null;
    icon?: React.ReactNode;
    color?: string;
    loading?: boolean;
    formatter?: (value: any) => string;
}> = ({
          label,
          value,
          icon,
          color,
          loading = false,
          formatter = (val) => val
      }) => {
    const theme = useTheme();

    // Determine the display value
    const displayValue = (() => {
        // Handle null, undefined, or empty values
        if (value === null || value === undefined || value === '') {
            return 'N/A';
        }

        // Apply custom formatter if provided
        try {
            return formatter(value);
        } catch (error) {
            console.warn(`Formatting error for ${label}:`, error);
            return String(value);
        }
    })();

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            py: 0.75,
            px: 1,
            borderRadius: 1,
            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)}, transparent)`,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            transition: 'all 0.2s ease',
            '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                transform: 'translateX(2px)',
            }
        }}>
            {icon && (
                <Box sx={{
                    mr: 1.5,
                    color: color || 'primary.main',
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center'
                }}>
                    {icon}
                </Box>
            )}
            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="caption"
                    sx={{
                        color: 'text.secondary',
                        fontWeight: 600,
                        display: 'block',
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontSize: '0.65rem'
                    }}
                >
                    {label}
                </Typography>
                {loading ? (
                    <Skeleton width={60} height={20} />
                ) : (
                    <Typography
                        variant="body2"
                        sx={{
                            fontWeight: 500,
                            color: displayValue === 'N/A' ? 'text.disabled' : 'text.primary',
                            fontSize: '0.875rem'
                        }}
                    >
                        {displayValue}
                    </Typography>
                )}
            </Box>
        </Box>
    );
};

// Progress indicator for data loading
const DataLoadingProgress: React.FC<{
    isLoading: boolean;
    progress?: number;
    label?: string;
}> = ({ isLoading, progress, label = "Loading..." }) => {
    if (!isLoading) return null;

    return (
        <Box sx={{ width: '100%', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="body2" sx={{ mr: 1 }}>{label}</Typography>
                {progress !== undefined && (
                    <Typography variant="body2" color="text.secondary">
                        {Math.round(progress)}%
                    </Typography>
                )}
            </Box>
            <LinearProgress
                variant={progress !== undefined ? "determinate" : "indeterminate"}
                value={progress}
                sx={{ height: 6, borderRadius: 3 }}
            />
        </Box>
    );
};

export const ImageInfoHeader: React.FC<ImageInfoHeaderProps> = ({
    selectedImage,
    sessionName,
    isLoading,
    loadingProgress,
    isMobile,
    isInfoExpanded,
}) => {
    const theme = useTheme();

    return (
        <Card sx={{ mb: 2, overflow: 'hidden' }}>
            <CardHeader
                avatar={<FileImage size={24} />}
                title={
                    <Typography variant="h6" component="div" noWrap>
                        {selectedImage.name}
                    </Typography>
                }
                sx={{ pb: 1 }}
            />

            <Collapse in={isInfoExpanded}>
                <CardContent sx={{ pt: 0 }}>
                    <DataLoadingProgress
                        isLoading={isLoading}
                        progress={loadingProgress}
                        label="Loading image data..."
                    />

                    <Stack
                        direction={isMobile ? "column" : "row"}
                        spacing={2}
                        divider={!isMobile && <Divider orientation="vertical" flexItem />}
                    >
                        <Stack spacing={1} sx={{ flex: 1 }}>
                            <InfoItem
                                label="Magnification"
                                value={selectedImage.mag ? `${selectedImage.mag}×` : undefined}
                                icon={<Zap size={16} />}
                                color={theme.palette.primary.main}
                            />
                            <InfoItem
                                label="Defocus"
                                value={selectedImage.defocus ? `${selectedImage.defocus?.toFixed(2)} μm` : undefined}
                                icon={<Target size={16} />}
                                color={theme.palette.warning.main}
                            />
                        </Stack>

                        <Stack spacing={1} sx={{ flex: 1 }}>
                            <InfoItem
                                label="Pixel Size"
                                value={selectedImage.pixelSize ? `${selectedImage.pixelSize?.toFixed(2)} Å/pix` : undefined}
                                icon={<Layers size={16} />}
                                color={theme.palette.info.main}
                            />
                            <InfoItem
                                label="Dose"
                                value={selectedImage.dose}
                                icon={<BarChart3 size={16} />}
                                color={theme.palette.success.main}
                            />
                        </Stack>

                        <Stack spacing={1} sx={{ flex: 1 }}>
                            <InfoItem
                                label="Session"
                                value={sessionName}
                                icon={<Database size={16} />}
                                color={theme.palette.secondary.main}
                            />
                            <InfoItem
                                label="Children"
                                value={selectedImage.children_count || 0}
                                icon={<Layers size={16} />}
                                color={theme.palette.text.secondary}
                            />
                        </Stack>
                    </Stack>
                </CardContent>
            </Collapse>
        </Card>
    );
};

export default ImageInfoHeader;
