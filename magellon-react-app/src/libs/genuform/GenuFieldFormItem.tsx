import React from 'react';
import {GenuFieldFormItemProps, IGenuWidgetProps} from "./GenuType.ts";
import {FormControl, FormLabel, Grid, TextField, Typography} from "@mui/material";
import GenuTextBoxEditor from "./editors/GenuTextBoxEditor.tsx";
import {GenuEditorsFactory} from "./GenuEditorsFactory.tsx";

const GenuFieldFormItem: React.FC<GenuFieldFormItemProps> = ({ name,caption,widget,field,
                                                                 info, warning, error,  }) => {

    // Add a new editor component to GenuEditorsFactory
    GenuEditorsFactory.addEditorComponent('GenuTextBoxEditor', GenuTextBoxEditor); // Adjust the import path

    const theParam: IGenuWidgetProps = {
        allowedTypes: ['GenuNumberEditor'],
        name:name,
        caption: caption,
        value: 20,
        onValueChanging: (oldValue: any, newValue: any) => 0,
        onValueChanged: (oldValue: any, newValue: any) => 0,
    };

    const EditorComponent = GenuEditorsFactory.getEditorByName(widget, theParam    ); // you can customize EdtiotrComponent More here!

    return (
        <>
            <Grid item xs={8} >
                <FormControl fullWidth>
                    <FormLabel>{caption}</FormLabel>
                    {EditorComponent}
                </FormControl>
            </Grid>

            {/*<Grid item sm={12} container>*/}
            {/*    <Grid item xs={2}>*/}
            {/*        <Typography variant="subtitle1">{caption}</Typography>*/}
            {/*    </Grid>*/}
            {/*    <Grid item xs={10}>*/}
            {/*        /!*{widget === 'GenuNumberEditor' && (<GenuNumberEditor   value={field}  onChange={(event) => console.log(event.target.value)} /> )}*!/*/}
            {/*        {EditorComponent}*/}
            {/*    </Grid>*/}
            {/*    <Grid item xs={12}>*/}
            {/*        {info && <Typography variant="caption" color="textSecondary">{info}</Typography>}*/}
            {/*        {warning && <Typography variant="caption" color="warning">{warning}</Typography>}*/}
            {/*        {error && <Typography variant="caption" color="error">{error}</Typography>}*/}
            {/*    </Grid>*/}
            {/*</Grid>*/}
        </>

    );
};

export default GenuFieldFormItem;
