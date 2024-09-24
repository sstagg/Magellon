import React, {useEffect, useState} from 'react';

import { Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material'; // Table for metadata
import { TextField, Grid } from '@mui/material';
import {useFetchImageMetaData} from "../../../services/api/ImageMetaDataRestService.ts";
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import {CategoryDto, MetadataDto} from "./ImageInfoDto.ts";
import {SoloImageViewerProps} from "./SoloImageViewerComponent.tsx";



const ImageMetadataDisplay: React.FC<SoloImageViewerProps> = ({ selectedImage }) => {
    const { data: imageMetadata, error, isLoading, refetch } = useFetchImageMetaData(selectedImage?.name, false);

    useEffect(() => {
        if (selectedImage?.name) {
            refetch();
        }
    }, [selectedImage?.name, refetch]);


    const [selectedCategory, setSelectedCategory] = useState<CategoryDto | null>(null);
    const [selectedMeta, setSelectedMeta] = useState<MetadataDto | null>(null);

    const handleCategoryClick = (category: CategoryDto) => {
        setSelectedCategory(category);
        setSelectedMeta(null); // Reset metadata selection when a new category is clicked
    };

    const handleMetaClick = (meta: MetadataDto) => {
        setSelectedMeta(meta);
    };

    if (isLoading) return <p>Loading...</p>;
    if (error) return <p>Error loading metadata</p>;

    return (
        <Grid container spacing={2}>
            {/* Left part: Categories Tree */}
            <Grid item xs={3}>
                <SimpleTreeView>
                    {imageMetadata && imageMetadata.map((category: CategoryDto) => (
                        <TreeItem
                            itemId={category.oid}
                            label={category.name}
                            key={category.oid}
                            onClick={() => handleCategoryClick(category)}
                        >
                            {category.children && category.children.map((child) => (
                                <TreeItem
                                    itemId={child.oid}
                                    label={child.name}
                                    key={child.oid}
                                    onClick={() => handleCategoryClick(child)}
                                />
                            ))}
                        </TreeItem>
                    ))}
                </SimpleTreeView>
            </Grid>

            {/* Right part: Metadata Table */}
            <Grid item xs={6}>
                {selectedCategory && selectedCategory.metadata && (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableCell>Name</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {selectedCategory.metadata.map((meta) => (
                                <TableRow
                                    key={meta.oid}
                                    hover
                                    onClick={() => handleMetaClick(meta)}
                                    selected={selectedMeta?.oid === meta.oid}
                                >
                                    <TableCell>{meta.name}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </Grid>

            {/* Bottom part: Metadata Details */}
            <Grid item xs={12}>
                {selectedMeta && (
                    <TextField
                        label="Metadata Details"
                        multiline
                        rows={6}
                        fullWidth
                        variant="outlined"
                        value={selectedMeta.data_json ? JSON.stringify(selectedMeta.data_json, null, 2) : selectedMeta.data}
                        InputProps={{
                            readOnly: true,
                        }}
                    />
                )}
            </Grid>
        </Grid>
    );
};

export default ImageMetadataDisplay;
