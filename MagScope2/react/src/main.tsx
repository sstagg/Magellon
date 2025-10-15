import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import MicroscopyPageView from './pages/MicroscopyPageView';

ReactDOM.createRoot(document.getElementById('app')!).render(
  <React.StrictMode>
    <MicroscopyPageView />
  </React.StrictMode>
);
