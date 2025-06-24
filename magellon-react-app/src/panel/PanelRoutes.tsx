import { Route, Routes } from "react-router-dom";
import { Home } from "../web/Home.tsx";
import { ApiView } from "./pages/ApiView.tsx";
import DomainRoutes from "../domains/DomainRoutes.tsx";
import { ImagesPageView } from "./pages/ImagesPageView.tsx";
import { RunJobPageView } from "./pages/RunJobPageView.tsx";
import MrcViewerPageView from "./pages/MrcViewerPageView.tsx";
import ImportPageView from "./pages/ImportPageView.tsx";
import SettingsView from "./pages/SettingsView.tsx";

import DashboardView from "./pages/DashboardView.tsx";
import { Box, Container, Typography } from "@mui/material";
import AboutPage from "./pages/AboutPage.tsx";
import MicroscopyPageView from "./pages/MicroscopyPageView.tsx";

// Settings placeholder component
// Test placeholder component

// Test placeholder component
const TestView = () => (
    <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Test Environment
            </Typography>
            <Typography variant="body1" paragraph>
                This area is for testing and development purposes.
            </Typography>
        </Box>
    </Container>
);

export const PanelRoutes = () => {
    return (
        <Routes>
            {/* Main routes */}
            <Route path="/microscopy" element={<MicroscopyPageView />} />
            <Route path="/dashboard" element={<DashboardView />} />
            <Route path="/home" element={<Home />} />
            <Route path="/images" element={<ImagesPageView />} />
            <Route path="/import-job" element={<ImportPageView />} />
            <Route path="/test" element={<TestView />} />
            <Route path="/settings" element={<SettingsView />} />

            {/* Processing routes */}
            <Route path="/run-job" element={<RunJobPageView />} />
            <Route path="/mrc-viewer" element={<MrcViewerPageView />} />
            <Route path="/about" element={<AboutPage />} />


            {/* Other routes */}
            <Route path="/domains/*" element={<DomainRoutes />} />
            <Route path="/api" element={<ApiView />} />
        </Routes>
    );
};

export default PanelRoutes;