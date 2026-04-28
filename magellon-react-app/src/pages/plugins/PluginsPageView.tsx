import React from 'react';
import { Container, Divider } from '@mui/material';
import { PluginBrowser } from '../../features/plugin-runner/ui/PluginBrowser.tsx';
import { AdminInstalledPanel } from '../../features/plugin-installer';

export const PluginsPageView: React.FC = () => {
    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            {/* v1 admin install pipeline (P8 in PLUGIN_INSTALL_PLAN.md).
                Sits above the runtime browser because the operator's
                first question on this page is usually "what did I
                install?" — that's this panel. The browser below
                answers "what's reachable for dispatch right now?". */}
            <AdminInstalledPanel />
            <Divider sx={{ my: 3 }} />
            <PluginBrowser />
        </Container>
    );
};

export default PluginsPageView;
