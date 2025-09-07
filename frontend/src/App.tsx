/**
 * ShadowRealms AI - Main Application Component
 * 
 * This is the root component that sets up the entire application structure.
 * It handles routing, authentication state, and provides the main layout.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Sets up React Router for navigation between different pages
 * 2. Provides authentication context and routing guards
 * 3. Renders the main application layout with navigation
 * 4. Handles loading states and error boundaries
 * 5. Integrates with the authentication store for user state
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';

// Import authentication components and store
import { useAuthStore } from './store/authStore';
import LoginForm from './components/auth/LoginForm';

// Import main application components (to be created)
import Dashboard from './components/Dashboard';
import CampaignDashboard from './components/campaign/CampaignDashboard';
import ChatInterface from './components/chat/ChatInterface';

// Import UI components
import { Button } from './components/ui/Button';
import { Card } from './components/ui/Card';

// Create React Query client for API state management
// This handles caching, background updates, and synchronization
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache data for 5 minutes by default
      staleTime: 5 * 60 * 1000,
      // Keep data in cache for 10 minutes
      cacheTime: 10 * 60 * 1000,
      // Retry failed requests 3 times
      retry: 3,
      // Don't refetch on window focus in development
      refetchOnWindowFocus: process.env.NODE_ENV === 'production',
    },
  },
});

/**
 * Loading Spinner Component
 * Shows a loading animation while the app is initializing
 */
const LoadingSpinner: React.FC = () => (
  <div className="min-h-screen bg-dark-900 flex items-center justify-center">
    <motion.div
      className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full"
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    />
  </div>
);

/**
 * Error Boundary Component
 * Catches and displays errors that occur in the component tree
 */
const ErrorBoundary: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [hasError, setHasError] = React.useState(false);

  React.useEffect(() => {
    const handleError = (error: ErrorEvent) => {
      console.error('Application error:', error);
      setHasError(true);
    };

    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  if (hasError) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <Card className="max-w-md mx-auto p-8 text-center">
          <h2 className="text-2xl font-bold text-red-400 mb-4">Something went wrong</h2>
          <p className="text-gray-300 mb-6">
            An unexpected error occurred. Please refresh the page to try again.
          </p>
          <Button
            onClick={() => window.location.reload()}
            variant="primary"
          >
            Refresh Page
          </Button>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
};

/**
 * Protected Route Component
 * Wraps routes that require authentication
 * Redirects to login if user is not authenticated
 */
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuthStore();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return <LoadingSpinner />;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

/**
 * Public Route Component
 * Wraps routes that should only be accessible when not authenticated
 * Redirects to dashboard if user is already authenticated
 */
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuthStore();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return <LoadingSpinner />;
  }

  // Redirect to dashboard if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

/**
 * Main Application Component
 * This is the root component that renders the entire application
 */
const App: React.FC = () => {
  const { isLoading } = useAuthStore();

  // Show loading spinner while the app is initializing
  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Router>
          <div className="min-h-screen bg-dark-900 text-white">
            <AnimatePresence mode="wait">
              <Routes>
                {/* Public Routes - Only accessible when not authenticated */}
                <Route
                  path="/login"
                  element={
                    <PublicRoute>
                      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900">
                        <motion.div
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.5 }}
                          className="w-full max-w-md mx-auto px-4"
                        >
                          <Card className="p-8">
                            <div className="text-center mb-8">
                              <h1 className="text-3xl font-bold text-primary-400 mb-2">
                                ShadowRealms AI
                              </h1>
                              <p className="text-gray-400">
                                Enter the world of AI-powered tabletop RPG
                              </p>
                            </div>
                            <LoginForm />
                          </Card>
                        </motion.div>
                      </div>
                    </PublicRoute>
                  }
                />

                {/* Protected Routes - Require authentication */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/campaigns"
                  element={
                    <ProtectedRoute>
                      <CampaignDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/campaign/:campaignId/chat"
                  element={
                    <ProtectedRoute>
                      <ChatInterface />
                    </ProtectedRoute>
                  }
                />

                {/* Default redirect */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                
                {/* 404 route */}
                <Route
                  path="*"
                  element={
                    <div className="min-h-screen flex items-center justify-center">
                      <Card className="max-w-md mx-auto p-8 text-center">
                        <h2 className="text-2xl font-bold text-red-400 mb-4">Page Not Found</h2>
                        <p className="text-gray-300 mb-6">
                          The page you're looking for doesn't exist.
                        </p>
                        <Button
                          onClick={() => window.history.back()}
                          variant="secondary"
                        >
                          Go Back
                        </Button>
                      </Card>
                    </div>
                  }
                />
              </Routes>
            </AnimatePresence>
          </div>
        </Router>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
