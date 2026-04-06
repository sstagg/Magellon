import React, { createContext, useContext, useState, useEffect } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';

import darkTheme from './darkTheme';
import lightTheme from './lightTheme';

// Available theme options
export type ThemeName = 'dark' | 'light';

interface ThemeContextType {
    themeName: ThemeName;
    toggleTheme: () => void;
    setTheme: (theme: ThemeName) => void;
}

// Create theme context with default values
const ThemeContext = createContext<ThemeContextType>({
    themeName: 'dark',
    toggleTheme: () => {},
    setTheme: () => {},
});

// Hook to use the theme context
export const useThemeContext = () => useContext(ThemeContext);

interface ThemeProviderProps {
    children: React.ReactNode;
    defaultTheme?: ThemeName;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({
                                                                children,
                                                                defaultTheme = 'dark'
                                                            }) => {
    // Initialize theme from localStorage or default
    const [themeName, setThemeName] = useState<ThemeName>(() => {
        const savedTheme = localStorage.getItem('appTheme');
        return (savedTheme as ThemeName) || defaultTheme;
    });

    // Get the actual theme object based on the theme name
    const theme = themeName === 'light' ? lightTheme : darkTheme;

    // Toggle between light and dark themes
    const toggleTheme = () => {
        setThemeName(prevTheme => prevTheme === 'dark' ? 'light' : 'dark');
    };

    // Set a specific theme
    const setTheme = (newTheme: ThemeName) => {
        setThemeName(newTheme);
    };

    // Save theme preference to localStorage when it changes
    useEffect(() => {
        localStorage.setItem('appTheme', themeName);
    }, [themeName]);

    return (
        <ThemeContext.Provider value={{ themeName, toggleTheme, setTheme }}>
            <MuiThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </MuiThemeProvider>
        </ThemeContext.Provider>
    );
};

export default ThemeProvider;