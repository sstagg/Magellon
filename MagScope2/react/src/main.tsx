import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import TestIdeaPageView from './pages/TestIdea/TestIdeaPageView';

ReactDOM.createRoot(document.getElementById('app')!).render(
  <React.StrictMode>
    <TestIdeaPageView />
  </React.StrictMode>
);
