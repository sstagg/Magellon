import React from 'react'
import {Navigate, Route, Routes} from "react-router-dom";

import PanelHomeComponent from "../panel/pages/PanelHomeComponent.tsx";



export default function DomainRoutes() {
    console.log("DomainRoutes   called");
    return (
        <Routes>
            <Route path="/" element={<PanelHomeComponent/>}/>
            <Route path="*" element={<Navigate to='/404'/>}/>
        </Routes>
    )
}
