import React from 'react';
import { Container, Divider } from '@mui/material';
import { PluginBrowser } from '../../features/plugin-runner/ui/PluginBrowser.tsx';
import {
    AdminInstalledPanel,
    HubCatalogBrowser,
} from '../../features/plugin-installer';

export const PluginsPageView: React.FC = () => {
    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            {/* Top: hub marketplace — what's available to install.
                Operators land here looking for "what can I add?";
                the catalog answers that directly. Backed by
                <HUB_URL>/v1/index.json (configs.json, default
                https://demo.magellon.org). */}
            <HubCatalogBrowser />
            <Divider sx={{ my: 3 }} />
            {/* Middle: what's already installed via the v1 admin
                pipeline. Each row offers Upgrade + Uninstall. */}
            <AdminInstalledPanel />
            <Divider sx={{ my: 3 }} />
            {/* Bottom: runtime/dispatch view — what's reachable on
                the bus right now. Different from "installed" (a
                plugin can be installed but not yet announcing). */}
            <PluginBrowser />
        </Container>
    );
};

export default PluginsPageView;
