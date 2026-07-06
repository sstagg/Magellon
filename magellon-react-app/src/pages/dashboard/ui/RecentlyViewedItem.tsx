import { Box, Typography, alpha, useTheme } from "@mui/material";
import { Database, FileText, Image as ImageIcon } from 'lucide-react';
import type { RecentlyViewedItemProps } from '../model/types.ts';

// Recently viewed item component
export const RecentlyViewedItem = ({ name, type, time, onClick }: RecentlyViewedItemProps) => {
    const theme = useTheme();

    const getIcon = () => {
        switch (type) {
            case "image": return <ImageIcon size={16} />;
            case "session": return <Database size={16} />;
            case "project": return <FileText size={16} />;
            default: return <FileText size={16} />;
        }
    };

    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                p: 1,
                borderRadius: 1,
                cursor: 'pointer',
                '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.05)
                }
            }}
            onClick={onClick}
        >
            <Box
                sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1,
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    color: theme.palette.primary.main
                }}
            >
                {getIcon()}
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 500,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                    }}
                >
                    {name}
                </Typography>
                <Typography
                    variant="caption"
                    sx={{ color: 'text.secondary', display: 'block' }}
                >
                    {time}
                </Typography>
            </Box>
        </Box>
    );
};
