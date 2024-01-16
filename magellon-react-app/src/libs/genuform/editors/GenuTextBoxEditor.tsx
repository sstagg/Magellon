import React, { useState, ChangeEvent } from 'react';
import {GenuType, IGenuSoloEditorProps, IGenuWidgetProps} from "../GenuType.ts";
import {TextField} from "@mui/material";

interface GenuTextBoxEditorProps extends IGenuSoloEditorProps {
    caption: string;
    value: string;
    onChange: (newValue: string) => void;
    onValueChanged: (oldValue: string, newValue: string) => void;
}

function GenuTextBoxEditor(props: IGenuWidgetProps)  {

    const [inputValue, setInputValue] = useState(props.value);

    const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
        const newValue = event.target.value;
        setInputValue(newValue);
        //onValueChanged(value, newValue);
    };

    return (
        <TextField
            label={props.caption}
            value={props.value}
            onChange={handleInputChange}
            fullWidth
            variant="filled"
        />
    );
};

GenuTextBoxEditor.allowedTypes = [GenuType.STRING];
export default GenuTextBoxEditor;
