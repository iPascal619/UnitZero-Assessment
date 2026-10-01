import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Login from './pages/Login';
import Layout from './components/Layout';
import ClientDashboard from './pages/ClientDashboard';
import OperatorDashboard from './pages/OperatorDashboard';
import RequestDetail from './pages/RequestDetail';
import EpisodeManager from './pages/EpisodeManager';
import UserManagement from './pages/UserManagement';

function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" />;
  return children;
}

function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" />;
  if (user.role === 'client') return <Navigate to="/requests" />;
  return <Navigate to="/dashboard" />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Home />} />
          <Route
            path="/requests"
            element={
              <ProtectedRoute>
                <Layout><ClientDashboard /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/requests/:id"
            element={
              <ProtectedRoute>
                <Layout><RequestDetail /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute roles={['operator', 'admin']}>
                <Layout><OperatorDashboard /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/episodes"
            element={
              <ProtectedRoute roles={['operator', 'admin']}>
                <Layout><EpisodeManager /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/users"
            element={
              <ProtectedRoute roles={['admin']}>
                <Layout><UserManagement /></Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
