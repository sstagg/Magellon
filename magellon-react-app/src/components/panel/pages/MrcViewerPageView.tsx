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
    CardContent
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {settings} from "../../../core/settings.ts";
import DirectoryTreeView from "../components/DirectoryTreeView.tsx";

interface MRCViewerProps {
    mrcFilePath: string;
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

const MrcViewerPageView: React.FC<MRCViewerProps> = ({mrcFilePath, metadataFiles = []}) => {
    const [selectedDirectory, setSelectedDirectory] = useState('');
    const [selectedImage, setSelectedImage] = useState<number | null>(null);
    const [imageData, setImageData] = useState<ImageData | null>(null);
    const [metadata, setMetadata] = useState<MetadataType>({});
    const [selectedMetadata, setSelectedMetadata] = useState<string>('');
    const [page, setPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(10);
    const [scale, setScale] = useState(1);
    const [brightness, setBrightness] = useState(50);
    const [contrast, setContrast] = useState(50);
    const [columns, setColumns] = useState(3);

    useEffect(() => {
        const fetchImages = async () => {
            try {
                const startIdx = (page - 1) * itemsPerPage;
                const response = await fetch(
                    `http://localhost:8000/web/mrc/?file_path=${encodeURIComponent(
                        "C:\\Users\\18505\\Downloads\\templates_selected.mrc"
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
                    transition: 'all 0.2s ease-in-out',
                    border: selectedImage === index ? 2 : 1,
                    borderColor: selectedImage === index ? 'primary.main' : 'divider',
                    '&:hover': {
                        boxShadow: 4,
                        transform: 'translateY(-2px)',
                        borderColor: 'primary.light',
                    },
                }}
                onClick={() => setSelectedImage(index)}
            >
                <Box sx={{ position: 'relative', p: 1 }}>
                    <img
                        src={canvas.toDataURL()}
                        alt={`MRC Image ${index + 1}`}
                        style={{
                            width: '100%',
                            height: 'auto',
                            display: 'block',
                            borderRadius: 4,
                        }}
                    />
                    <Box
                        sx={{
                            position: 'absolute',
                            top: 8,
                            left: 8,
                            backgroundColor: selectedImage === index ? 'primary.main' : 'background.paper',
                            color: selectedImage === index ? 'primary.contrastText' : 'text.primary',
                            borderRadius: 1,
                            px: 1,
                            py: 0.5,
                            typography: 'caption',
                            fontWeight: 'bold',
                            boxShadow: 1,
                        }}
                    >
                        {index + 1}
                    </Box>
                </Box>
            </Card>
        );
    };

    const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
        setPage(value);
    };

    return (
        <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', p: 2 }}>
            {/* Header */}
            <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    MRC Viewer
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    {mrcFilePath}
                </Typography>
            </Paper>

            {/* Main Content */}
            <Box sx={{ flex: 1, display: 'flex', gap: 2, minHeight: 0 }}>
                {/* Left Sidebar - Directory Tree */}
                <Paper sx={{ width: 280, p: 2, overflow: 'auto' }}>
                    <Typography variant="h6" gutterBottom>
                        Directory Tree
                    </Typography>
                    <Divider sx={{ mb: 2 }} />
                    <DirectoryTreeView />
                </Paper>

                {/* Center - Image Grid */}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    {/* Controls Bar */}
                    <Paper sx={{ p: 2, mb: 2 }}>
                        <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap">
                            <FormControl size="small" sx={{ minWidth: 120 }}>
                                <InputLabel>Items per page</InputLabel>
                                <Select
                                    value={itemsPerPage}
                                    label="Items per page"
                                    onChange={(event) => setItemsPerPage(Number(event.target.value))}
                                >
                                    {[1, 5, 10, 25, 50, 100].map((value) => (
                                        <MenuItem key={value} value={value}>
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
                                    size="large"
                                />
                            </Box>
                        </Stack>
                    </Paper>

                    {/* Image Grid */}
                    <Paper sx={{ flex: 1, p: 2, overflow: 'auto' }}>
                        {imageData?.images?.length ? (
                            <Grid container spacing={2}>
                                {imageData.images.map((image, index) => (
                                    <Grid key={index} xs={12} sm={6} md={4} lg={3}>
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
                    </Paper>
                </Box>

                {/* Right Sidebar - Controls & Metadata */}
                <Box sx={{ width: 300, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {/* Image Controls */}
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Image Controls
                        </Typography>
                        <Divider sx={{ mb: 2 }} />

                        <Stack spacing={3}>
                            <Box>
                                <Typography variant="body2" gutterBottom>
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
                                <Typography variant="body2" gutterBottom>
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

                            <Box>
                                <Typography variant="body2" gutterBottom>
                                    Scale: {scale.toFixed(1)}x
                                </Typography>
                                <Slider
                                    value={scale}
                                    onChange={(_, value) => setScale(value as number)}
                                    min={0.1}
                                    max={5}
                                    step={0.1}
                                    size="small"
                                />
                            </Box>
                        </Stack>
                    </Paper>

                    {/* Metadata */}
                    <Paper sx={{ p: 2, flex: 1 }}>
                        <Typography variant="h6" gutterBottom>
                            Metadata
                        </Typography>
                        <Divider sx={{ mb: 2 }} />

                        <Box sx={{ overflow: 'auto' }}>
                            <Box component="table" sx={{ width: '100%', '& td, & th': { p: 1, border: 1, borderColor: 'divider' } }}>
                                <Box component="thead">
                                    <Box component="tr">
                                        <Box component="th" sx={{ backgroundColor: 'grey.100' }}>Key</Box>
                                        <Box component="th" sx={{ backgroundColor: 'grey.100' }}>Value</Box>
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
                    </Paper>
                </Box>
            </Box>
        </Box>
    );
};

export default MrcViewerPageView;