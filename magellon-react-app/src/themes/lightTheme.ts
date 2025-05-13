import { createTheme } from '@mui/material/styles';
import { getBaseComponents, getBaseShape, getBaseTypography, DRAWER_BACKGROUND } from './shared';

const lightTheme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#0891b2', // Darker cyan for contrast in light mode
            light: '#22d3ee',
            dark: '#0e7490',
            contrastText: '#ffffff',
        },
        secondary: {
            main: '#6366f1', // Darker indigo for contrast in light mode
            light: '#818cf8',
            dark: '#4f46e5',
            contrastText: '#ffffff',
        },
        background: {
            default: '#f8fafc', // Light background for the main content
            paper: '#ffffff',   // White for cards and surfaces
        },
        text: {
            primary: '#334155', // Dark slate for text
            secondary: '#64748b', // Lighter slate for secondary text
        },
        divider: 'rgba(0, 0, 0, 0.12)',
    },
    typography: getBaseTypography(),
    shape: getBaseShape(),
});

// Add components after the base theme with some light theme-specific overrides
const baseComponents = getBaseComponents(lightTheme);
lightTheme.components = {
    ...baseComponents,
    // Override specific components for light theme while keeping dark header/sidebar
    MuiAppBar: {
        styleOverrides: {
            root: {
                backgroundColor: DRAWER_BACKGROUND, // Keep dark header
            },
        },
    },
    MuiDrawer: {
        styleOverrides: {
            paper: {
                backgroundColor: DRAWER_BACKGROUND, // Keep dark sidebar
                color: 'rgba(255, 255, 255, 0.8)', // Keep light text for dark sidebar
            },
        },
    },
    // Add light theme specific shadows
    MuiPaper: {
        styleOverrides: {
            root: {
                backgroundImage: 'none',
                boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.05)',
            },
        },
    },
};

export default lightTheme;