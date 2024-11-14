import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Paper,
    Divider,
    Typography,
    Skeleton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableRow
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { ExpandMore, ChevronRight } from '@mui/icons-material';
import { settings } from "../../../core/settings.ts";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';

import { Card, CardContent } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';


const gridRef = useRef<HTMLDivElement>(null);

const BASE_URL = settings.ConfigData.SERVER_API_URL;

const MrcViewerPageView = () => {
    const [selectedDirectory, setSelectedDirectory] = useState('');
    const [imageData, setImageData] = useState([]);
    const [selectedImage, setSelectedImage] = useState(null);

    const [page, setPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(10);
    const [scale, setScale] = useState(1);
    const [brightness, setBrightness] = useState(50);
    const [contrast, setContrast] = useState(50);

    const [columns, setColumns] = useState(3);

    // Sample directory structure
    const directories = [
        { name: 'Documents', children: ['File1.txt', 'File2.txt'] },
        { name: 'Images', children: ['Image1.jpg', 'Image2.jpg', 'Image3.jpg'] },
        { name: 'Videos', children: ['Video1.mp4', 'Video2.mp4'] }
    ];

    // Sample image data
    const sampleImageData = [
        { id: 1, src: '/api/placeholder/200/150', name: 'Image1.jpg', width: 200, height: 150, metadata: { size: '100KB', resolution: '1920x1080' } },
        { id: 2, src: '/api/placeholder/200/150', name: 'Image2.jpg', width: 200, height: 150, metadata: { size: '120KB', resolution: '1920x1080' } },
        { id: 3, src: '/api/placeholder/200/150', name: 'Image3.jpg', width: 200, height: 150, metadata: { size: '150KB', resolution: '1920x1080' } }
    ];

    const handleDirectorySelect = (directory) => {
        setSelectedDirectory(directory);
        // Fetch image data for the selected directory
        setImageData(sampleImageData);
    };

    const handleImageSelect = (image) => {
        setSelectedImage(image);
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

                    <Grid size={12}  >
                        {/* Lower Section - 30% height */}
                        <Typography variant="h6">Selected Image Details</Typography>
                    </Grid>
                <Grid size={12}>

                    <Divider sx={{ my: 1 }} />
                    {selectedImage ? (
                        <Box>
                            <Typography>Name: {selectedImage.name}</Typography>
                            <Typography>Size: {selectedImage.metadata.size}</Typography>
                            <Typography>Resolution: {selectedImage.metadata.resolution}</Typography>
                        </Box>
                    ) : (
                        <Typography variant="body2">Select an image to view details</Typography>
                    )}
                </Grid>
                <Grid size={12}>
                    <div className="flex flex-col h-full p-4 gap-4">
                        <Card>
                            <CardContent className="p-4 flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <span>Scale:</span>
                                    <Button
                                        variant="outline"
                                        onClick={() => setScale(s => Math.max(0.1, s - 0.1))}
                                    >
                                        -
                                    </Button>
                                    <span className="w-12 text-center">{scale.toFixed(1)}</span>
                                    <Button
                                        variant="outline"
                                        onClick={() => setScale(s => s + 0.1)}
                                    >
                                        +
                                    </Button>
                                </div>

                                <div className="flex items-center gap-2">
                                    <span>Items per page:</span>
                                    <Select
                                        value={String(itemsPerPage)}
                                        onValueChange={(value) => setItemsPerPage(Number(value))}
                                    >
                                        <SelectTrigger className="w-20">
                                            <SelectValue/>
                                        </SelectTrigger>
                                        <SelectContent>
                                            {[1, 5, 10, 25, 50, 100].map((value) => (
                                                <SelectItem key={value} value={String(value)}>
                                                    {value}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                {metadataFiles.length > 0 && (
                                    <div className="flex items-center gap-2">
                                        <span>Metadata:</span>
                                        <Select
                                            value={selectedMetadata}
                                            onValueChange={setSelectedMetadata}
                                        >
                                            <SelectTrigger className="w-48">
                                                <SelectValue placeholder="Select metadata"/>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {metadataFiles.map((file) => (
                                                    <SelectItem key={file} value={file}>
                                                        {file}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardContent className="p-4">
                                <div className="flex items-center gap-4">
                                    <div className="flex-1">
                                        <span>Brightness</span>
                                        <Slider
                                            value={[brightness]}
                                            onValueChange={([value]) => setBrightness(value)}
                                            min={0}
                                            max={100}
                                            step={1}
                                        />
                                    </div>
                                    <div className="flex-1">
                                        <span>Contrast</span>
                                        <Slider
                                            value={[contrast]}
                                            onValueChange={([value]) => setContrast(value)}
                                            min={0}
                                            max={100}
                                            step={1}
                                        />
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <div className="flex justify-between items-center mb-4">
                            <Button
                                variant="outline"
                                onClick={() => setPage(p => Math.max(1, p - 1))}
                                disabled={page === 1}
                            >
                                Previous
                            </Button>
                            <span>
          Page {page} of {imageData?.total_images ? Math.ceil(imageData.total_images / itemsPerPage) : 1}
        </span>
                            <Button
                                variant="outline"
                                onClick={() => setPage(p => p + 1)}
                                disabled={!imageData || (page * itemsPerPage) >= imageData.total_images}
                            >
                                Next
                            </Button>
                        </div>

                        <div
                            ref={gridRef}
                            className="grid gap-4 auto-rows-max"
                            style={{
                                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                            }}
                        >
                            {imageData?.images.map((image, index) => renderImage(image, index))}
                        </div>
                    </div>

                </Grid>
            </Grid>
        </Grid>
    );

};

export default MrcViewerPageView;