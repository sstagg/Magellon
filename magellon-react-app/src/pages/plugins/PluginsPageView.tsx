import React from 'react';
import { Container } from '@mui/material';
import { PluginBrowser } from '../../features/plugin-runner/ui/PluginBrowser.tsx';

export const PluginsPageView: React.FC = () => {
    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            <PluginBrowser />
        </Container>
    );
};

export default PluginsPageView;
