import {Route, Routes} from "react-router-dom";
import {Home} from "../../views/web/Home.tsx";
import {ApiView} from "../../views/panel/ApiView.tsx";
import DomainRoutes from "../../../domains/DomainRoutes.tsx";
import {ImagesPageView} from "../../views/panel/ImagesPageView.tsx";
import {LeginonImportPageView} from "../../views/panel/LeginonImportPageView.tsx";
import {RunJobPageView} from "../../views/panel/RunJobPageView.tsx";
import MrcViewerPageView from "../../views/panel/MrcViewerPageView.tsx";


export const PanelRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/images" element={<ImagesPageView />} />
            <Route path="/run-job" element={<RunJobPageView />} />
            <Route path="/leginon-transfer" element={<LeginonImportPageView />} />
            <Route path="/domains/*" element={<DomainRoutes />} />
            <Route path="/mrc-viewer" element={<MrcViewerPageView />} />
            <Route path="/2d-ass" element={<MrcViewerPageView />} />
            <Route path="/api" element={<ApiView />} />
        </Routes>
    );
};
