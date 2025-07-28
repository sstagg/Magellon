import React from 'react';
import { Box, Typography, Link } from '@mui/material';

const Footer = () => {
  return (
    <Box sx={{ textAlign: 'center', mt: 5, py: 3, backgroundColor: '#f0f0f0', width: '100%' }}>
      <Typography variant="body2">
        © {new Date().getFullYear()} CryoSift. Part of the <Link href="https://magellon.org" target="_blank" rel="noopener">Magellon Project</Link>.
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        Funded by NIH
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <Link href="/terms" underline="hover">Terms of Use</Link> | 
        <Link href="/terms#data-reuse" underline="hover" sx={{ ml: 1 }}>Data Reuse</Link> |
        <Link href="https://www.magellon.org/groups" target="_blank" rel="noopener" underline="hover" sx={{ ml: 1 }}>Contact Us</Link>
      </Typography>
    </Box>
  );
};

export default Footer;
