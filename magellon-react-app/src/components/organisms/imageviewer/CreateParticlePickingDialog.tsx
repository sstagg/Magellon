
import {useState} from "react";
import {
    AlertProps,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Snackbar,
    TextField
} from "@mui/material";
import Alert from '@mui/material/Alert';
import {Check} from "@mui/icons-material";


const SuccessBox: React.FC = () => {
    return (
        <Snackbar
            open
            autoHideDuration={6000}
            message="Created Successfully!"
        />
    );
};
export const CreateParticlePickingDialog: React.FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
    const [name, setName] = useState('');
    const [showError, setShowError] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);

    const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setName(e.target.value);
        setShowError(false); // Clear the error when the text changes
    };

    const handleCreate = () => {
        if (name.trim() === '') {
            setShowError(true);
        } else {
            // Here you can perform any action with the entered name, such as sending it to an API
            setShowSuccess(true);
            setTimeout(() => {
                setShowSuccess(false);
            }, 6000);
            onClose();
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
                {/*{showError && <Alert severity="error">You have not entered a name</Alert>}*/}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} color="primary">
                    Cancel
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
