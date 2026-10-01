import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isOperatorOrAdmin = user?.role === 'operator' || user?.role === 'admin';

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>
            <span className="logo-icon">📊</span>
            Request Desk
          </h1>
        </div>

        <nav className="sidebar-nav">
          {user?.role === 'client' && (
            <NavLink to="/requests" className={({ isActive }) => isActive ? 'active' : ''}>
              📋 My Requests
            </NavLink>
          )}

          {isOperatorOrAdmin && (
            <>
              <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
                📊 All Requests
              </NavLink>
              <NavLink to="/episodes" className={({ isActive }) => isActive ? 'active' : ''}>
                🎬 Episodes
              </NavLink>
            </>
          )}

          {user?.role === 'admin' && (
            <NavLink to="/users" className={({ isActive }) => isActive ? 'active' : ''}>
              👤 Users
            </NavLink>
          )}

          <button onClick={handleLogout} style={{ marginTop: 'auto' }}>
            🚪 Logout
          </button>
        </nav>

        <div className="sidebar-user">
          <div className="user-info">
            <div className="user-avatar">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div>
              <div className="user-name">{user?.username}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
