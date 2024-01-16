import {Route, Routes} from "react-router-dom";
import {Home} from "../../views/web/Home.tsx";
import {ApiView} from "../../views/panel/ApiView.tsx";
import DomainRoutes from "../../../domains/DomainRoutes.tsx";
import {ImagesPageView} from "../../views/panel/ImagesPageView.tsx";
import {TestPageView} from "../../views/panel/TestPageView.tsx";
import {LeginonImportPageView} from "../../views/panel/LeginonImportPageView.tsx";


export const PanelRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/images" element={<ImagesPageView />} />
            <Route path="/leginon-transfer" element={<LeginonImportPageView />} />
            <Route path="/domains/*" element={<DomainRoutes />} />
            <Route path="/api" element={<ApiView />} />
        </Routes>
    );
};
