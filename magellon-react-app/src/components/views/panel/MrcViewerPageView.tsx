import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Divider,
    Typography,
 Slider, Select, MenuItem
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { settings } from "../../../core/settings.ts";
import Button from "@mui/material/Button";



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

const MrcViewerPageView: React.FC<MRCViewerProps> = ({ mrcFilePath, metadataFiles = [] }) => {
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



    const adjustImageData = (imageArray: number[][]) => {
        const adjustedArray = imageArray.map(row =>
            row.map(pixel => {
                let adjusted = pixel * (brightness / 50);
                adjusted = 128 + (contrast / 50) * (adjusted - 128);
                return Math.max(0, Math.min(255, adjusted));
            })
        );
        return adjustedArray;
    };

    const renderImage = (imageArray: number[][], index: number) => {
        const adjustedData = adjustImageData(imageArray);
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        const scaledHeight = imageData?.height ? imageData.height * scale : 256;
        const scaledWidth = imageData?.width ? imageData.width * scale : 256;

        canvas.width = scaledWidth;
        canvas.height = scaledHeight;

        const canvasImageData = ctx.createImageData(scaledWidth, scaledHeight);
        for (let i = 0; i < adjustedData.length; i++) {
            for (let j = 0; j < adjustedData[i].length; j++) {
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
                }}
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
                        color: 'text.primary',
                        borderRadius: 1,
                        padding: '2px 4px',
                    }}
                >
                    {index + 1}
                </Box>
                {selectedMetadata && metadata[selectedMetadata] && (
                    <Box
                        sx={{
                            position: 'absolute',
                            bottom: 2,
                            left: 2,
                            backgroundColor: 'background.default',
                            color: 'text.primary',
                            borderRadius: 1,
                            padding: '2px 4px',
                        }}
                    >
                        {metadata[selectedMetadata][index]}
                    </Box>
                )}
            </Box>
        );
    };


    return (
        <Grid container spacing={2}>
            {/* Left Panel - 3 columns */}
            <Grid size={3}>

                    <Typography variant="h6" gutterBottom>
                        Directory Tree
                    </Typography>
                    <SimpleTreeView>
                        <TreeItem itemId="grid" label="Data Grid">
                            <TreeItem itemId="grid-community" label="@mui/x-data-grid" />
                            <TreeItem itemId="grid-pro" label="@mui/x-data-grid-pro" />
                            <TreeItem itemId="grid-premium" label="@mui/x-data-grid-premium" />
                        </TreeItem>
                        <TreeItem itemId="pickers" label="Date and Time Pickers">
                            <TreeItem itemId="pickers-community" label="@mui/x-date-pickers" />
                            <TreeItem itemId="pickers-pro" label="@mui/x-date-pickers-pro" />
                        </TreeItem>
                        <TreeItem itemId="charts" label="Charts">
                            <TreeItem itemId="charts-community" label="@mui/x-charts" />
                        </TreeItem>
                        <TreeItem itemId="tree-view" label="Tree View">
                            <TreeItem itemId="tree-view-community" label="@mui/x-tree-view" />
                        </TreeItem>
                    </SimpleTreeView>

            </Grid>

            {/* Main Panel - 8 columns */}
            <Grid container size={9} spacing={2}>

               {/*<Grid size={12}   ref={gridRef}>*/}
               <Grid size={12}   >

                       <Grid container spacing={2} sx={{ flexGrow: 1 }}>

                       </Grid>
                </Grid>
                <Grid size={12}>
                    {imageData?.images ? (
                        imageData.images.map((image, index) => (
                            renderImage(image, index)
                        ))
                    ) : (
                        <Box
                            display="flex"
                            justifyContent="center"
                            alignItems="center"
                            height="200px"
                        >
                            <Typography variant="h6" color="error">
                                Error: Failed to load images
                            </Typography>
                        </Box>
                    )}
                </Grid>
                <Grid container size={12}>

                        <Grid size={6}>
                            <Typography>Brightness</Typography>
                            <Slider
                                value={brightness}
                                onChange={(_, value) => setBrightness(value as number)}
                                min={0}
                                max={100}
                                step={1}
                            />
                        </Grid>
                        <Grid size={6}>
                            <Typography>Contrast</Typography>
                            <Slider
                                value={contrast}
                                onChange={(_, value) => setContrast(value as number)}
                                min={0}
                                max={100}
                                step={1}
                            />
                        </Grid>


                </Grid>
                <Grid container size={12} spacing={2} alignItems="center">


                            <Grid >
                                <Typography>Scale:</Typography>
                            </Grid>
                            <Grid >
                                <Button
                                    variant="outlined"
                                    onClick={() => setScale(s => Math.max(0.1, s - 0.1))}
                                >
                                    -
                                </Button>
                            </Grid>
                            <Grid >
                                <Typography>{scale.toFixed(1)}</Typography>
                            </Grid>
                            <Grid >
                                <Button
                                    variant="outlined"
                                    onClick={() => setScale(s => s + 0.1)}
                                >
                                    +
                                </Button>
                            </Grid>
                            <Grid >
                                <Typography>Items per page:</Typography>
                            </Grid>
                            <Grid >
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


                </Grid>
            </Grid>
        </Grid>
    );

};

export default MrcViewerPageView;