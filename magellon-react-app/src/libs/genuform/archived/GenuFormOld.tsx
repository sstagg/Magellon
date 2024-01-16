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

interface GenuFormProps {
    name: string;
    caption: string;
    rowSpacing: number;
    colSpacing: number;
    entity: any;
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

    const OnSubmit = (event) => {
        event.preventDefault();
        // console.log(formData); // Replace with your form submission logic
        // console.log(data);
        // // setError("email", {
        // //     type: 'server',
        // //     message: "name is very good",
        // // });
        // const thePerson = new PersonDto();
        // thePerson.name = data.name;
        // thePerson.email = data.email;
        //
        // validate(thePerson).then( errors => {
        //     // errors is an array of validation errors
        //     if (errors.length > 0) {
        //         console.log('validation failed. errors: ',JSON.stringify(errors) );
        //     } else {
        //         console.log('validation succeed');
        //     }
        // })

    };

    const {handleSubmit, register,setError,setValue, formState: {errors, isValid}} = useForm({
        mode: 'onChange',
    });

    const isEmailAvailable = async (email) => {
        try {
            console.log("Email is called")
            //const response = await axios.get(`/api/check-email?email=${email}`); // Replace with your API endpoint
            return  false;
        } catch (error) {
            console.error(error);
            return false;
        }
    };
    // Render the form with the generated content
    return (
        <div>

            <form onSubmit={OnSubmit(handleSubmit)}>
                <TextField
                    label="Name"
                    {...register('name')}
                    error={!!errors.name}
                    helperText={errors.name ? 'Name is required' : ''}
                />

                <TextField
                    label="Email2"
                    {...register('email', {
                        required: 'Email is required',
                        validate: async (value) => {
                            if (!value) return true; // Skip validation if empty
                            const isAvailable = await isEmailAvailable(value);
                            if (!isAvailable) {
                                return 'This email is already in use';
                            }
                            return true;
                        },
                    })}

                    error={!!errors.email}
                    helperText={errors.email ? errors.email.message : ''}
                />

                {/*<EmailField register={register} errors={errors} />*/}

                <Button type="submit" variant="contained" color="primary">
                    Submit
                </Button>
            </form>

            <form id="GenuForm-" onSubmit={OnSubmit}>
                <Grid container rowSpacing={1} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                    <Grid item xs={12}  >
                        <Typography variant="h4">Registration Form</Typography>
                        <Typography>Please fill in the details below:</Typography>
                    </Grid>

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            <FormLabel>Enter Name</FormLabel>
                            <TextField label="Email" ></TextField>
                        </FormControl>
                    </Grid>

                    <Grid item xs={4}>
                        <FormControl fullWidth>
                            <FormLabel>Enter Name</FormLabel>
                            <TextField label="Phone" fullWidth></TextField>
                        </FormControl>
                    </Grid>

                    <Grid item xs={12}>
                        <FormControl fullWidth >
                            <FormLabel>Enter Name</FormLabel>
                            <TextField label="Address" variant="outlined" margin="normal" fullWidth/>
                        </FormControl>
                    </Grid>

                    <Grid item xs={6} >
                        <FormControl variant="outlined" fullWidth>
                            <FormLabel>City</FormLabel>
                            <TextField
                                label="City"
                                variant="outlined"
                                fullWidth
                                margin="normal"
                            />
                        </FormControl>
                    </Grid>
                    <Grid item xs={4}>
                        <FormControl variant="outlined" fullWidth>
                            <FormLabel>State</FormLabel>
                            <Select label="State" value={"California"}>
                                <MenuItem value="California">California</MenuItem>
                                <MenuItem value="New York">New York</MenuItem>
                                <MenuItem value="Texas">Texas</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid item xs={2}>
                        <FormControl variant="outlined" fullWidth>
                            <TextField
                                label="Zip"
                                variant="outlined"
                                fullWidth
                                margin="normal"
                            /></FormControl>
                    </Grid>

                    <Grid item xs={6}>
                        <FormControl >
                            <FormLabel>Subscribe to Newsletter</FormLabel>
                            <FormGroup>
                                <FormControlLabel
                                    control={<Checkbox name="subscribe"/>}
                                    label="Subscribe"
                                />
                            </FormGroup>
                        </FormControl>
                    </Grid>
                    <Grid item xs={6}>
                        <Button variant="contained" color="primary" type="submit"> Submit </Button>
                    </Grid>

                    {formContent}
                </Grid>





            </form>

        </div>

    );
}
export default GenuForm;