import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './App';
import Landing from './pages/Landing';
import Discover from './pages/Discover';
import Results from './pages/Results';
import Career from './pages/Career';
import { Spinner } from './components/ui';
import './index.css';

// Dashboard pulls in Recharts (~500 kB); split it into its own chunk.
const Dashboard = lazy(() => import('./pages/Dashboard'));

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Landing />} />
          <Route path="discover" element={<Discover />} />
          <Route path="results" element={<Results />} />
          <Route path="career" element={<Career />} />
          <Route
            path="dashboard"
            element={
              <Suspense fallback={<Spinner label="Loading dashboard…" />}>
                <Dashboard />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
