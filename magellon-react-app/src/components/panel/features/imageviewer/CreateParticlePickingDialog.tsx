
import {useState} from "react";
import {
    Button, CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Snackbar,
    TextField
} from "@mui/material";

import {useCreateParticlePickingMutation} from "../../../../services/api/ParticlePickingRestService.ts";
import ImageInfoDto from "./ImageInfoDto.ts";


const SuccessBox: React.FC = () => {
    return (
        <Snackbar
            open
            autoHideDuration={6000}
            message="Created Successfully!"
        />
    );
};
export const CreateParticlePickingDialog: React.FC<{ open: boolean; onClose: () => void ;ImageDto:ImageInfoDto}> = ({ open, onClose,ImageDto }) => {
    const [name, setName] = useState('');
    const [loading, setLoading] = useState(false);
    const [showError, setShowError] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);
    const mutation = useCreateParticlePickingMutation();

    const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setName(e.target.value);
        setShowError(false); // Clear the error when the text changes
    };

    const handleCreate = async () => {
        if (name.trim() === '') {
            setShowError(true);
        } else {
            try {
                setLoading(true); // Set loading to true
                await mutation.mutateAsync({ metaName: name, imageName: ImageDto?.oid });
                // setShowSuccess(true);
                // setTimeout(() => {
                //     setShowSuccess(false);
                // }, 6000);
                // onClose();
            } catch (error) {
                console.error('Error:', error);
            } finally {
                setLoading(false); // Reset loading state
            }
        }
    };
    const handleCloseAlert = () => {
        setShowError(false);
    };


    return (
        <>
            <Dialog open={open} onClose={onClose} aria-labelledby="form-dialog-title">
            <DialogTitle id="form-dialog-title">Create Particle Picking</DialogTitle>
            <DialogContent>
                <TextField
                    error={showError}
                    autoFocus
                    margin="dense"
                    id="name"
                    label="Name"
                    type="text"
                    fullWidth
                    value={name}
                    onChange={handleTextChange}
                    helperText={showError ? "You have not entered a name" : ""}
                />
                {loading && <CircularProgress />}
                {/*{showError && <Alert severity="error">You have not entered a name</Alert>}*/}
                {mutation.isLoading && <span>Creating...</span>}
                {mutation.isError && <span>Error: {mutation.error.message}</span>}
                {mutation.isSuccess && <span>Entity created successfully</span>}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} color="primary">
                    Close
                </Button>
                <Button onClick={handleCreate} color="primary">
                    Create
                </Button>
            </DialogActions>

        </Dialog>
            {showSuccess && <SuccessBox />}
        </>


    );
};
