import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { Home } from "../../pages/home/HomePage.tsx";
import DomainRoutes from "../../domains/DomainRoutes.tsx";
import { ImagesPageView } from "../../pages/images/ImagesPageView.tsx";
import { RunJobPageView } from "../../pages/run-job/RunJobPageView.tsx";
import ImportPageView from "../../pages/import/ImportPageView.tsx";
import SettingsView from "../../pages/settings/SettingsView.tsx";

import DashboardView from "../../pages/dashboard/DashboardView.tsx";
import { Box, CircularProgress, Container, Typography } from "@mui/material";
import AboutPage from "../../pages/about/AboutPage.tsx";
import { FftTestPage } from "../../pages/dev/FftTestPage.tsx";
import { PtolemyTestPage } from "../../pages/dev/PtolemyTestPage.tsx";
import { TopazTestPage } from "../../pages/dev/TopazTestPage.tsx";
import { RealtimeMockPage } from "../../pages/dev/RealtimeMockPage.tsx";

import {ExportPageView} from "../../pages/export/ExportPageView.tsx";
import PluginsPageView from "../../pages/plugins/PluginsPageView.tsx";
import PluginRunnerPageView from "../../pages/plugins/PluginRunnerPageView.tsx";
import LoginPageView from "../../features/auth/ui/LoginPageView.tsx";
import UserProfilePage from "../../features/user-management/ui/UserProfilePage.tsx";
import AccountPage from "../../features/user-management/ui/page.tsx";

// Heavy, infrequently visited routes — split out so the main bundle stays lean.
const MrcViewerPageView = lazy(() => import("../../pages/mrc-viewer/MrcViewerPageView.tsx"));
const ApiView = lazy(() => import("../../pages/api-docs/ApiView.tsx").then(m => ({ default: m.ApiView })));
const ScalarApiDocs = lazy(() => import("../../pages/api-docs/ScalarApiDocs.tsx"));
const SwaggerApiDocs = lazy(() => import("../../pages/api-docs/SwaggerApiDocs.tsx"));
const PipelineHealthPage = lazy(() => import("../../pages/admin/PipelineHealthPage.tsx"));

const RouteFallback = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 240 }}>
        <CircularProgress />
    </Box>
);

const TestView = () => (
    <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Test Environment
            </Typography>
            <Typography variant="body1" sx={{
                marginBottom: "16px"
            }}>
                This area is for testing and development purposes.
            </Typography>
        </Box>
    </Container>
);

export const PanelRoutes = () => {
    return (
        <Suspense fallback={<RouteFallback />}>
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
                <Route path="/dev/fft-test" element={<FftTestPage />} />
                <Route path="/dev/ptolemy-test" element={<PtolemyTestPage />} />
                <Route path="/dev/topaz-test" element={<TopazTestPage />} />
                <Route path="/dev/realtime-mock" element={<RealtimeMockPage />} />
                <Route path="/admin/pipeline-health" element={<PipelineHealthPage />} />
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
                <Route path="/api-swagger" element={<SwaggerApiDocs />} />
            </Routes>
        </Suspense>
    );
};

export default PanelRoutes;
