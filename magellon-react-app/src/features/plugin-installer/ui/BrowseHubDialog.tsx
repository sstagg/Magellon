/**
 * Modal wrapper around HubCatalogBrowser.
 *
 * Per the operator's "user can open a modal to search and install all
 * plugins available in our hub" — the marketplace browser used to
 * occupy the top of /panel/plugins; behind a modal it stays one click
 * away without dominating the page.
 */
import React from 'react';
import { Dialog, DialogContent, DialogTitle, IconButton } from '@mui/material';
import { X } from 'lucide-react';
import { HubCatalogBrowser } from './HubCatalogBrowser.tsx';

interface BrowseHubDialogProps {
    open: boolean;
    onClose: () => void;
}

export const BrowseHubDialog: React.FC<BrowseHubDialogProps> = ({ open, onClose }) => {
    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth scroll="paper">
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <span style={{ flex: 1 }}>Browse plugin hub</span>
                <IconButton size="small" onClick={onClose} aria-label="close">
                    <X size={16} />
                </IconButton>
            </DialogTitle>
            <DialogContent dividers>
                <HubCatalogBrowser />
            </DialogContent>
        </Dialog>
    );
};
