import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function RequestDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [request, setRequest] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);

  // Episode assignment state (operator/admin)
  const [showAssign, setShowAssign] = useState(false);
  const [episodes, setEpisodes] = useState([]);
  const [selectedEps, setSelectedEps] = useState([]);
  const [epTaskFilter, setEpTaskFilter] = useState('');
  const [epQualityFilter, setEpQualityFilter] = useState('');
  const [taskNames, setTaskNames] = useState([]);

  const isOperator = user?.role === 'operator' || user?.role === 'admin';

  const loadData = async () => {
    try {
      const [req, assigns, hist] = await Promise.all([
        api.getRequest(id),
        api.listAssignments(id),
        api.getHistory(id),
      ]);
      setRequest(req);
      setAssignments(assigns);
      setHistory(hist);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [id]);

  const loadEpisodes = async () => {
    try {
      const params = { available_only: true, limit: 200 };
      if (epTaskFilter) params.task_name = epTaskFilter;
      if (epQualityFilter) params.quality = epQualityFilter;
      const data = await api.listEpisodes(params);
      setEpisodes(data);
      const names = await api.listTaskNames();
      setTaskNames(names);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleAssign = async () => {
    setError('');
    try {
      await api.assignEpisodes(id, selectedEps);
      setSuccess('Episodes assigned successfully!');
      setTimeout(() => setSuccess(''), 3000);
      setSelectedEps([]);
      setShowAssign(false);
      loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRemoveAssignment = async (assignmentId) => {
    setError('');
    try {
      await api.removeAssignment(id, assignmentId);
      setSuccess('Assignment removed');
      setTimeout(() => setSuccess(''), 3000);
      loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleTransition = async (status) => {
    setError('');
    try {
      await api.transitionStatus(id, status);
      setSuccess(`Status changed to ${status}`);
      setTimeout(() => setSuccess(''), 3000);
      loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const openAssignModal = () => {
    setShowAssign(true);
    loadEpisodes();
  };

  const toggleEpisode = (epId) => {
    setSelectedEps(prev =>
      prev.includes(epId) ? prev.filter(x => x !== epId) : [...prev, epId]
    );
  };

  const statusLabel = (s) => s?.replace('_', ' ') || '';

  if (loading) return <p>Loading...</p>;
  if (!request) return <p>Request not found</p>;

  return (
    <div>
      <button className="btn btn-outline" onClick={() => navigate(-1)} style={{ marginBottom: '1rem' }}>
        ← Back
      </button>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Request Details */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3>Request #{request.id}</h3>
          <span className={`badge badge-${request.status}`}>{statusLabel(request.status)}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Task Name</span>
            <p style={{ fontWeight: 600 }}>{request.task_name}</p>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Episodes</span>
            <p style={{ fontWeight: 600 }}>{request.assigned_count} / {request.episodes_requested}</p>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Client</span>
            <p style={{ fontWeight: 600 }}>{request.client_username}</p>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Deadline</span>
            <p style={{ fontWeight: 600 }}>{request.deadline}</p>
          </div>
          {request.notes && (
            <div style={{ gridColumn: '1 / -1' }}>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Notes</span>
              <p>{request.notes}</p>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="progress-bar" style={{ marginBottom: '1rem' }}>
          <div
            className="progress-bar-fill"
            style={{ width: `${Math.min(100, (request.assigned_count / request.episodes_requested) * 100)}%` }}
          />
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {isOperator && request.status === 'submitted' && (
            <button className="btn btn-primary" onClick={() => handleTransition('in_progress')}>
              → Start Working
            </button>
          )}
          {isOperator && request.status === 'in_progress' && (
            <button className="btn btn-primary" onClick={() => handleTransition('delivered')}>
              → Mark Delivered
            </button>
          )}
          {isOperator && request.status === 'rejected' && (
            <button className="btn btn-primary" onClick={() => handleTransition('in_progress')}>
              → Start Rework
            </button>
          )}
          {user?.role === 'client' && request.status === 'delivered' && (
            <>
              <button className="btn btn-success" onClick={() => handleTransition('accepted')}>
                ✓ Accept
              </button>
              <button className="btn btn-danger" onClick={() => handleTransition('rejected')}>
                ✕ Reject
              </button>
            </>
          )}
          {isOperator && ['submitted', 'in_progress', 'rejected'].includes(request.status) && (
            <button className="btn btn-outline" onClick={openAssignModal}>
              + Assign Episodes
            </button>
          )}
        </div>
      </div>

      {/* Assigned Episodes */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3>Assigned Episodes ({assignments.length})</h3>
        </div>
        {assignments.length === 0 ? (
          <div className="empty-state">
            <p>No episodes assigned yet</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Episode ID</th>
                  <th>Robot</th>
                  <th>Task</th>
                  <th>Quality</th>
                  <th>Duration</th>
                  {isOperator && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {assignments.map(a => (
                  <tr key={a.id}>
                    <td>{a.episode?.episode_id}</td>
                    <td>{a.episode?.robot_id}</td>
                    <td>{a.episode?.task_name}</td>
                    <td><span className={`badge badge-${a.episode?.quality}`}>{a.episode?.quality}</span></td>
                    <td>{a.episode?.duration_seconds ? `${a.episode.duration_seconds}s` : '—'}</td>
                    {isOperator && (
                      <td>
                        {!['delivered', 'accepted'].includes(request.status) && (
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => handleRemoveAssignment(a.id)}
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Status History */}
      <div className="card">
        <div className="card-header">
          <h3>Status History</h3>
        </div>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>From</th>
                <th>To</th>
                <th>By</th>
                <th>When</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {history.map(h => (
                <tr key={h.id}>
                  <td>{h.from_status ? <span className={`badge badge-${h.from_status}`}>{statusLabel(h.from_status)}</span> : '—'}</td>
                  <td><span className={`badge badge-${h.to_status}`}>{statusLabel(h.to_status)}</span></td>
                  <td>{h.username}</td>
                  <td>{new Date(h.changed_at).toLocaleString()}</td>
                  <td>{h.notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assign Episodes Modal */}
      {showAssign && (
        <div className="modal-overlay" onClick={() => setShowAssign(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '700px', maxHeight: '80vh', overflow: 'auto' }}>
            <h3>Assign Episodes to Request #{request.id}</h3>

            <div className="filters-bar">
              <select
                className="form-control"
                value={epTaskFilter}
                onChange={e => { setEpTaskFilter(e.target.value); setTimeout(loadEpisodes, 0); }}
              >
                <option value="">All Tasks</option>
                {taskNames.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select
                className="form-control"
                value={epQualityFilter}
                onChange={e => { setEpQualityFilter(e.target.value); setTimeout(loadEpisodes, 0); }}
              >
                <option value="">All Quality</option>
                <option value="good">Good</option>
                <option value="usable">Usable</option>
              </select>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>
                {selectedEps.length} selected
              </span>
            </div>

            {episodes.length === 0 ? (
              <div className="empty-state">
                <p>No available episodes match your filters</p>
              </div>
            ) : (
              <div className="table-wrapper" style={{ maxHeight: '400px', overflow: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th></th>
                      <th>Episode ID</th>
                      <th>Robot</th>
                      <th>Task</th>
                      <th>Quality</th>
                      <th>Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {episodes.map(ep => (
                      <tr key={ep.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedEps.includes(ep.id)}
                            onChange={() => toggleEpisode(ep.id)}
                          />
                        </td>
                        <td>{ep.episode_id}</td>
                        <td>{ep.robot_id}</td>
                        <td>{ep.task_name}</td>
                        <td><span className={`badge badge-${ep.quality}`}>{ep.quality}</span></td>
                        <td>{ep.duration_seconds ? `${ep.duration_seconds}s` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowAssign(false)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={handleAssign}
                disabled={selectedEps.length === 0}
              >
                Assign {selectedEps.length} Episodes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
