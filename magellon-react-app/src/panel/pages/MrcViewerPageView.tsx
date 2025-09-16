import React, {useEffect, useState} from 'react';
import {
    Box,
    MenuItem,
    Pagination,
    Select,
    Slider,
    Typography,
    Paper,
    FormControl,
    InputLabel,
    Divider,
    Stack,
    Card,
    IconButton,
    Tooltip,
    Chip,
    useTheme
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Menu, X, Maximize2, Minimize2 } from 'lucide-react';
import {settings} from "../../core/settings.ts";
import DirectoryTreeView from "../components/DirectoryTreeView.tsx";

interface MRCViewerProps {
    mrcFilePath?: string;
    metadataFiles?: string[];
}

interface ImageData {
    images: number[][][];
    total_images: number;
    height: number;
    width: number;
}

interface MetadataType {
    [key: string]: number[];
}

const BASE_URL = settings.ConfigData.SERVER_API_URL;
const DRAWER_WIDTH = 240;

// Custom resize handle styles
const ResizeHandle = ({ direction }: { direction: 'horizontal' | 'vertical' }) => (
    <PanelResizeHandle>
        <Box
            sx={{
                width: direction === 'horizontal' ? 6 : '100%',
                height: direction === 'horizontal' ? '100%' : 6,
                backgroundColor: 'divider',
                cursor: direction === 'horizontal' ? 'col-resize' : 'row-resize',
                transition: 'background-color 0.2s ease',
                position: 'relative',
                '&:hover': {
                    backgroundColor: 'primary.main',
                    '&::after': {
                        opacity: 1,
                    }
                },
                '&:active': {
                    backgroundColor: 'primary.dark',
                },
                '&::after': {
                    content: '""',
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: direction === 'horizontal' ? 3 : 24,
                    height: direction === 'horizontal' ? 24 : 3,
                    backgroundColor: 'background.paper',
                    borderRadius: 2,
                    opacity: 0.7,
                    transition: 'opacity 0.2s ease',
                }
            }}
        />
    </PanelResizeHandle>
);

const MrcViewerPageView: React.FC<MRCViewerProps> = ({mrcFilePath = "C:\\Users\\18505\\Downloads\\templates_selected.mrc", metadataFiles = []}) => {
    const theme = useTheme();
    const [selectedDirectory, setSelectedDirectory] = useState('');
    const [selectedImage, setSelectedImage] = useState<number | null>(null);
    const [imageData, setImageData] = useState<ImageData | null>(null);
    const [metadata, setMetadata] = useState<MetadataType>({});
    const [selectedMetadata, setSelectedMetadata] = useState<string>('');
    const [page, setPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(25);
    const [scale, setScale] = useState(1);
    const [brightness, setBrightness] = useState(50);
    const [contrast, setContrast] = useState(50);
    const [showSidePanels, setShowSidePanels] = useState(true);

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

        // Listen for storage changes (when drawer state changes)
        window.addEventListener('storage', handleStorageChange);

        // Also check periodically in case of same-tab changes
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    useEffect(() => {
        const fetchImages = async () => {
            try {
                const startIdx = (page - 1) * itemsPerPage;
                const response = await fetch(
                    `http://localhost:8000/web/mrc/?file_path=${encodeURIComponent(
                        mrcFilePath
                    )}&start_idx=${startIdx}&count=${itemsPerPage}`
                );

                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }

                const data = await response.json();
                setImageData(data);
            } catch (error) {
                console.error('Error fetching images:', error);
                setImageData(null);
            }
        };

        fetchImages();
    }, [mrcFilePath, page, itemsPerPage]);

    const adjustImageData = (imageArray: number[][], scale: number) => {
        if (!imageArray || imageArray.length === 0 || imageArray[0].length === 0) {
            console.error('Invalid imageArray data');
            return null;
        }

        const originalHeight = imageArray.length;
        const originalWidth = imageArray[0].length;
        const scaledHeight = Math.round(originalHeight * scale);
        const scaledWidth = Math.round(originalWidth * scale);

        const scaledArray = Array.from({length: scaledHeight}, () =>
            new Array(scaledWidth).fill(0)
        );

        for (let y = 0; y < scaledHeight; y++) {
            for (let x = 0; x < scaledWidth; x++) {
                const originalY = Math.floor(y / scale);
                const originalX = Math.floor(x / scale);
                scaledArray[y][x] = imageArray[originalY][originalX];
            }
        }

        const adjustedArray = scaledArray.map(row =>
            row.map(pixel => {
                let adjusted = pixel * (brightness / 50);
                adjusted = 128 + (contrast / 50) * (adjusted - 128);
                return Math.max(0, Math.min(255, adjusted));
            })
        );

        return adjustedArray;
    };

    const renderImage = (
        imageArray: number[][],
        index: number,
        scale: number
    ) => {
        if (!imageArray || imageArray.length === 0 || imageArray[0].length === 0) {
            return <div>Error: Invalid image data</div>;
        }

        const adjustedData = adjustImageData(imageArray, scale);

        if (!adjustedData || adjustedData.length === 0 || !adjustedData[0]) {
            return <div>Error: Failed to adjust image data</div>;
        }

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        const scaledHeight = adjustedData.length;
        const scaledWidth = adjustedData[0].length;

        canvas.width = scaledWidth;
        canvas.height = scaledHeight;

        const canvasImageData = ctx.createImageData(scaledWidth, scaledHeight);
        for (let i = 0; i < scaledHeight; i++) {
            for (let j = 0; j < scaledWidth; j++) {
                const pixelIndex = (i * scaledWidth + j) * 4;
                const value = adjustedData[i][j];
                canvasImageData.data[pixelIndex] = value;
                canvasImageData.data[pixelIndex + 1] = value;
                canvasImageData.data[pixelIndex + 2] = value;
                canvasImageData.data[pixelIndex + 3] = 255;
            }
        }

        ctx.putImageData(canvasImageData, 0, 0);

        return (
            <Card
                key={index}
                sx={{
                    cursor: 'pointer',
                    transition: 'all 0.15s ease-in-out',
                    border: selectedImage === index ? 2 : 1,
                    borderColor: selectedImage === index ? 'primary.main' : 'divider',
                    '&:hover': {
                        boxShadow: 3,
                        borderColor: 'primary.light',
                    },
                    height: 'fit-content',
                    borderRadius: 1,
                    overflow: 'hidden',
                }}
                onClick={() => setSelectedImage(index)}
            >
                <Box sx={{ position: 'relative', p: 0.25 }}>
                    <img
                        src={canvas.toDataURL()}
                        alt={`MRC Image ${index + 1}`}
                        style={{
                            width: '100%',
                            height: 'auto',
                            display: 'block',
                        }}
                    />
                    <Chip
                        label={index + 1}
                        size="small"
                        color={selectedImage === index ? 'primary' : 'default'}
                        sx={{
                            position: 'absolute',
                            top: 2,
                            left: 2,
                            height: 18,
                            fontSize: '0.65rem',
                            fontWeight: 'bold',
                        }}
                    />
                </Box>
            </Card>
        );
    };

    const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
        setPage(value);
    };

    // Calculate dynamic grid sizing for maximum space utilization
    const getGridColumns = () => {
        if (!showSidePanels) {
            // Full width mode - more columns
            if (scale <= 0.2) return 1.5; // 8 columns
            if (scale <= 0.3) return 2;   // 6 columns
            if (scale <= 0.5) return 2.4; // 5 columns
            if (scale <= 0.8) return 3;   // 4 columns
            if (scale <= 1.5) return 4;   // 3 columns
            if (scale <= 2.5) return 6;   // 2 columns
            return 12;                    // 1 column
        } else {
            // Panel mode - fewer columns due to less space
            if (scale <= 0.3) return 3;   // 4 columns
            if (scale <= 0.6) return 4;   // 3 columns
            if (scale <= 1.2) return 6;   // 2 columns
            return 12;                    // 1 column
        }
    };

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return (
        <Box sx={{
            // Break out of template constraints but respect drawer
            position: 'fixed',
            top: 64, // Account for header
            left: leftMargin, // Adjust for drawer
            right: 0,
            bottom: 0,
            zIndex: 1050, // Below drawer (1200) and header (1100+) but above content
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Minimal Header */}
            <Paper sx={{
                p: 0.75,
                borderRadius: 0,
                borderBottom: 1,
                borderColor: 'divider',
                backgroundColor: 'background.paper',
                zIndex: 10,
                flexShrink: 0
            }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Stack direction="row" alignItems="center" spacing={2}>
                        <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
                            MRC Viewer
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{
                            maxWidth: 300,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                        }}>
                            {mrcFilePath}
                        </Typography>
                    </Stack>

                    <Stack direction="row" spacing={1} alignItems="center">
                        <Chip
                            label={`${imageData?.total_images || 0} images`}
                            size="small"
                            variant="outlined"
                        />
                        <Tooltip title={showSidePanels ? "Hide panels (more space)" : "Show panels"}>
                            <IconButton
                                onClick={() => setShowSidePanels(!showSidePanels)}
                                size="small"
                                color={showSidePanels ? "default" : "primary"}
                            >
                                {showSidePanels ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                            </IconButton>
                        </Tooltip>
                    </Stack>
                </Stack>
            </Paper>

            {/* Main Content */}
            <Box sx={{ flex: 1, overflow: 'hidden' }}>
                {showSidePanels ? (
                    <PanelGroup direction="horizontal">
                        {/* Left Panel - Directory Tree */}
                        <Panel defaultSize={15} minSize={10} maxSize={25}>
                            <Box sx={{
                                height: '100%',
                                p: 0.75,
                                overflow: 'auto',
                                borderRight: 1,
                                borderColor: 'divider',
                                backgroundColor: 'background.paper'
                            }}>
                                <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
                                    Directory
                                </Typography>
                                <Divider sx={{ mb: 1 }} />
                                <DirectoryTreeView />
                            </Box>
                        </Panel>

                        <ResizeHandle direction="horizontal" />

                        {/* Center Panel - Images */}
                        <Panel defaultSize={70} minSize={55}>
                            <PanelGroup direction="vertical">
                                {/* Controls */}
                                <Panel defaultSize={7} minSize={5} maxSize={10}>
                                    <Box sx={{
                                        p: 0.75,
                                        borderBottom: 1,
                                        borderColor: 'divider',
                                        backgroundColor: 'background.paper'
                                    }}>
                                        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                                            <FormControl size="small" sx={{ minWidth: 70 }}>
                                                <InputLabel sx={{ fontSize: '0.8rem' }}>Per page</InputLabel>
                                                <Select
                                                    value={itemsPerPage}
                                                    label="Per page"
                                                    onChange={(event) => setItemsPerPage(Number(event.target.value))}
                                                    sx={{ fontSize: '0.8rem' }}
                                                >
                                                    {[25, 50, 100, 200].map((value) => (
                                                        <MenuItem key={value} value={value} sx={{ fontSize: '0.8rem' }}>
                                                            {value}
                                                        </MenuItem>
                                                    ))}
                                                </Select>
                                            </FormControl>

                                            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                                                <Pagination
                                                    count={Math.ceil((imageData?.total_images || 0) / itemsPerPage)}
                                                    page={page}
                                                    onChange={handlePageChange}
                                                    color="primary"
                                                    size="small"
                                                />
                                            </Box>

                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Typography variant="caption" sx={{ fontSize: '0.7rem', minWidth: 60 }}>
                                                    Scale: {scale?.toFixed(1)}x
                                                </Typography>
                                                <Slider
                                                    value={scale}
                                                    onChange={(_, value) => setScale(value as number)}
                                                    min={0.1}
                                                    max={3}
                                                    step={0.1}
                                                    size="small"
                                                    sx={{ width: 80 }}
                                                />
                                            </Stack>
                                        </Stack>
                                    </Box>
                                </Panel>

                                <ResizeHandle direction="vertical" />

                                {/* Images */}
                                <Panel defaultSize={93} minSize={85}>
                                    <Box sx={{
                                        height: '100%',
                                        p: 0.5,
                                        overflow: 'auto',
                                        backgroundColor: 'grey.50'
                                    }}>
                                        {imageData?.images?.length ? (
                                            <Grid container spacing={0.5} sx={{
                                                justifyContent: 'flex-start'
                                            }}>
                                                {imageData.images.map((image, index) => (
                                                    <Grid key={index} size={getGridColumns()}>
                                                        {renderImage(image, index, scale)}
                                                    </Grid>
                                                ))}
                                            </Grid>
                                        ) : (
                                            <Box
                                                display="flex"
                                                justifyContent="center"
                                                alignItems="center"
                                                height="100%"
                                            >
                                                <Typography variant="h6" color="error">
                                                    Failed to load images
                                                </Typography>
                                            </Box>
                                        )}
                                    </Box>
                                </Panel>
                            </PanelGroup>
                        </Panel>

                        <ResizeHandle direction="horizontal" />

                        {/* Right Panel - Controls */}
                        <Panel defaultSize={15} minSize={12} maxSize={20}>
                            <PanelGroup direction="vertical">
                                {/* Image Controls */}
                                <Panel defaultSize={60} minSize={40}>
                                    <Box sx={{
                                        p: 0.75,
                                        borderBottom: 1,
                                        borderColor: 'divider',
                                        overflow: 'auto',
                                        backgroundColor: 'background.paper'
                                    }}>
                                        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
                                            Controls
                                        </Typography>
                                        <Divider sx={{ mb: 1 }} />

                                        <Stack spacing={1.5}>
                                            <Box>
                                                <Typography variant="caption" display="block" gutterBottom sx={{ fontSize: '0.7rem' }}>
                                                    Brightness: {brightness}
                                                </Typography>
                                                <Slider
                                                    value={brightness}
                                                    onChange={(_, value) => setBrightness(value as number)}
                                                    min={0}
                                                    max={100}
                                                    step={1}
                                                    size="small"
                                                />
                                            </Box>

                                            <Box>
                                                <Typography variant="caption" display="block" gutterBottom sx={{ fontSize: '0.7rem' }}>
                                                    Contrast: {contrast}
                                                </Typography>
                                                <Slider
                                                    value={contrast}
                                                    onChange={(_, value) => setContrast(value as number)}
                                                    min={0}
                                                    max={100}
                                                    step={1}
                                                    size="small"
                                                />
                                            </Box>
                                        </Stack>
                                    </Box>
                                </Panel>

                                <ResizeHandle direction="vertical" />

                                {/* Metadata */}
                                <Panel defaultSize={40} minSize={25}>
                                    <Box sx={{
                                        p: 0.75,
                                        overflow: 'auto',
                                        height: '100%',
                                        backgroundColor: 'background.paper'
                                    }}>
                                        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
                                            Metadata
                                        </Typography>
                                        <Divider sx={{ mb: 1 }} />

                                        <Box component="table" sx={{
                                            width: '100%',
                                            borderCollapse: 'collapse',
                                            '& td, & th': {
                                                p: 0.375,
                                                border: 1,
                                                borderColor: 'divider',
                                                fontSize: '0.65rem'
                                            }
                                        }}>
                                            <Box component="thead">
                                                <Box component="tr">
                                                    <Box component="th" sx={{ backgroundColor: 'grey.100', fontWeight: 'bold' }}>
                                                        Key
                                                    </Box>
                                                    <Box component="th" sx={{ backgroundColor: 'grey.100', fontWeight: 'bold' }}>
                                                        Value
                                                    </Box>
                                                </Box>
                                            </Box>
                                            <Box component="tbody">
                                                <Box component="tr">
                                                    <Box component="td">Dose</Box>
                                                    <Box component="td">5</Box>
                                                </Box>
                                                <Box component="tr">
                                                    <Box component="td">Magnification</Box>
                                                    <Box component="td">2</Box>
                                                </Box>
                                                <Box component="tr">
                                                    <Box component="td">Defocus</Box>
                                                    <Box component="td">30</Box>
                                                </Box>
                                                <Box component="tr">
                                                    <Box component="td">Intensity</Box>
                                                    <Box component="td">11</Box>
                                                </Box>
                                                <Box component="tr">
                                                    <Box component="td">Shift X</Box>
                                                    <Box component="td">12</Box>
                                                </Box>
                                            </Box>
                                        </Box>
                                    </Box>
                                </Panel>
                            </PanelGroup>
                        </Panel>
                    </PanelGroup>
                ) : (
                    // Full-width image grid when panels are hidden (~95% screen usage)
                    <Box sx={{
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column'
                    }}>
                        {/* Inline controls bar */}
                        <Box sx={{
                            p: 0.5,
                            borderBottom: 1,
                            borderColor: 'divider',
                            backgroundColor: 'background.paper',
                            flexShrink: 0
                        }}>
                            <Stack direction="row" spacing={3} alignItems="center" justifyContent="center">
                                <FormControl size="small" sx={{ minWidth: 70 }}>
                                    <InputLabel sx={{ fontSize: '0.8rem' }}>Per page</InputLabel>
                                    <Select
                                        value={itemsPerPage}
                                        label="Per page"
                                        onChange={(event) => setItemsPerPage(Number(event.target.value))}
                                        sx={{ fontSize: '0.8rem' }}
                                    >
                                        {[25, 50, 100, 200].map((value) => (
                                            <MenuItem key={value} value={value} sx={{ fontSize: '0.8rem' }}>
                                                {value}
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>

                                <Pagination
                                    count={Math.ceil((imageData?.total_images || 0) / itemsPerPage)}
                                    page={page}
                                    onChange={handlePageChange}
                                    color="primary"
                                    size="small"
                                />

                                <Stack direction="row" spacing={2} alignItems="center">
                                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Scale:</Typography>
                                    <Slider
                                        value={scale}
                                        onChange={(_, value) => setScale(value as number)}
                                        min={0.1}
                                        max={3}
                                        step={0.1}
                                        size="small"
                                        sx={{ width: 100 }}
                                    />
                                    <Typography variant="caption" sx={{ fontSize: '0.7rem', minWidth: 35 }}>
                                        {scale?.toFixed(1)}x
                                    </Typography>
                                </Stack>

                                <Stack direction="row" spacing={2} alignItems="center">
                                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Brightness:</Typography>
                                    <Slider
                                        value={brightness}
                                        onChange={(_, value) => setBrightness(value as number)}
                                        min={0}
                                        max={100}
                                        step={1}
                                        size="small"
                                        sx={{ width: 80 }}
                                    />
                                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Contrast:</Typography>
                                    <Slider
                                        value={contrast}
                                        onChange={(_, value) => setContrast(value as number)}
                                        min={0}
                                        max={100}
                                        step={1}
                                        size="small"
                                        sx={{ width: 80 }}
                                    />
                                </Stack>
                            </Stack>
                        </Box>

                        {/* Full-width images - MAXIMUM SPACE! */}
                        <Box sx={{
                            flex: 1,
                            p: 0.25,
                            overflow: 'auto',
                            backgroundColor: 'grey.50'
                        }}>
                            {imageData?.images?.length ? (
                                <Grid container spacing={0.25} sx={{
                                    justifyContent: 'flex-start'
                                }}>
                                    {imageData.images.map((image, index) => (
                                        <Grid key={index} size={getGridColumns()}>
                                            {renderImage(image, index, scale)}
                                        </Grid>
                                    ))}
                                </Grid>
                            ) : (
                                <Box
                                    display="flex"
                                    justifyContent="center"
                                    alignItems="center"
                                    height="100%"
                                >
                                    <Typography variant="h6" color="error">
                                        Failed to load images
                                    </Typography>
                                </Box>
                            )}
                        </Box>
                    </Box>
                )}
            </Box>
        </Box>
    );
};

export default MrcViewerPageView;