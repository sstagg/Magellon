import { Box, Button, Typography, useMediaQuery, useTheme } from "@mui/material";
import Grid from '@mui/material/Grid';
import {
    BarChart,
    ChevronRight,
    Cpu,
    FolderPlus,
    Image as ImageIcon,
    Layers,
    Microscope,
    Settings,
    Upload
} from 'lucide-react';
import { QuickActionCard } from './QuickActionCard.tsx';

interface QuickActionsSectionProps {
    navigateTo: (path: string) => void;
}

// Quick Actions
export const QuickActionsSection = ({ navigateTo }: QuickActionsSectionProps) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

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
                    Quick Actions
                </Typography>

                {isDesktop && (
                    <Button
                        variant="text"
                        endIcon={<ChevronRight size={16} />}
                        size="small"
                    >
                        View All
                    </Button>
                )}
            </Box>

            <Grid container spacing={1.5}>
                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <QuickActionCard
                        title="Import Data"
                        icon={<Upload />}
                        color="#67e8f9"
                        onClick={() => navigateTo('import-job')}
                        featured
                    />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <QuickActionCard
                        title="View Images"
                        icon={<ImageIcon />}
                        color="#818cf8"
                        onClick={() => navigateTo('images')}
                    />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <QuickActionCard
                        title="Process Data"
                        icon={<Layers />}
                        color="#8b5cf6"
                        onClick={() => navigateTo('run-job')}
                    />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <QuickActionCard
                        title="MRC Viewer"
                        icon={<Microscope />}
                        color="#a78bfa"
                        onClick={() => navigateTo('mrc-viewer')}
                    />
                </Grid>
                {!isMobile && (
                    <>
                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                            <QuickActionCard
                                title="Run Job"
                                icon={<Cpu />}
                                color="#f471b5"
                                onClick={() => navigateTo('run-job')}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                            <QuickActionCard
                                title="New Project"
                                icon={<FolderPlus />}
                                color="#f97316"
                                onClick={() => {}}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                            <QuickActionCard
                                title="Statistics"
                                icon={<BarChart />}
                                color="#10b981"
                                onClick={() => {}}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                            <QuickActionCard
                                title="Settings"
                                icon={<Settings />}
                                color="#6b7280"
                                onClick={() => navigateTo('settings')}
                            />
                        </Grid>
                    </>
                )}
            </Grid>
        </Box>
    );
};
