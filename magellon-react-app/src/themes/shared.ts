import { Components, Theme } from '@mui/material/styles';

// Common theme components configuration
export const getBaseComponents = (theme: Theme): Components => ({
    MuiCssBaseline: {
        styleOverrides: {
            body: {
                scrollbarColor: "#6b6b6b transparent",
                "&::-webkit-scrollbar, & *::-webkit-scrollbar": {
                    backgroundColor: "transparent",
                    width: 8,
                },
                "&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb": {
                    borderRadius: 8,
                    backgroundColor: "#6b6b6b",
                    minHeight: 24,
                },
                "&::-webkit-scrollbar-thumb:focus, & *::-webkit-scrollbar-thumb:focus": {
                    backgroundColor: "#959595",
                },
                "&::-webkit-scrollbar-thumb:active, & *::-webkit-scrollbar-thumb:active": {
                    backgroundColor: "#959595",
                },
                "&::-webkit-scrollbar-thumb:hover, & *::-webkit-scrollbar-thumb:hover": {
                    backgroundColor: "#959595",
                },
            },
        },
    },
    MuiAppBar: {
        styleOverrides: {
            root: {
                backgroundColor: '#0a1929', // Dark header for both themes
            },
        },
    },
    MuiDrawer: {
        styleOverrides: {
            paper: {
                backgroundColor: '#0a1929', // Dark sidebar for both themes
                color: 'rgba(255, 255, 255, 0.8)', // Slightly softer white text
            },
        },
    },
    MuiButton: {
        styleOverrides: {
            root: {
                textTransform: 'none',
                borderRadius: 8,
            },
            contained: {
                boxShadow: 'none',
                '&:hover': {
                    boxShadow: 'none',
                },
            },
        },
    },
    MuiChip: {
        styleOverrides: {
            root: {
                borderRadius: 4,
            },
        },
    },
    MuiPaper: {
        styleOverrides: {
            root: {
                backgroundImage: 'none',
            },
        },
    },
});

// Common typography settings
export const getBaseTypography = () => ({
    fontFamily: '"Exo 2", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
        fontWeight: 700,
    },
    h2: {
        fontWeight: 700,
    },
    h3: {
        fontWeight: 600,
    },
    h4: {
        fontWeight: 600,
    },
    h5: {
        fontWeight: 500,
    },
    h6: {
        fontWeight: 500,
    },
});

// Common shape settings
export const getBaseShape = () => ({
    borderRadius: 8,
});

// Constants
export const DRAWER_BACKGROUND = '#0a1929';