import React from 'react'
import ReactDOM from 'react-dom/client'
import './assets/css/index.css'
import {BrowserRouter} from "react-router-dom";
import AppRoutes from "./AppRoutes.tsx";
import './core/i18n';
import {QueryClient, QueryClientProvider} from "react-query";

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
            <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                        <AppRoutes/>
                </BrowserRouter>
            </QueryClientProvider>
    </React.StrictMode>,
)
