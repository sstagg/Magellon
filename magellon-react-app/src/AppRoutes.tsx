import {Routes, Route, Navigate,} from "react-router-dom";
import {MainWebTemplate} from "./web/MainWebTemplate.tsx";
import {PanelTemplate} from "./panel/PanelTemplate.tsx";
import {PageNotFoundView} from "./panel/PageNotFoundView.tsx";
import LoginPageView from "./account/LoginPageView.tsx";



const AppRoutes = () => {

    return (
        <Routes>
            {/*<Route path="/" element={<Home/>}/>*/}
            <Route path="/" element={<Navigate to='/en/panel/images'/>}/>
            <Route path="*" element={<Navigate to='/404'/>}/>
            <Route path="404" element={<PageNotFoundView/>}/>

            <Route path="/:lang/web/*" element={<MainWebTemplate/>}/>
            <Route path="/:lang/account/" element={<LoginPageView/>}/>
            <Route path="/:lang/panel/*" element={<PanelTemplate/>}/>
        </Routes>
    );


};

export default AppRoutes;