import { Route, Routes } from "react-router-dom";
import { Home } from "../../pages/home/HomePage.tsx";
import { ApiView } from "../../pages/api-docs/ApiView.tsx";
import DomainRoutes from "../../domains/DomainRoutes.tsx";
import { ImagesPageView } from "../../pages/images/ImagesPageView.tsx";
import { RunJobPageView } from "../../pages/run-job/RunJobPageView.tsx";
import MrcViewerPageView from "../../pages/mrc-viewer/MrcViewerPageView.tsx";
import ImportPageView from "../../pages/import/ImportPageView.tsx";
import SettingsView from "../../pages/settings/SettingsView.tsx";

import DashboardView from "../../pages/dashboard/DashboardView.tsx";
import { Box, Container, Typography } from "@mui/material";
import AboutPage from "../../pages/about/AboutPage.tsx";

import {ExportPageView} from "../../pages/export/ExportPageView.tsx";
import {TestIdeaPageView} from "../../panel/pages/TestIdea/TestIdeaPageView.tsx";
import PluginsPageView from "../../pages/plugins/PluginsPageView.tsx";
import PluginRunnerPageView from "../../pages/plugins/PluginRunnerPageView.tsx";
import UserManagementPage from "../../features/user-management/ui/UserManagementPage.tsx";
import LoginPageView from "../../features/auth/ui/LoginPageView.tsx";
import UserProfilePage from "../../features/user-management/ui/UserProfilePage.tsx";
import AccountPage from "../../features/user-management/ui/page.tsx";
import ScalarApiDocs from "../../pages/api-docs/ScalarApiDocs.tsx";
import StoplightApiDocs from "../../pages/api-docs/StoplightApiDocs.tsx";
import SwaggerApiDocs from "../../pages/api-docs/SwaggerApiDocs.tsx";

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
            <Route path="/dashboard" element={<DashboardView />} />
            <Route path="/home" element={<Home />} />
            <Route path="/images" element={<ImagesPageView />} />
            <Route path="/import-job" element={<ImportPageView />} />
            <Route path="/export" element={<ExportPageView />} />
            <Route path="/plugins" element={<PluginsPageView />} />
            <Route path="/plugins/*" element={<PluginRunnerPageView />} />
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
            <Route path="/api-scalar" element={<ScalarApiDocs />} />
            <Route path="/api-stoplight" element={<StoplightApiDocs />} />
            <Route path="/api-swagger" element={<SwaggerApiDocs />} />
        </Routes>
    );
};

export default PanelRoutes;