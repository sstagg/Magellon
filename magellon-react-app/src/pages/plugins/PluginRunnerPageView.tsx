import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Container,
    Button,
    Stack,
    Alert,
    CircularProgress,
    Box,
} from '@mui/material';
import { ArrowLeft } from 'lucide-react';
import { usePlugins } from '../../features/plugin-runner/api/PluginApi.ts';
import { PluginRunner } from '../../features/plugin-runner/ui/PluginRunner.tsx';

export const PluginRunnerPageView: React.FC = () => {
    const { '*': pluginId } = useParams();
    const navigate = useNavigate();
    const { data: plugins, isLoading } = usePlugins();

    const plugin = plugins?.find((p) => p.plugin_id === pluginId);

    return (
        <Container maxWidth="lg" sx={{ py: 3 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <Button
                    size="small"
                    startIcon={<ArrowLeft size={16} />}
                    onClick={() => navigate('/en/panel/plugins')}
                >
                    All plugins
                </Button>
            </Stack>

            {isLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                    <CircularProgress />
                </Box>
            )}

            {!isLoading && !plugin && (
                <Alert severity="warning">Plugin "{pluginId}" was not found.</Alert>
            )}

            {plugin && <PluginRunner plugin={plugin} />}
        </Container>
    );
};

export default PluginRunnerPageView;
