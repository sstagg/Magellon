import Paper from "@mui/material/Paper";
import IconButton from "@mui/material/IconButton";
import Box from '@mui/material/Box';
import { DataGrid, GridColDef, GridValueGetterParams } from '@mui/x-data-grid';
import React from "react";
import IServerlessCode from "./Serverless.Model.ts";
import {ButtonGroup} from "@mui/material";
import {ControlPoint, HighlightOff, Palette, Straighten} from "@mui/icons-material";
import {useNavigate} from "react-router-dom";
import {
    handleEnter
} from "@blocknote/core/types/src/extensions/Blocks/nodes/BlockContent/ListItemBlockContent/ListItemKeyboardShortcuts";

const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 90 },
    { field: 'name', headerName: 'Name', width: 150, editable: false },
    { field: 'alias', headerName: 'Alias', width: 150, editable: false },
    { field: 'description', headerName: 'Description', width: 200, editable: false },
    { field: 'runtime_id', headerName: 'Runtime', width: 150, type: 'number', editable: true },
    { field: 'author', headerName: 'Author', width: 150, editable: true },
    { field: 'copyright', headerName: 'Copyright', width: 150, editable: true },
    { field: 'requirements', headerName: 'Requirements', width: 200, editable: true },
    { field: 'created_at', headerName: 'Created At', width: 150, type: 'date', editable: true },
    { field: 'updated_at', headerName: 'Updated At', width: 150, type: 'date', editable: true },
    { field: 'status_id', headerName: 'Status', width: 150, type: 'number', editable: true },
    { field: 'version', headerName: 'Version', width: 150, editable: true },
];

const rows: IServerlessCode[] = [
    {
        id: 1,
        name: 'CTF4Finde',
        alias: 'Ex1',
        code: 'function example() { }',
        description: 'This is an example code snippet',
        runtime_id: 1,
        author: 'John Doe',
        copyright: 'Company XYZ',
        requirements: 'None',
        created_at: new Date(),
        updated_at: new Date(),
        status_id: 1,
        version: '1.0',
    },
    {
        id: 2,
        name: 'CTFFind5',
        alias: 'Ex2',
        code: 'function anotherExample() { }',
        description: 'Another example code snippet',
        runtime_id: 2,
        author: 'Jane Smith',
        copyright: 'Company ABC',
        requirements: 'Node.js 14',
        created_at: new Date(),
        updated_at: new Date(),
        status_id: 2,
        version: '2.0',
    },
    // Add more rows as needed
];


export const ServerlessTableComponent = () => {
    const navigate = useNavigate();
    const handleNew = () => {
        navigate("new");
    }
    return (
        <Box sx={{ height: 400, width: '100%' }}>
            <ButtonGroup size="medium" >
                <IconButton  key="three" onClick={handleNew}><ControlPoint/></IconButton>
                <IconButton  key="four"><HighlightOff/></IconButton>
            </ButtonGroup>
            <DataGrid
                rows={rows}
                columns={columns}
                initialState={{
                    pagination: {  paginationModel: {     pageSize: 5,      },               },
                }}
                pageSizeOptions={[5]}
                checkboxSelection

            />
        </Box>
    );
};
