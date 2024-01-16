import React from 'react'
import {Navigate, Route, Routes} from "react-router-dom";
import {BlogRoutes} from "./blog/BlogRoutes.tsx";
import PanelHomeComponent from "../components/views/panel/PanelHomeComponent.tsx";
import {ServerlessRoutes} from "./serverless/ServerlessRoutes.tsx";


export default function DomainRoutes() {
    console.log("DomainRoutes   called");
    return (
        <Routes>
            <Route path="/" element={<PanelHomeComponent/>}/>
            <Route path="/blogs/*" element={<BlogRoutes/>}/>
            <Route path="/plugins/*" element={<ServerlessRoutes/>}/>
            <Route path="*" element={<Navigate to='/404'/>}/>
        </Routes>
    )
}
