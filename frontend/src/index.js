import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import SimpleApp from './SimpleApp';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <SimpleApp />
  </React.StrictMode>
);
