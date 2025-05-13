import { createTheme } from '@mui/material/styles';
import { getBaseComponents, getBaseShape, getBaseTypography } from './shared';

const darkTheme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#67e8f9', // Cyan color that matches our brain circuit icon
            light: '#99ecfb',
            dark: '#0891b2',
            contrastText: '#ffffff',
        },
        secondary: {
            main: '#818cf8', // Indigo that complements the primary color
            light: '#a5b4fc',
            dark: '#6366f1',
            contrastText: '#ffffff',
        },
        background: {
            default: '#111827', // Dark background for the main content
            paper: '#1e293b',  // Slightly lighter for cards and surfaces
        },
        text: {
            primary: '#f1f5f9',
            secondary: '#cbd5e1',
        },
        divider: 'rgba(255, 255, 255, 0.12)',
    },
    typography: getBaseTypography(),
    shape: getBaseShape(),
});

// Add components after creating the base theme to access theme in component overrides
darkTheme.components = getBaseComponents(darkTheme);

export default darkTheme;