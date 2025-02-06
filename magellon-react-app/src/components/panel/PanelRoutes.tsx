import {Route, Routes} from "react-router-dom";
import {Home} from "../web/Home.tsx";
import {ApiView} from "./pages/ApiView.tsx";
import DomainRoutes from "../../domains/DomainRoutes.tsx";
import {ImagesPageView} from "./pages/ImagesPageView.tsx";
import {LeginonImportComponent} from "./LeginonImportComponent.tsx";
import {RunJobPageView} from "./pages/RunJobPageView.tsx";
import MrcViewerPageView from "./pages/MrcViewerPageView.tsx";
import {ImportPageView} from "./pages/ImportPageView.tsx";


export const PanelRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/images" element={<ImagesPageView />} />
            <Route path="/run-job" element={<RunJobPageView />} />
            <Route path="/import-job" element={<ImportPageView />} />
            <Route path="/domains/*" element={<DomainRoutes />} />
            <Route path="/mrc-viewer" element={<MrcViewerPageView />} />
            <Route path="/2d-ass" element={<MrcViewerPageView />} />
            <Route path="/api" element={<ApiView />} />
        </Routes>
    );
};
