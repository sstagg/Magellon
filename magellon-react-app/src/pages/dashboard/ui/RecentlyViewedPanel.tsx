import { Box, Button, Paper, Typography, useTheme } from "@mui/material";
import { ChevronRight } from 'lucide-react';
import { recentlyViewed } from '../model/dashboardData.tsx';
import { RecentlyViewedItem } from './RecentlyViewedItem.tsx';

// Recently Viewed
export const RecentlyViewedPanel = () => {
    const theme = useTheme();

    return (
        <Paper elevation={1} sx={{ borderRadius: 2, mb: 3, overflow: 'hidden' }}>
            <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                    Recently Viewed
                </Typography>
            </Box>

            <Box sx={{ p: 1 }}>
                {recentlyViewed.map((item, index) => (
                    <RecentlyViewedItem
                        key={index}
                        {...item}
                        onClick={() => {}}
                    />
                ))}

                <Button
                    fullWidth
                    variant="text"
                    size="small"
                    endIcon={<ChevronRight size={16} />}
                    sx={{ mt: 1 }}
                >
                    View History
                </Button>
            </Box>
        </Paper>
    );
};
