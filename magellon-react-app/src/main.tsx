import React from 'react'
import ReactDOM from 'react-dom/client'
import './assets/css/index.css'
import {BrowserRouter} from "react-router-dom";
import AppRoutes from "./app/routes/AppRoutes.tsx";
import './shared/i18n/i18n.ts';
import {QueryClient, QueryClientProvider} from "react-query";

import { ThemeProvider } from './app/providers/theme';
import {AuthProvider} from "./features/auth/model/AuthContext.tsx";

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