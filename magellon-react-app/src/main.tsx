import React from 'react'
import ReactDOM from 'react-dom/client'
import './assets/css/index.css'
import {BrowserRouter} from "react-router-dom";
import AppRoutes from "./app/routes/AppRoutes.tsx";
import {QueryClient, QueryClientProvider} from "@tanstack/react-query";

import { ThemeProvider } from './app/providers/theme';
import { AppErrorBoundary } from './app/providers/AppErrorBoundary';
import {AuthProvider} from "./features/auth/model/AuthContext.tsx";

// Shared data-fetching policy (see docs/adr/0001-react-query.md):
// most viewer data is immutable per acquisition, so a 30s staleTime
// kills refetch storms on tab focus; one retry covers transient blips
// without masking real outages behind long spinners.
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <AppErrorBoundary>
            <ThemeProvider>
                <QueryClientProvider client={queryClient}>
                  <AuthProvider>
                    <BrowserRouter>
                        <AppRoutes/>
                    </BrowserRouter>
                  </AuthProvider>
                </QueryClientProvider>
            </ThemeProvider>
        </AppErrorBoundary>
    </React.StrictMode>,
)