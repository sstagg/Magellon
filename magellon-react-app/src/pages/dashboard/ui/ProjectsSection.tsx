import { Box, Button, Typography } from "@mui/material";
import Grid from '@mui/material/Grid';
import { ChevronRight } from 'lucide-react';
import { projects } from '../model/dashboardData.tsx';
import { ProjectCard } from './ProjectCard.tsx';

// Projects Section
export const ProjectsSection = () => {
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
                    Active Projects
                </Typography>

                <Button
                    variant="text"
                    endIcon={<ChevronRight size={16} />}
                    size="small"
                >
                    View All
                </Button>
            </Box>

            <Grid container spacing={2}>
                {projects.map((project, index) => (
                    <Grid key={index} size={{ xs: 12, sm: 6, md: 4 }}>
                        <ProjectCard
                            {...project}
                            onClick={() => {}}
                        />
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};
