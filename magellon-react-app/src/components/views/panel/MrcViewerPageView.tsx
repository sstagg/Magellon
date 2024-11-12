import React, { useState } from 'react';
import {
    Box,
    Grid,
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
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { ExpandMore, ChevronRight } from '@mui/icons-material';
import { settings } from "../../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_API_URL;

const MrcViewerPageView = () => {
    const [selectedDirectory, setSelectedDirectory] = useState('');
    const [imageData, setImageData] = useState([]);
    const [selectedImage, setSelectedImage] = useState(null);

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
            <Grid item xs={3}>
                <Paper elevation={2}>
                    <Box p={2}>
                        <Typography variant="h6">Directory Structure</Typography>
                        <Divider />
                        <SimpleTreeView
                            defaultCollapseIcon={<ExpandMore />}
                            defaultExpandIcon={<ChevronRight />}
                            onNodeSelect={(_, directory) => handleDirectorySelect(directory)}
                        >
                            {/*{directories.map((dir) => (*/}
                            {/*    <TreeItem key={dir.name} nodeId={dir.name} label={dir.name}>*/}
                            {/*        {dir.children.map((file) => (*/}
                            {/*            <TreeItem key={file} nodeId={file} label={file} />*/}
                            {/*        ))}*/}
                            {/*    </TreeItem>*/}
                            {/*))}*/}
                        </SimpleTreeView>
                    </Box>
                </Paper>
            </Grid>
            <Grid item xs={9}>
                <Paper elevation={2}>
                    <Box p={2}>
                        <Typography variant="h6">Image Viewer</Typography>
                        <Divider />
                        {selectedImage ? (
                            <Box display="flex" alignItems="center" justifyContent="center" height="400px">
                                <img src={selectedImage.src} alt={selectedImage.name} width={selectedImage.width} height={selectedImage.height} />
                            </Box>
                        ) : (
                            <Box height="400px" display="flex" alignItems="center" justifyContent="center">
                                <Skeleton variant="rectangular" width="100%" height="100%" />
                            </Box>
                        )}
                        <Box mt={2}>
                            <Typography variant="subtitle1">Thumbnails</Typography>
                            <Box display="flex" flexWrap="wrap" gap={1}>
                                {imageData.map((image) => (
                                    <Box
                                        key={image.id}
                                        component="img"
                                        src={image.src}
                                        alt={image.name}
                                        width={50}
                                        height={50}
                                        sx={{ cursor: 'pointer' }}
                                        onClick={() => handleImageSelect(image)}
                                    />
                                ))}
                            </Box>
                        </Box>
                    </Box>
                </Paper>
            </Grid>
            {selectedImage && (
                <Grid item xs={3}>
                    <Paper elevation={2}>
                        <Box p={2}>
                            <Typography variant="h6">Image Properties</Typography>
                            <Divider />
                            <TableContainer>
                                <Table>
                                    <TableBody>
                                        <TableRow>
                                            <TableCell>Name</TableCell>
                                            <TableCell>{selectedImage.name}</TableCell>
                                        </TableRow>
                                        <TableRow>
                                            <TableCell>Size</TableCell>
                                            <TableCell>{selectedImage.metadata.size}</TableCell>
                                        </TableRow>
                                        <TableRow>
                                            <TableCell>Resolution</TableCell>
                                            <TableCell>{selectedImage.metadata.resolution}</TableCell>
                                        </TableRow>
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Box>
                    </Paper>
                </Grid>
            )}
        </Grid>
    );
};

export default MrcViewerPageView;