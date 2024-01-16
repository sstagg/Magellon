import {Navigate, Route, Routes} from "react-router-dom";
import BlogFormComponent from "./BlogFormComponent.tsx";
import BlogTableComponent from "./BlogTableComponent.tsx";

export const BlogRoutes = () => {
    return (
        <Routes>
            {/*<Route path="/" element={<Home/>}/>*/}
            <Route path="/" element={<BlogTableComponent/>}/>
            <Route path="/new" element={<BlogFormComponent/>}/>
            <Route path="/:id" element={<BlogFormComponent/>}/>
            <Route path="/:id/edit" element={<BlogFormComponent/>}/>
            <Route path="/:id/delete" element={<BlogFormComponent/>}/>
            <Route path="/:id/*" element={<Navigate to='/404'/>}/>
        </Routes>
    );
};
