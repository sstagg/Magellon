import {Routes, Route, Navigate,} from "react-router-dom";
import {MainWebTemplate} from "./components/templates/web/MainWebTemplate.tsx";
import {PanelTemplate} from "./components/templates/panel/PanelTemplate.tsx";
import {PageNotFoundView} from "./components/views/PageNotFoundView.tsx";



const AppRoutes = () => {

    return (
        <Routes>
            {/*<Route path="/" element={<Home/>}/>*/}
            <Route path="/" element={<Navigate to='/en/web'/>}/>
            <Route path="*" element={<Navigate to='/404'/>}/>
            <Route path="404" element={<PageNotFoundView/>}/>
            <Route path="/:lang/web/*" element={<MainWebTemplate/>}/>
            <Route path="/:lang/panel/*" element={<PanelTemplate/>}/>
        </Routes>
    );


};

export default AppRoutes;