import {Route, Routes} from "react-router-dom";
import {Home} from "../../views/web/Home.tsx";
import {ServicesView} from "../../views/web/ServicesView.tsx";
import Login from "../../../domains/account/Login.tsx";


export const MainWebRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/services" element={<ServicesView />} />
            <Route path="/login/*" element={<Login/>}/>
            <Route path="/register/*" element={<Login/>}/>
            <Route path="/reset-password/*" element={<Login/>}/>
            <Route path="/activate/*" element={<Login/>}/>
        </Routes>
    );
};
