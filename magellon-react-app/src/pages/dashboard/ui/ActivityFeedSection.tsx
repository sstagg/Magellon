import { Box, Button, Paper, Typography } from "@mui/material";
import { ChevronRight } from 'lucide-react';
import { activities } from '../model/dashboardData.tsx';
import { ActivityItem } from './ActivityItem.tsx';

// Activity Feed
export const ActivityFeedSection = () => {
    return (
        <Box sx={{ mb: { xs: 2, md: 4 } }}>
            <Box sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 2
            }}>
                <Typography
                    variant="h6"
                    sx={{ fontWeight: 600, fontSize: { xs: '1.1rem', md: '1.25rem' } }}
                >
                    Recent Activity
                </Typography>

                <Button
                    variant="text"
                    endIcon={<ChevronRight size={16} />}
                    size="small"
                >
                    View All
                </Button>
            </Box>

            <Paper
                elevation={1}
                sx={{
                    borderRadius: 2,
                    overflow: 'hidden'
                }}
            >
                <Box sx={{ p: { xs: 1, sm: 2 } }}>
                    {activities.map((activity, index) => (
                        <ActivityItem
                            key={index}
                            {...activity}
                        />
                    ))}
                </Box>
            </Paper>
        </Box>
    );
};
