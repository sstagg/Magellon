import { lazy } from "react";
import { Route, Routes } from "react-router-dom";

// Dev/test pages. This module is only referenced when
// import.meta.env.DEV is true (see PanelRoutes), so production builds
// emit neither this chunk nor any of the page chunks below.
const FftTestPage = lazy(() => import("../../pages/dev/FftTestPage.tsx").then(m => ({ default: m.FftTestPage })));
const PtolemyTestPage = lazy(() => import("../../pages/dev/PtolemyTestPage.tsx").then(m => ({ default: m.PtolemyTestPage })));
const TopazTestPage = lazy(() => import("../../pages/dev/TopazTestPage.tsx").then(m => ({ default: m.TopazTestPage })));
const RealtimeMockPage = lazy(() => import("../../pages/dev/RealtimeMockPage.tsx").then(m => ({ default: m.RealtimeMockPage })));

export default function DevRoutes() {
    return (
        <Routes>
            <Route path="fft-test" element={<FftTestPage />} />
            <Route path="ptolemy-test" element={<PtolemyTestPage />} />
            <Route path="topaz-test" element={<TopazTestPage />} />
            <Route path="realtime-mock" element={<RealtimeMockPage />} />
        </Routes>
    );
}
