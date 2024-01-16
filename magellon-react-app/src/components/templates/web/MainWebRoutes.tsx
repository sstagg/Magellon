import {Route, Routes} from "react-router-dom";
import {Home} from "../../views/web/Home.tsx";
import {ServicesView} from "../../views/web/ServicesView.tsx";



export const MainWebRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/services" element={<ServicesView />} />
        </Routes>
    );
};
