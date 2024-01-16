import React, {ReactNode} from "react";
import {GenuFieldFormItemProps} from "./GenuType.ts";
import {
    Button,
    Checkbox,
    FormControl,
    FormControlLabel,
    FormGroup,
    FormLabel,
    Grid, InputLabel,
    MenuItem, Paper,
    Select, styled,
    TextField,
    Typography
} from "@mui/material";
import {useForm} from "react-hook-form";
import {IEntity} from "../../core/IEntity.ts";

interface GenuFormProps {
    name: string;
    caption: string;
    rowSpacing: number;
    colSpacing: number;
    entity: IEntity;
    children: ReactNode;
}

// Define the GenuForm component
// const GenuForm: React.FC<GenuFormProps> = ({ name, caption, rowSpacing, colSpacing, children }) => {
function GenuForm(props: GenuFormProps) {
    // Process the children components and generate your form structure
    const formContent = React.Children.map(props.children, child => {
        // You might need to handle different child component types accordingly
        return React.cloneElement(child);
    });


    function generateEntityFields(): void {
        if (!props.entity) {
            return;
        }
        // Iterate through the properties of the entity

        for (const propertyName of Object.keys(props.entity)) {
            const field = new GenuFieldFormItemProps();
            field.name = propertyName;
            field.caption = propertyName; // You can customize this caption as needed

            // Get the type of the attribute
            const attributeType: string = typeof props.entity[propertyName];
            //field.widget = this.getFirstEditorNameForType(attributeType);
            //this.items.push(field);
        }

        // Implement fields generation logic here based on entity's properties
    }
    const Item = styled(Paper)(({ theme }) => ({
        backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
        ...theme.typography.body2,
        padding: theme.spacing(1),
        textAlign: 'center',
        color: theme.palette.text.secondary,
    }));

    const OnFormSubmit = (event) => {
        event.preventDefault();
    };

    const {handleSubmit, register,setError,setValue, formState: {errors, isValid}} = useForm({
        mode: 'onChange',
    });

    // Render the form with the generated content
    return (
            <form id="GenuForm-" onSubmit={OnFormSubmit}>
                <Grid container rowSpacing={1} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                    <Grid item xs={12}  >
                        <Typography variant="h4">Registration Form</Typography>
                        <Typography>Please fill in the details below:</Typography>
                    </Grid>

                    {formContent}

                    <Grid item xs={6}>
                        <Button variant="contained" color="primary" type="submit"> Submit </Button>
                    </Grid>
                </Grid>
            </form>
    );
}
export default GenuForm;