import React, {useEffect, useState} from 'react';

import {Table, TableBody, TableCell, tableCellClasses, TableHead, TableRow} from '@mui/material'; // Table for metadata
import { TextField, Grid } from '@mui/material';
import {useFetchImageMetaData} from "../../../services/api/ImageMetaDataRestService.ts";
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import {CategoryDto, MetadataDto} from "./ImageInfoDto.ts";
import {SoloImageViewerProps} from "./SoloImageViewerComponent.tsx";
import Box from "@mui/material/Box";

import { JsonEditor as Editor } from 'jsoneditor-react'
import 'jsoneditor-react/es/editor.min.css';
import {styled} from "@mui/material/styles";

const StyledTableCell = styled(TableCell)(({ theme }) => ({
    [`&.${tableCellClasses.head}`]: {
        backgroundColor: theme.palette.common.black,
        color: theme.palette.common.white,
        fontSize: 14,
        fontWeight: 'bold', // Makes the font bold
    },
    [`&.${tableCellClasses.body}`]: {
        fontSize: 14,
    },
}));

const StyledTableRow = styled(TableRow)(({ theme }) => ({
    '&:nth-of-type(odd)': {
        backgroundColor: theme.palette.action.hover,
    },
    // hide last border
    '&:last-child td, &:last-child th': {
        border: 0,
    },
}));



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
        <Grid container spacing={5}>
            {/* Left part: Categories Tree */}
            <Grid item xs={4}>
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
            <Grid item xs={8}>

                {selectedCategory && selectedCategory.metadata && (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <StyledTableCell>Metadata Records</StyledTableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {selectedCategory.metadata.map((meta) => (
                                <StyledTableRow
                                    key={meta.oid}
                                    hover
                                    onClick={() => handleMetaClick(meta)}
                                    selected={selectedMeta?.oid === meta.oid}
                                >
                                    <StyledTableCell >{meta.name}</StyledTableCell >
                                </StyledTableRow >
                            ))}
                        </TableBody>
                    </Table>
                )}
            </Grid>

            {/* Bottom part: Metadata Details */}
            {selectedMeta && selectedMeta.data &&(
            <Grid item xs={12}>
                {selectedMeta && (
                    <TextField
                        label="Metadata Details"
                        multiline
                        rows={20}
                        fullWidth
                        variant="outlined"
                        //value={selectedMeta.data_json ? JSON.stringify(selectedMeta.data_json, null, 2) : selectedMeta.data}
                        value={selectedMeta.data_json ? JSON.stringify(selectedMeta.data_json, null, 2) : selectedMeta.data}
                        InputProps={{
                            readOnly: true,
                        }}
                    />
                )}
            </Grid>
            )}
            {selectedMeta && selectedMeta.data_json &&(
                <Grid item xs={12}>
                        <Editor
                            mode="tree"
                            history
                            value={selectedMeta.data_json}
                            // onChange={setJson}
                        />
                </Grid>
            )}

        </Grid>
    );
};

export default ImageMetadataDisplay;
