import { useState, useEffect } from 'react';
import api from '../api';

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'client',
  });

  const loadUsers = async () => {
    try {
      const data = await api.listUsers();
      setUsers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.createUser(form);
      setShowCreate(false);
      setForm({ username: '', email: '', password: '', role: 'client' });
      setSuccess('User created successfully!');
      setTimeout(() => setSuccess(''), 3000);
      loadUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      setSuccess(`User ${user.username} ${user.is_active ? 'deactivated' : 'activated'}`);
      setTimeout(() => setSuccess(''), 3000);
      loadUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleChangeRole = async (userId, newRole) => {
    try {
      await api.updateUser(userId, { role: newRole });
      setSuccess('Role updated');
      setTimeout(() => setSuccess(''), 3000);
      loadUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>User Management</h2>
          <p className="subtitle">Create and manage user accounts</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New User
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="card">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td style={{ fontWeight: 600 }}>{u.username}</td>
                  <td>{u.email}</td>
                  <td>
                    <select
                      className="form-control"
                      value={u.role}
                      onChange={e => handleChangeRole(u.id, e.target.value)}
                      style={{ width: 'auto', padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    >
                      <option value="client">Client</option>
                      <option value="operator">Operator</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-accepted' : 'badge-rejected'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className={`btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                      onClick={() => handleToggleActive(u)}
                    >
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create New User</h3>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Username</label>
                <input
                  className="form-control"
                  value={form.username}
                  onChange={e => setForm({ ...form, username: e.target.value })}
                  required
                  minLength={3}
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  className="form-control"
                  type="email"
                  value={form.email}
                  onChange={e => setForm({ ...form, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  className="form-control"
                  type="password"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  required
                  minLength={6}
                />
              </div>
              <div className="form-group">
                <label>Role</label>
                <select
                  className="form-control"
                  value={form.role}
                  onChange={e => setForm({ ...form, role: e.target.value })}
                >
                  <option value="client">Client</option>
                  <option value="operator">Operator</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-outline" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
