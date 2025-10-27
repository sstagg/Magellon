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
import {ExportPageView} from "./pages/ExportPageView.tsx";
import {TestIdeaPageView} from "./pages/TestIdea/TestIdeaPageView.tsx";
import UserManagementPage from "../account/UserManagement/UserManagementPage.tsx";
import LoginPageView from "../account/LoginPageView.tsx";
import UserProfilePage from "../account/UserManagement/UserProfilePage.tsx";
import AccountPage from "../account/UserManagement/page.tsx";

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
            <Route path="/export" element={<ExportPageView />} />
            <Route path="/test" element={<TestView />} />
            <Route path="/test-idea" element={<TestIdeaPageView />} />
            <Route path="/settings" element={<SettingsView />} />

            <Route path="/login" element={<LoginPageView />} />
            <Route path="/users" element={<AccountPage />} />
            <Route path="/profile" element={<UserProfilePage />} />

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