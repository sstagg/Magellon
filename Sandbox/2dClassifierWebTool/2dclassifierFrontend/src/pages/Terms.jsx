import React from 'react';
import { Box, Typography } from '@mui/material';

const Terms = () => {
  return (
    <Box sx={{ p: 4, maxWidth: 800, margin: 'auto' }}>
      <Typography variant="h4" gutterBottom>Terms of Use</Typography>
      <Typography paragraph>
        This tool is intended for use by researchers and professionals. By using this tool, you agree not to misuse or reverse-engineer the system.
      </Typography>

      <Typography variant="h5" gutterBottom id="data-reuse">Data Re-Use</Typography>
      <Typography paragraph>
        By uploading your data, you consent to CryoSift using the data for internal purposes, including model training and system improvements.
      </Typography>

      <Typography variant="h5" gutterBottom>Support</Typography>
      <Typography paragraph>
        For help or to report an issue, please post on <a href="https://www.magellon.org/groups" target="_blank" rel="noopener">magellon.org</a>.
      </Typography>
    </Box>
  );
};

export default Terms;
