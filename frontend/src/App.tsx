import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { QueuesPage } from './pages/QueuesPage';
import { JobsPage } from './pages/JobsPage';
import { JobDetailPage } from './pages/JobDetailPage';
import { WorkersPage } from './pages/WorkersPage';
import { PlatformOverviewPage } from './pages/platform/PlatformOverviewPage';
import { ObservabilityPage } from './pages/platform/ObservabilityPage';
import { BatchJobsPage } from './pages/platform/BatchJobsPage';
import { BatchDetailPage } from './pages/platform/BatchDetailPage';
import { WorkflowsPage } from './pages/platform/WorkflowsPage';
import { RateLimitingPage } from './pages/platform/RateLimitingPage';
import { FailureAnalysisPage } from './pages/platform/FailureAnalysisPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { LoadingSkeleton } from './components/common/LoadingSkeleton';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Unhandled UI Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-center">
          <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
            <h2 className="text-xl font-bold text-rose-400">Application Error</h2>
            <p className="text-xs text-slate-400 font-mono bg-slate-950 p-3 rounded-lg border border-slate-800 text-left overflow-x-auto">
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="w-full py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <LoadingSkeleton type="card" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="queues" element={<QueuesPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />
        <Route path="workers" element={<WorkersPage />} />

        {/* Platform Operations Center Routes */}
        <Route path="platform" element={<PlatformOverviewPage />} />
        <Route path="platform/observability" element={<ObservabilityPage />} />
        <Route path="platform/batches" element={<BatchJobsPage />} />
        <Route path="platform/batches/:batchId" element={<BatchDetailPage />} />
        <Route path="platform/workflows" element={<WorkflowsPage />} />
        <Route path="platform/rate-limits" element={<RateLimitingPage />} />
        <Route path="platform/failures" element={<FailureAnalysisPage />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
};

export default App;
