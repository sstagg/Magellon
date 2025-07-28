import React from 'react';
import { AppBar, Toolbar, Typography, Box } from '@mui/material';

const Navbar = () => {
  return (
    <AppBar position="static">
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <img 
            src="/mug.png" // Path relative to /public folder
            alt="Cryosift Logo"
            style={{ height: 32, marginRight: 8 }}
          />
          <Typography variant="h6" component="div">
            Cryosift
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
