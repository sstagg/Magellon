import './polyfills.ts';
import React from 'react'
import ReactDOM from 'react-dom/client'
import './assets/css/index.css'
import {BrowserRouter} from "react-router-dom";
import AppRoutes from "./AppRoutes.tsx";
import './core/i18n';
import {QueryClient, QueryClientProvider} from "react-query";

import { ThemeProvider } from './themes';
import {AuthProvider} from "./account/UserManagement/AuthContext.tsx";

// Import our new theme provider

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ThemeProvider>
            <QueryClientProvider client={queryClient}>
              <AuthProvider>
                <BrowserRouter>
                    <AppRoutes/>
                </BrowserRouter>
              </AuthProvider>
            </QueryClientProvider>
        </ThemeProvider>
    </React.StrictMode>,
)