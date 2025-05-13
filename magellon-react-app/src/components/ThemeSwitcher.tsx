import React from 'react';
import { IconButton, Tooltip, useTheme } from '@mui/material';
import { Moon, Sun } from 'lucide-react';
import { useThemeContext } from '../themes';

interface ThemeSwitcherProps {
    size?: number;
}

const ThemeSwitcher: React.FC<ThemeSwitcherProps> = ({ size = 20 }) => {
    const { themeName, toggleTheme } = useThemeContext();
    const theme = useTheme();

    return (
        <Tooltip title={`Switch to ${themeName === 'dark' ? 'light' : 'dark'} theme`}>
            <IconButton
                onClick={toggleTheme}
                color="inherit"
                sx={{
                    transition: theme.transitions.create('transform', {
                        duration: theme.transitions.duration.shorter,
                    }),
                    '&:hover': {
                        transform: 'rotate(12deg)',
                    },
                }}
            >
                {themeName === 'dark' ? (
                    <Sun size={size} />
                ) : (
                    <Moon size={size} />
                )}
            </IconButton>
        </Tooltip>
    );
};

export default ThemeSwitcher;