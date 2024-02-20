import {FormControl, Grid, ImageListItem, InputLabel, MenuItem, Select, Stack} from "@mui/material";

import {Field, QueryBuilder} from 'react-querybuilder';
import 'react-querybuilder/dist/query-builder.css';

// import '@react-awesome-query-builder/mui/css/styles.css';
// import {ActionMeta, Builder, Config, ImmutableTree, Query} from "@react-awesome-query-builder/mui";
//
// const config = {
//
//     fields: {
//         qty: {
//             label: 'Qty',
//             type: 'number',
//             fieldSettings: {
//                 min: 0,
//             },
//             valueSources: ['value'],
//             preferWidgets: ['number'],
//         },
//         price: {
//             label: 'Price',
//             type: 'number',
//             valueSources: ['value'],
//             fieldSettings: {
//                 min: 10,
//                 max: 100,
//             },
//             preferWidgets: ['slider', 'rangeslider'],
//         },
//         name: {
//             label: 'Name',
//             type: 'text',
//         },
//         color: {
//             label: 'Color',
//             type: 'select',
//             valueSources: ['value'],
//             fieldSettings: {
//                 listValues: [
//                     {value: 'yellow', title: 'Yellow'},
//                     {value: 'green', title: 'Green'},
//                     {value: 'orange', title: 'Orange'}
//                 ],
//             }
//         },
//         is_promotion: {
//             label: 'Promo?',
//             type: 'boolean',
//             operators: ['equal'],
//             valueSources: ['value'],
//         },
//     }
// };
const fields: Field[] = [
    { name: 'projectName', label: 'Project Name' },
    { name: 'sessionName', label: 'Session Name' },
    { name: 'imageName', label: 'Image Name' },
];
export const RunJobPageView = () => {


    return (
        <Grid container>
            <Stack>
                <FormControl sx={{ m: 1, minWidth: 120 }} size="small">
                    <InputLabel id="demo-select-small-label">Run Pipline</InputLabel>
                    <Select
                        labelId="demo-select-small-label"
                        id="demo-select-small"
                        value={""}
                        label="Age"
                        // onChange={handleChange}
                    >
                        <MenuItem value="">
                            <em>None</em>
                        </MenuItem>
                        <MenuItem value="ctf">
                            <em>CTF</em>
                        </MenuItem>
                        <MenuItem value="fa">
                            <em>Frame Allignment</em>
                        </MenuItem>
                    </Select>
                </FormControl>
                <QueryBuilder  fields={fields}/>;

            </Stack>


        </Grid>
    );
}