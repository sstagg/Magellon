import React from 'react'
import ReactDOM from 'react-dom/client'
// import OldApp from './components/App.tsx'
import './assets/css/index.css'
import {store} from "./core/reduxStore.ts";
import {Provider as ReduxProvider} from 'react-redux';
import {BrowserRouter} from "react-router-dom";
import AppRoutes from "./AppRoutes.tsx";
import './core/i18n';
import {QueryClient, QueryClientProvider} from "react-query";

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ReduxProvider store={store}>
            <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                        <AppRoutes/>
                </BrowserRouter>
            </QueryClientProvider>
        </ReduxProvider>
    </React.StrictMode>,
)
