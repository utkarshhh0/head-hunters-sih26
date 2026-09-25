import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';

// Pages
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Investigation } from './pages/Investigation';
import { EntityIntelligence } from './pages/EntityIntelligence';
import { NetworkExplorer } from './pages/NetworkExplorer';
import { Timeline } from './pages/Timeline';
import { AnalyticalFindings } from './pages/AnalyticalFindings';
import { Evidence } from './pages/Evidence';
import { Reports } from './pages/Reports';

const ProtectedLayout: React.FC = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <AppShell />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Demo access authentication route */}
          <Route path="/login" element={<Login />} />

          {/* Protected Investigator Workspace Shell */}
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/investigation" element={<Investigation />} />
            <Route path="/entities" element={<EntityIntelligence />} />
            <Route path="/entities/:entityId" element={<EntityIntelligence />} />
            <Route path="/network" element={<NetworkExplorer />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/findings" element={<AnalyticalFindings />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="/reports" element={<Reports />} />
          </Route>

          {/* Fallback to root */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
