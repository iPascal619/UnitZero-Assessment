import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { BarChart2, ClipboardList, BarChart, Film, Users, LogOut } from 'lucide-react';

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
            <BarChart2 className="logo-icon" size={28} />
            Request Desk
          </h1>
        </div>

        <nav className="sidebar-nav">
          {user?.role === 'client' && (
            <NavLink to="/requests" className={({ isActive }) => isActive ? 'active' : ''}>
              <ClipboardList size={18} /> My Requests
            </NavLink>
          )}

          {isOperatorOrAdmin && (
            <>
              <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
                <BarChart size={18} /> All Requests
              </NavLink>
              <NavLink to="/episodes" className={({ isActive }) => isActive ? 'active' : ''}>
                <Film size={18} /> Episodes
              </NavLink>
            </>
          )}

          {user?.role === 'admin' && (
            <NavLink to="/users" className={({ isActive }) => isActive ? 'active' : ''}>
              <Users size={18} /> Users
            </NavLink>
          )}

          <button onClick={handleLogout} style={{ marginTop: 'auto' }}>
            <LogOut size={18} /> Logout
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
