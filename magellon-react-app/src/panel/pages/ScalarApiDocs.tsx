import { ApiReferenceReact } from '@scalar/api-reference-react';
import '@scalar/api-reference-react/style.css';
import { Box, CircularProgress, Typography } from '@mui/material';
import { settings } from '../../core/settings.ts';
import { useEffect, useState } from 'react';
import getAxiosClient from '../../core/AxiosClient.ts';

export default function ScalarApiDocs() {
  const [spec, setSpec] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSpec = async () => {
      try {
        const axiosClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);
        const response = await axiosClient.get('/openapi.json');
        setSpec(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch OpenAPI spec:', err);
        setError(err.message || 'Failed to load API documentation');
      } finally {
        setLoading(false);
      }
    };

    fetchSpec();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 64px - 56px)' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 64px - 56px)' }}>
        <Typography color="error">Error: {error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: 'calc(100vh - 64px - 56px)', width: '100%' }}>
      <ApiReferenceReact
        configuration={{
          spec: {
            content: spec,
          },
        }}
      />
    </Box>
  );
}
