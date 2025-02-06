import React, {useEffect, useState} from 'react';
import {Box, MenuItem, Pagination, Select, Slider, Typography} from '@mui/material';
import Grid from '@mui/material/Grid2';
import {settings} from "../../../core/settings.ts";
import DirectoryTreeView from "../DirectoryTreeView.tsx";


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


// const gridRef = useRef<HTMLDivElement>(null);

const BASE_URL = settings.ConfigData.SERVER_API_URL;

const MrcViewerPageView: React.FC<MRCViewerProps> = ({mrcFilePath, metadataFiles = []}) => {

    const [selectedDirectory, setSelectedDirectory] = useState('');
    const [selectedImage, setSelectedImage] = useState(null);

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
                canvasImageData.data[pixelIndex + 3] = 255; // Alpha channel
            }
        }

        ctx.putImageData(canvasImageData, 0, 0);

        return (
            <Box
                key={index}
                sx={{
                    position: 'relative',
                    backgroundColor: 'background.paper',
                    borderRadius: 1,
                    boxShadow: 1,
                    padding: 2,
                    width: scaledWidth + 20,
                    height: scaledHeight + 20,
                    transition: 'all 0.3s ease',
                    '&:hover': {
                        boxShadow: '0 0 10px rgba(0, 0, 255, 0.5)', // Hover effect
                        transform: 'scale(1.05)', // Slight zoom effect
                    },
                    border: selectedImage === index ? '3px solid blue' : 'none', // Border for selected image
                }}
                onClick={() => setSelectedImage(index)}
            >
                <img
                    src={canvas.toDataURL()}
                    alt={`MRC Image ${index + 1}`}
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                    }}
                />
                <Box
                    sx={{
                        position: 'absolute',
                        top: 2,
                        left: 2,
                        backgroundColor: 'background.default',
                        color: selectedImage === index ? 'blue' : 'text.primary', // Change color for selected image
                        borderRadius: 1,
                        padding: '2px 4px',
                        transition: 'color 0.3s ease',
                    }}
                >
                    {index + 1}
                </Box>
            </Box>
        );
    };
    const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
        setPage(value);
    };
    return (
        <Grid container spacing={2}>
            {/* Left Panel - 3 columns */}
            <Grid size={2}>

                <Typography variant="h6" gutterBottom>
                    Directory Tree
                </Typography>

                <DirectoryTreeView></DirectoryTreeView>

            </Grid>

            {/* Main Panel - 8 columns */}
            <Grid container size={10} spacing={2}>


                <Grid size={9} container direction="row">
                    {imageData?.images?.length ? (
                        imageData.images.map((image, index) =>
                            renderImage(image, index, scale)
                        )
                    ) : (
                        <Box
                            display="flex"
                            justifyContent="center"
                            alignItems="center"
                            height="200px"
                        >
                            <Typography variant="h2" color="error">
                                Error: Failed to load images
                            </Typography>
                        </Box>
                    )}
                </Grid>

                <Grid size={3}>

                    <Typography variant="h6" display="inline" style={{marginRight: 8}}>
                        Metadata:
                    </Typography>
                    <table>
                        <thead>
                        <tr>
                            <th>Key</th>
                            <th>Value</th>
                        </tr>
                        </thead>
                        <tbody>
                        <tr>
                            <td>Dose</td>
                            <td>5</td>
                        </tr>
                        <tr>
                            <td>magnification</td>
                            <td>2</td>
                        </tr>
                        <tr>
                            <td>defocus</td>
                            <td>30</td>
                        </tr>
                        <tr>
                            <td>intensity</td>
                            <td>11</td>
                        </tr>
                        <tr>
                            <td>shift_x</td>
                            <td>12</td>
                        </tr>
                        </tbody>
                    </table>
                </Grid>

                <Grid container size={6}>

                    <Grid>
                        <Typography variant="h6" display="inline" style={{marginRight: 8}}>
                            Items per page:
                        </Typography>
                    </Grid>

                    <Grid>
                        <Select
                            value={String(itemsPerPage)}
                            onChange={(event) => setItemsPerPage(Number(event.target.value))}
                        >
                            {[1, 5, 10, 25, 50, 100].map((value) => (
                                <MenuItem key={value} value={value}>
                                    {value}
                                </MenuItem>
                            ))}
                        </Select>
                    </Grid>

                    <Grid>
                        <Pagination
                            count={Math.ceil(imageData?.total_images / itemsPerPage) || 0}
                            page={page}
                            onChange={handlePageChange}
                            color="primary"
                            size="large"
                        />
                    </Grid>
                </Grid>

                <Grid size={2}>
                    <Grid size={12}>
                        <Typography variant="h6" display="inline" style={{marginRight: 8}}>
                            Brightness:
                        </Typography>
                        <Typography variant="h6" display="inline" color="primary">
                            {brightness}
                        </Typography>
                    </Grid>

                    <Slider
                        value={brightness}
                        onChange={(_, value) => setBrightness(value as number)}
                        min={0}
                        max={100}
                        step={1}
                    />
                </Grid>
                <Grid size={2}>
                    <Grid size={12}>
                        <Typography variant="h6" display="inline" style={{marginRight: 8}}>
                            Contrast:
                        </Typography>
                        <Typography variant="h6" display="inline" color="primary">
                            {contrast}
                        </Typography>
                    </Grid>
                    <Slider
                        value={contrast}
                        onChange={(_, value) => setContrast(value as number)}
                        min={0}
                        max={100}
                        step={1}
                    />
                </Grid>


                <Grid size={2}>
                    <Grid size={12}>
                        <Typography variant="h6" display="inline" style={{marginRight: 8}}>
                            Scale:
                        </Typography>
                        <Typography variant="h6" display="inline" color="primary">
                            {scale}
                        </Typography>
                    </Grid>
                    <Slider
                        value={scale}
                        onChange={(_, value) => setScale(value as number)}
                        min={0.1}
                        max={5}
                        step={0.1}
                        aria-labelledby="scale-slider"
                    />
                </Grid>


            </Grid>


        </Grid>
    );

};

export default MrcViewerPageView;