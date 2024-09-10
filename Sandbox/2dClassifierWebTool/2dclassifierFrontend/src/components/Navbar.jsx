import React from 'react';
import { AppBar, Toolbar, Typography } from '@mui/material';

const Navbar = () => {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1,textAlign:'left' }}>
          2D Classifier
        </Typography>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
