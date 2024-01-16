import React, { useState, ChangeEvent } from 'react';
import {GenuType, IGenuSoloEditorProps, IGenuWidgetProps} from "../GenuType.ts";
import {TextField} from "@mui/material";

interface GenuNumberEditorProps extends IGenuSoloEditorProps {
    caption: string;
    value: string;
    onChange: (newValue: string) => void;
    onValueChanged: (oldValue: string, newValue: string) => void;
}

function GenuNumberEditor(props: IGenuWidgetProps)  {
    const [inputValue, setInputValue] = useState(props.value);

    const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
        const newValue = event.target.value;
        setInputValue(newValue);
        //onValueChanged(value, newValue);
    };
    console.log("caption is : " + props.caption);

    return (

        <TextField
            label={props.caption}
            value={props.value}
            onChange={handleInputChange}
            fullWidth
            variant="filled"
            type="number"
        />
    );
};

GenuNumberEditor.allowedTypes = [GenuType.UINT8, GenuType.UINT16, GenuType.UINT32, GenuType.INT16, GenuType.DOUBLE];
export default GenuNumberEditor;
