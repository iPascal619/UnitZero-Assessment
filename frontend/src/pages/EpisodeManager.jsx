import { useState, useEffect } from 'react';
import api from '../api';
import { Film, Upload } from 'lucide-react';

export default function EpisodeManager() {
  const [episodes, setEpisodes] = useState([]);
  const [taskNames, setTaskNames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [taskFilter, setTaskFilter] = useState('');
  const [qualityFilter, setQualityFilter] = useState('');
  const [importResult, setImportResult] = useState(null);

  const loadEpisodes = async () => {
    try {
      const params = { limit: 200 };
      if (taskFilter) params.task_name = taskFilter;
      if (qualityFilter) params.quality = qualityFilter;
      const data = await api.listEpisodes(params);
      setEpisodes(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTaskNames = async () => {
    try {
      const names = await api.listTaskNames();
      setTaskNames(names);
    } catch {}
  };

  useEffect(() => {
    loadEpisodes();
    loadTaskNames();
  }, [taskFilter, qualityFilter]);

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setError('');
    setImportResult(null);
    try {
      const result = await api.importCSV(file);
      setImportResult(result);
      setSuccess(`Imported ${result.imported} episodes, skipped ${result.skipped}`);
      setTimeout(() => setSuccess(''), 5000);
      loadEpisodes();
      loadTaskNames();
    } catch (err) {
      setError(err.message);
    }
    // Reset file input
    e.target.value = '';
  };

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Episodes</h2>
          <p className="subtitle">Browse and import episode data</p>
        </div>
        <div>
          <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
            <Upload size={16} /> Import CSV
            <input
              type="file"
              accept=".csv"
              onChange={handleImport}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Import Result */}
      {importResult && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h3>Import Results</h3>
            <button className="btn btn-outline btn-sm" onClick={() => setImportResult(null)}>
              Dismiss
            </button>
          </div>
          <div className="stats-row">
            <div className="stat-card">
              <div className="stat-label">Imported</div>
              <div className="stat-value" style={{ color: 'var(--color-success)' }}>{importResult.imported}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Skipped</div>
              <div className="stat-value" style={{ color: 'var(--color-warning)' }}>{importResult.skipped}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Errors</div>
              <div className="stat-value" style={{ color: 'var(--color-danger)' }}>{importResult.errors.length}</div>
            </div>
          </div>
          {importResult.errors.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4 style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>Error Details:</h4>
              {importResult.errors.map((err, i) => (
                <div key={i} className="alert alert-error" style={{ marginBottom: '0.25rem' }}>
                  Row {err.row}: {err.reason} {err.episode_id ? `(${err.episode_id})` : ''}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="filters-bar">
        <select
          className="form-control"
          value={taskFilter}
          onChange={e => setTaskFilter(e.target.value)}
        >
          <option value="">All Tasks</option>
          {taskNames.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          className="form-control"
          value={qualityFilter}
          onChange={e => setQualityFilter(e.target.value)}
        >
          <option value="">All Quality</option>
          <option value="good">Good</option>
          <option value="usable">Usable</option>
          <option value="bad">Bad</option>
        </select>
        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>
          {episodes.length} episodes shown
        </span>
      </div>

      {/* Episodes Table */}
      <div className="card">
        {episodes.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><Film size={48} /></div>
            <p>No episodes found. Import a CSV file to get started.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Episode ID</th>
                  <th>Robot</th>
                  <th>Task</th>
                  <th>Recorded</th>
                  <th>Duration</th>
                  <th>Operator</th>
                  <th>Quality</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {episodes.map(ep => (
                  <tr key={ep.id}>
                    <td style={{ fontFamily: 'monospace' }}>{ep.episode_id}</td>
                    <td>{ep.robot_id}</td>
                    <td>{ep.task_name}</td>
                    <td>{ep.recorded_at ? new Date(ep.recorded_at).toLocaleDateString() : '—'}</td>
                    <td>{ep.duration_seconds ? `${ep.duration_seconds}s` : '—'}</td>
                    <td>{ep.operator_name || '—'}</td>
                    <td><span className={`badge badge-${ep.quality}`}>{ep.quality}</span></td>
                    <td>
                      {ep.is_assigned
                        ? <span className="badge badge-in_progress">Assigned</span>
                        : <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Available</span>
                      }
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
