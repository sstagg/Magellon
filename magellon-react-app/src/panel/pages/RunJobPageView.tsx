import {
    Typography,
    Box,
    useTheme,
    useMediaQuery
} from "@mui/material";
import { useState, useEffect } from "react";
import { Beaker } from "lucide-react";
import { MotionCorForm } from "../components/MotionCorForm.tsx";

const DRAWER_WIDTH = 240;

export const RunJobPageView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Drawer state for layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

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
                    <Box>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 600 }}>
                            Run Processing Jobs
                        </Typography>
                        <Typography variant="body1" color="textSecondary" sx={{ mt: 0.5 }}>
                            Submit motion correction (frame alignment) jobs for processing
                        </Typography>
                    </Box>
                </Box>

                {/* Motion Correction Form */}
                <MotionCorForm
                    initialSessionName="testing"
                    onSuccess={handleSuccess}
                    onError={handleError}
                />
            </Box>
        </Box>
    );
};
