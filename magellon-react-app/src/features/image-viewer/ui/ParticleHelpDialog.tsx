import React from 'react';
import {
    Typography,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    List,
    ListItem,
    ListItemText,
    Stack,
} from '@mui/material';
import { HelpCircle } from 'lucide-react';

export interface ParticleHelpDialogProps {
    open: boolean;
    onClose: () => void;
}

export const ParticleHelpDialog: React.FC<ParticleHelpDialogProps> = ({
    open,
    onClose,
}) => {
    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                <Stack direction="row" spacing={1} sx={{
                    alignItems: "center"
                }}>
                    <HelpCircle />
                    <Typography variant="h6">Particle Picking Help</Typography>
                </Stack>
            </DialogTitle>
            <DialogContent>
                <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                    Keyboard Shortcuts
                </Typography>
                <List dense>
                    <ListItem>
                        <ListItemText primary="1-6" secondary="Select tools (Add, Remove, Select, Move, Box, Brush)" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+Z / Cmd+Z" secondary="Undo last action" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+Shift+Z / Cmd+Shift+Z" secondary="Redo last action" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+A / Cmd+A" secondary="Select all particles" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+C / Cmd+C" secondary="Copy selected particles" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+V / Cmd+V" secondary="Paste particles" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Delete" secondary="Delete selected particles" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="G" secondary="Toggle grid" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="H" secondary="Show this help" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="+/-" secondary="Zoom in/out" />
                    </ListItem>
                </List>

                <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                    Mouse Controls
                </Typography>
                <List dense>
                    <ListItem>
                        <ListItemText primary="Left Click" secondary="Apply current tool action" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Right Click" secondary="Quick remove particle" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Middle Mouse / Alt+Drag" secondary="Pan view" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Scroll Wheel" secondary="Zoom in/out" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Shift+Click" secondary="Add to selection" />
                    </ListItem>
                    <ListItem>
                        <ListItemText primary="Ctrl+Click" secondary="Toggle selection" />
                    </ListItem>
                </List>

                <Typography variant="subtitle1" sx={{ mt: 2 }}>
                    Tips
                </Typography>
                <List dense>
                    <ListItem>
                        <ListItemText
                            primary="Use particle classes"
                            secondary="Categorize particles as Good, Edge, Contamination, or Uncertain"
                        />
                    </ListItem>
                    <ListItem>
                        <ListItemText
                            primary="Auto-picking"
                            secondary="Use the auto-pick feature for initial particle detection, then refine manually"
                        />
                    </ListItem>
                    <ListItem>
                        <ListItemText
                            primary="Save frequently"
                            secondary="Press Ctrl+S to save your work regularly"
                        />
                    </ListItem>
                </List>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
};
