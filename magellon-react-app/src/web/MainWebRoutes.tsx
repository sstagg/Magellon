import {Route, Routes} from "react-router-dom";
import {Home} from "./Home.tsx";

export const MainWebRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
        </Routes>
    );
};
