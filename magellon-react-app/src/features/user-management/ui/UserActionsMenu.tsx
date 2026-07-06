import {
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem
} from '@mui/material';
import { Delete, Edit } from '@mui/icons-material';

interface UserActionsMenuProps {
    anchorEl: HTMLElement | null;
    onClose: () => void;
    onEditUser: () => void;
    onDeleteUser: () => void;
}

export default function UserActionsMenu({
    anchorEl,
    onClose,
    onEditUser,
    onDeleteUser
}: UserActionsMenuProps) {
    return (
        <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={onClose}
        >
            <MenuItem onClick={onEditUser}>
                <ListItemIcon><Edit /></ListItemIcon>
                <ListItemText>Edit User</ListItemText>
            </MenuItem>
            <MenuItem onClick={onDeleteUser}>
                <ListItemIcon><Delete /></ListItemIcon>
                <ListItemText>Delete User</ListItemText>
            </MenuItem>
        </Menu>
    );
}
