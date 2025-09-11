import React from 'react';
import { Route, Routes } from "react-router-dom";
import { Home } from "./Home.tsx";

// Placeholder components for additional routes
const About = () => (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h1>About Magellon</h1>
        <p>Learn more about our cutting-edge CryoEM platform and team.</p>
    </div>
);

const Contact = () => (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h1>Contact Us</h1>
        <p>Get in touch with our research team.</p>
    </div>
);

export const MainWebRoutes = () => {
    return (
        <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="/" element={<Home />} />
        </Routes>
    );
};