/**
 * /panel/plugins — operator's plugin manager.
 *
 * Two-tab layout (Installed | Downloaded) plus two header action buttons
 * that open install modals. The previous one-page-everything layout
 * conflated "running on the bus" with "registered in the database"
 * with "available in the hub"; the tabs split those by lifecycle.
 *
 *   Hub     — published in the federated registry, not yet on this server
 *   Downloaded — `.mpn` archive uploaded here, not yet installed
 *   Installed — DB row exists; lives in a directory or container
 *   Running — heartbeating on the bus right now (a chip on each card)
 *
 * The Hub view is reached via the "Browse hub" modal — keeps the
 * page surface focused on what's already on this server.
 */
import React, { useState } from 'react';
import {
    Box,
    Button,
    Container,
    Stack,
    Tab,
    Tabs,
    Typography,
} from '@mui/material';
import { Cloud, Puzzle, Upload } from 'lucide-react';
import { CatalogView } from '../../features/plugin-runner/ui/CatalogView.tsx';
import { InstalledPluginsView } from '../../features/plugin-runner/ui/InstalledPluginsView.tsx';
import {
    BrowseHubDialog,
    UploadArchiveDialog,
} from '../../features/plugin-installer';

type TabKey = 'installed' | 'catalog';

export const PluginsPageView: React.FC = () => {
    const [tab, setTab] = useState<TabKey>('installed');
    const [uploadOpen, setUploadOpen] = useState(false);
    const [hubOpen, setHubOpen] = useState(false);

    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 3 }}>
                <Puzzle size={26} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h5">Plugins</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Manage what's installed on this server. Install new
                        plugins from a local archive or browse the hub.
                    </Typography>
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<Upload size={16} />}
                    onClick={() => setUploadOpen(true)}
                >
                    Upload archive
                </Button>
                <Button
                    variant="contained"
                    startIcon={<Cloud size={16} />}
                    onClick={() => setHubOpen(true)}
                >
                    Browse hub
                </Button>
            </Stack>

            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v as TabKey)}
                sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
            >
                <Tab value="installed" label="Installed" />
                <Tab value="catalog" label="Downloaded" />
            </Tabs>

            {tab === 'installed' && (
                <InstalledPluginsView
                    onUploadArchive={() => setUploadOpen(true)}
                    onBrowseHub={() => setHubOpen(true)}
                />
            )}
            {tab === 'catalog' && (
                <CatalogView
                    onUploadArchive={() => setUploadOpen(true)}
                    onBrowseHub={() => setHubOpen(true)}
                />
            )}

            <UploadArchiveDialog
                open={uploadOpen}
                onClose={() => setUploadOpen(false)}
            />
            <BrowseHubDialog open={hubOpen} onClose={() => setHubOpen(false)} />
        </Container>
    );
};

export default PluginsPageView;
