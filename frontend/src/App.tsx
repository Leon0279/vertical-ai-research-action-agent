import { Spin } from 'antd';
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';

const AgentPlaygroundPage = lazy(() =>
  import('./pages/AgentPlaygroundPage').then((module) => ({
    default: module.AgentPlaygroundPage,
  })),
);
const ProjectsPage = lazy(() =>
  import('./pages/ProjectsPage').then((module) => ({
    default: module.ProjectsPage,
  })),
);
const MemoryPage = lazy(() =>
  import('./pages/MemoryPage').then((module) => ({
    default: module.MemoryPage,
  })),
);

const routeFallback = (
  <div className="route-loading">
    <Spin size="large" />
  </div>
);

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/agent" replace />} />
        <Route
          path="agent"
          element={
            <Suspense fallback={routeFallback}>
              <AgentPlaygroundPage />
            </Suspense>
          }
        />
        <Route
          path="agent/:sessionId"
          element={
            <Suspense fallback={routeFallback}>
              <AgentPlaygroundPage />
            </Suspense>
          }
        />
        <Route
          path="projects"
          element={
            <Suspense fallback={routeFallback}>
              <ProjectsPage />
            </Suspense>
          }
        />
        <Route
          path="memory"
          element={
            <Suspense fallback={routeFallback}>
              <MemoryPage />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/agent" replace />} />
      </Route>
    </Routes>
  );
}
