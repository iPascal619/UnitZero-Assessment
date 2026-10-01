import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function ClientDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create form state
  const [form, setForm] = useState({
    task_name: '',
    episodes_requested: '',
    deadline: '',
    notes: '',
  });

  const loadRequests = async () => {
    try {
      const data = await api.listRequests();
      setRequests(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRequests(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.createRequest({
        task_name: form.task_name,
        episodes_requested: parseInt(form.episodes_requested),
        deadline: form.deadline,
        notes: form.notes || null,
      });
      setShowCreate(false);
      setForm({ task_name: '', episodes_requested: '', deadline: '', notes: '' });
      setSuccess('Request created successfully!');
      setTimeout(() => setSuccess(''), 3000);
      loadRequests();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleTransition = async (requestId, status) => {
    setError('');
    try {
      await api.transitionStatus(requestId, status);
      setSuccess(`Request ${status} successfully!`);
      setTimeout(() => setSuccess(''), 3000);
      loadRequests();
    } catch (err) {
      setError(err.message);
    }
  };

  const statusLabel = (s) => s.replace('_', ' ');

  if (loading) return <div className="main-content"><p>Loading...</p></div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>My Requests</h2>
          <p className="subtitle">Manage your dataset collection requests</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New Request
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value">{requests.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pending Review</div>
          <div className="stat-value">{requests.filter(r => r.status === 'delivered').length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Accepted</div>
          <div className="stat-value">{requests.filter(r => r.status === 'accepted').length}</div>
        </div>
      </div>

      {/* Requests Table */}
      <div className="card">
        {requests.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <p>No requests yet. Create your first dataset request!</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Task</th>
                  <th>Episodes</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(req => (
                  <tr key={req.id}>
                    <td>#{req.id}</td>
                    <td>{req.task_name}</td>
                    <td>{req.assigned_count} / {req.episodes_requested}</td>
                    <td>{req.deadline}</td>
                    <td><span className={`badge badge-${req.status}`}>{statusLabel(req.status)}</span></td>
                    <td>
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${Math.min(100, (req.assigned_count / req.episodes_requested) * 100)}%` }}
                        />
                      </div>
                    </td>
                    <td>
                      {req.status === 'delivered' && (
                        <>
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => handleTransition(req.id, 'accepted')}
                            style={{ marginRight: '0.5rem' }}
                          >
                            ✓ Accept
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => handleTransition(req.id, 'rejected')}
                          >
                            ✕ Reject
                          </button>
                        </>
                      )}
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate(`/requests/${req.id}`)}
                        style={{ marginLeft: '0.5rem' }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Request Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>New Dataset Request</h3>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Task Name</label>
                <input
                  className="form-control"
                  value={form.task_name}
                  onChange={e => setForm({ ...form, task_name: e.target.value })}
                  placeholder="e.g. picking_cups"
                  required
                />
              </div>
              <div className="form-group">
                <label>Episodes Requested</label>
                <input
                  className="form-control"
                  type="number"
                  min="1"
                  value={form.episodes_requested}
                  onChange={e => setForm({ ...form, episodes_requested: e.target.value })}
                  placeholder="e.g. 200"
                  required
                />
              </div>
              <div className="form-group">
                <label>Deadline</label>
                <input
                  className="form-control"
                  type="date"
                  value={form.deadline}
                  onChange={e => setForm({ ...form, deadline: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Notes (optional)</label>
                <textarea
                  className="form-control"
                  value={form.notes}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  placeholder="Any additional requirements..."
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-outline" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Request
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
