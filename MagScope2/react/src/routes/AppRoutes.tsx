import { Route, Routes, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import MicroscopyPageView from "@/pages/MicroscopyPageView";
import TestIdeaPageView from "@/pages/TestIdea/TestIdeaPageView";
import { MicroscopyHeaderProvider } from "@/contexts/MicroscopyHeaderContext";

export const AppRoutes = () => {
  return (
    <MicroscopyHeaderProvider>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          {/* Redirect root to microscopy */}
          <Route index element={<Navigate to="/microscopy" replace />} />

          {/* Main routes */}
          <Route path="microscopy" element={<MicroscopyPageView />} />
          <Route path="test-idea" element={<TestIdeaPageView />} />

          {/* Catch all - redirect to microscopy */}
          <Route path="*" element={<Navigate to="/microscopy" replace />} />
        </Route>
      </Routes>
    </MicroscopyHeaderProvider>
  );
};

export default AppRoutes;
