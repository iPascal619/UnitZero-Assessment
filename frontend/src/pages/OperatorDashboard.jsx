import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { ClipboardList } from 'lucide-react';

export default function OperatorDashboard() {
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [liveEvents, setLiveEvents] = useState([]);
  const eventSourceRef = useRef(null);

  const loadRequests = async () => {
    try {
      const data = await api.listRequests(statusFilter || undefined);
      setRequests(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRequests(); }, [statusFilter]);

  // SSE: Real-time updates (stretch item)
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    let cancelled = false;

    async function connectSSE() {
      try {
        const response = await fetch('/api/events', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value);
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                setLiveEvents(prev => [data, ...prev].slice(0, 10));
                // Refresh the list
                loadRequests();
              } catch {}
            }
          }
        }
      } catch {}
    }

    connectSSE();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleTransition = async (requestId, newStatus) => {
    setError('');
    try {
      await api.transitionStatus(requestId, newStatus);
      setSuccess(`Request #${requestId} → ${newStatus}`);
      setTimeout(() => setSuccess(''), 3000);
      loadRequests();
    } catch (err) {
      setError(err.message);
    }
  };

  const statusLabel = (s) => s.replace('_', ' ');

  const getTransitions = (request) => {
    const t = [];
    if (request.status === 'submitted') t.push('in_progress');
    if (request.status === 'in_progress') t.push('delivered');
    if (request.status === 'rejected') t.push('in_progress');
    return t;
  };

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>All Requests <span className="live-dot" title="Live updates"></span></h2>
          <p className="subtitle">Manage dataset collection workflow</p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Live events toast */}
      {liveEvents.length > 0 && (
        <div className="toast-container">
          {liveEvents.slice(0, 3).map((evt, i) => (
            <div key={i} className="toast toast-info">
              {evt.from_status
                ? `Request #${evt.request_id}: ${evt.from_status} → ${evt.to_status}`
                : `New request #${evt.request_id}: ${evt.task_name}`}
            </div>
          ))}
        </div>
      )}

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Total</div>
          <div className="stat-value">{requests.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Submitted</div>
          <div className="stat-value">{requests.filter(r => r.status === 'submitted').length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">In Progress</div>
          <div className="stat-value">{requests.filter(r => r.status === 'in_progress').length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Delivered</div>
          <div className="stat-value">{requests.filter(r => r.status === 'delivered').length}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <select
          className="form-control"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="submitted">Submitted</option>
          <option value="in_progress">In Progress</option>
          <option value="delivered">Delivered</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {/* Requests Table */}
      <div className="card">
        {requests.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><ClipboardList size={48} /></div>
            <p>No requests match your filter.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Client</th>
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
                    <td>{req.client_username}</td>
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
                    <td style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                      {getTransitions(req).map(t => (
                        <button
                          key={t}
                          className={`btn btn-sm ${t === 'delivered' ? 'btn-primary' : 'btn-outline'}`}
                          onClick={() => handleTransition(req.id, t)}
                        >
                          → {statusLabel(t)}
                        </button>
                      ))}
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate(`/requests/${req.id}`)}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
