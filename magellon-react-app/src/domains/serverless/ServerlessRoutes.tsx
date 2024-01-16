import {Navigate, Route, Routes} from "react-router-dom";
import {ServerlessTableComponent} from "./ServerlessTableComponent.tsx";
import {ServerlessFormComponent} from "./ServerlessFormComponent.tsx";

export const ServerlessRoutes = () => {
    return (
        <Routes>
            {/*<Route path="/" element={<Home/>}/>*/}
            <Route path="/" element={<ServerlessTableComponent/>}/>
            <Route path="/new" element={<ServerlessFormComponent/>}/>
            <Route path="/:id" element={<ServerlessFormComponent/>}/>
            <Route path="/:id/edit" element={<ServerlessFormComponent/>}/>
            <Route path="/:id/delete" element={<ServerlessFormComponent/>}/>
            <Route path="/:id/*" element={<Navigate to='/404'/>}/>
        </Routes>
    );
};
