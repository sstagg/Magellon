import {Routes, Route, Navigate,} from "react-router-dom";
import {MainWebTemplate} from "./web/MainWebTemplate.tsx";
import {PanelTemplate} from "./panel/PanelTemplate.tsx";
import {PageNotFoundView} from "./panel/PageNotFoundView.tsx";
import LoginPageView from "./account/LoginPageView.tsx";
import {useAuth} from "./account/UserManagement/AuthContext.tsx";
import {PublicRoute} from "./account/PublicRoute.tsx";
import { ProtectedRoute } from "./account/ProtectedRoute.tsx";



const AppRoutes = () => {
    const { isAuthenticated, loading } = useAuth();

    // Show loading screen while checking authentication status
    if (loading) {
        return (
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '100vh',
                flexDirection: 'column',
                gap: '16px'
            }}>
                <div>Loading...</div>
            </div>
        );
    }

    return (
        <Routes>
            {/* Default redirect logic based on authentication */}
            <Route
                path="/"
                element={
                    <Navigate
                        to={isAuthenticated ? '/en/panel/images' : '/en/web/home'}
                        replace
                    />
                }
            />

            {/* 404 Page */}
            <Route path="404" element={<PageNotFoundView />} />

            {/* WEB AREA - Public routes (no authentication required) */}
            <Route path="/:lang/web/*" element={<MainWebTemplate />} />

            {/* ACCOUNT AREA - Authentication routes */}
            <Route
                path="/:lang/account/*"
                element={
                    <PublicRoute redirectTo="/en/panel/images">
                        <LoginPageView />
                    </PublicRoute>
                }
            />

            {/* PANEL AREA - Protected routes (authentication required) */}
            <Route
                path="/:lang/panel/*"
                element={
                    <ProtectedRoute fallback="/en/account/">
                        <PanelTemplate />
                    </ProtectedRoute>
                }
            />

            {/* Catch all other routes and redirect to 404 */}
            <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
    );
};

export default AppRoutes;