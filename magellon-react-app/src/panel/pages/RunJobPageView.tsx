import {
    Typography,
    Box,
    useTheme,
    useMediaQuery,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent
} from "@mui/material";
import { useState, useEffect } from "react";
import { Beaker } from "lucide-react";
import { MotionCorForm } from "../components/MotionCorForm.tsx";
import { CTFForm } from "../components/CTFForm.tsx";

type PipelineType = 'frame_alignment' | 'ctf';

const DRAWER_WIDTH = 240;

export const RunJobPageView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Pipeline selection state
    const [selectedPipeline, setSelectedPipeline] = useState<PipelineType>('frame_alignment');

    // Drawer state for layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    const handlePipelineChange = (event: SelectChangeEvent) => {
        setSelectedPipeline(event.target.value as PipelineType);
    };

    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };
        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);
        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    const handleSuccess = (taskId: string, sessionName: string) => {
        console.log(`Task ${taskId} created for session ${sessionName}`);
    };

    const handleError = (error: string) => {
        console.error('Motion correction error:', error);
    };

    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return (
        <Box sx={{
            position: 'fixed',
            top: 64,
            left: leftMargin,
            right: 0,
            bottom: 0,
            zIndex: 1050,
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            <Box sx={{ flex: 1, overflow: 'auto', p: { xs: 2, sm: 3, md: 4 } }}>
                {/* Header Section */}
                <Box sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    alignItems: { xs: 'flex-start', sm: 'center' },
                    gap: { xs: 1, sm: 2 },
                    mb: { xs: 2, sm: 3, md: 4 }
                }}>
                    <Beaker
                        width={isMobile ? 36 : 48}
                        height={isMobile ? 36 : 48}
                        color="#0000FF"
                    />
                    <Box sx={{ flex: 1 }}>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 600 }}>
                            Run Processing Jobs
                        </Typography>
                        <Typography variant="body1" color="textSecondary" sx={{ mt: 0.5 }}>
                            Submit processing jobs for your cryo-EM data
                        </Typography>
                    </Box>
                </Box>

                {/* Pipeline Selector */}
                <Box sx={{ mb: 3 }}>
                    <FormControl sx={{ minWidth: 300 }} variant="filled">
                        <InputLabel id="pipeline-select-label">Pipeline</InputLabel>
                        <Select
                            labelId="pipeline-select-label"
                            id="pipeline-select"
                            value={selectedPipeline}
                            onChange={handlePipelineChange}
                        >
                            <MenuItem value="frame_alignment">Frame Alignment (MotionCor2)</MenuItem>
                            <MenuItem value="ctf">CTF Estimation (CTFFIND4)</MenuItem>
                        </Select>
                    </FormControl>
                </Box>

                {/* Conditional Form Rendering */}
                {selectedPipeline === 'frame_alignment' && (
                    <MotionCorForm
                        initialSessionName="testing"
                        onSuccess={handleSuccess}
                        onError={handleError}
                    />
                )}
                {selectedPipeline === 'ctf' && (
                    <CTFForm
                        onSuccess={handleSuccess}
                        onError={handleError}
                    />
                )}
            </Box>
        </Box>
    );
};
