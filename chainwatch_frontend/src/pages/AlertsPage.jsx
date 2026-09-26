/**
 * AlertsPage.jsx — /alerts
 * ────────────────────────
 * Paginated alert list using GET /api/v1/alerts (frozen endpoint).
 * All filtering and sorting happen server-side — no local sorting/filtering.
 * Clicking an alert navigates to /investigate/:address.
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate }                       from 'react-router-dom';
import CwNav                                 from '../components/CwNav';
import { getAlerts }                         from '../api/alerts';

const SEVERITY_COLOR = {
  critical: 'var(--gov-red)',
  high:     '#c2410c',
  medium:   '#92400e',
  low:      'var(--gov-green)',
};

const SEVERITY_BG = {
  critical: 'var(--gov-red-dim)',
  high:     '#fff7ed',
  medium:   'var(--gov-saffron-dim)',
  low:      'var(--gov-green-dim)',
};

export default function AlertsPage() {
  const navigate = useNavigate();

  // Filter/sort state — all sent to server
  const [severity,  setSeverity]  = useState('');
  const [minRisk,   setMinRisk]   = useState('');
  const [detector,  setDetector]  = useState('');
  const [sort,      setSort]      = useState('risk_score');
  const [order,     setOrder]     = useState('desc');
  const [limit,     setLimit]     = useState(50);
  const [offset,    setOffset]    = useState(0);

  // Data state
  const [alerts,   setAlerts]   = useState([]);
  const [total,    setTotal]    = useState(0);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [selected, setSelected] = useState(null);

  // Fetch whenever filter/sort/page changes
  const fetchAlerts = useCallback(() => {
    setLoading(true);
    setError(null);
    getAlerts({
      severity:  severity  || undefined,
      minRisk:   minRisk   ? parseFloat(minRisk) : undefined,
      detector:  detector  || undefined,
      sort,
      order,
      limit,
      offset,
    })
      .then(data => {
        setAlerts(data.items   ?? []);
        setTotal(data.total    ?? 0);
        setLoading(false);
      })
      .catch(err => {
        setError(err.detail ?? err.message ?? 'Failed to load alerts.');
        setLoading(false);
      });
  }, [severity, minRisk, detector, sort, order, limit, offset]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  // Reset to page 0 when filters change
  const applyFilter = (setter) => (val) => {
    setter(val);
    setOffset(0);
  };

  const handleRowClick = (alert) => {
    setSelected(alert.alert_id);
    navigate(`/investigate/${encodeURIComponent(alert.entity_id)}`);
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#f8fafc' }}>
      <CwNav status="ok" />

      <div className="alerts-page">

        {/* ── Filter toolbar ── */}
        <div className="alerts-toolbar">
          <span style={{ fontSize: 11, fontWeight: 800, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Filters
          </span>

          <select className="page-select" value={severity} onChange={e => applyFilter(setSeverity)(e.target.value)}>
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select className="page-select" value={detector} onChange={e => applyFilter(setDetector)(e.target.value)}>
            <option value="">All Detectors</option>
            <option value="isolation_forest">Isolation Forest</option>
            <option value="peeling_chain">Peeling Chain</option>
            <option value="coinjoin">CoinJoin</option>
            <option value="risk_propagation">Risk Propagation</option>
            <option value="ciou">CIOU</option>
          </select>

          <select className="page-select" value={sort} onChange={e => applyFilter(setSort)(e.target.value)}>
            <option value="risk_score">Sort: Risk Score</option>
            <option value="created_at">Sort: Date</option>
            <option value="severity">Sort: Severity</option>
          </select>

          <select className="page-select" value={order} onChange={e => applyFilter(setOrder)(e.target.value)}>
            <option value="desc">Desc</option>
            <option value="asc">Asc</option>
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 10, color: '#64748b', fontWeight: 700 }}>Min Risk</span>
            <input
              type="number" min="0" max="100" placeholder="0"
              value={minRisk}
              onChange={e => applyFilter(setMinRisk)(e.target.value)}
              style={{
                width: 52, padding: '4px 6px', border: '1px solid #94a3b8',
                borderRadius: 2, fontSize: 11, fontFamily: 'var(--mono)',
                background: '#fff', color: '#0f172a',
              }}
            />
          </div>

          <div style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b', fontWeight: 600 }}>
            {loading ? 'Loading…' : `${total.toLocaleString()} alert${total !== 1 ? 's' : ''}`}
          </div>
        </div>

        {/* ── Alert list ── */}
        <div className="alerts-list">
          {error && (
            <div style={{ padding: '20px 24px', color: 'var(--gov-red)', fontSize: 12 }}>⚠ {error}</div>
          )}

          {!loading && !error && alerts.length === 0 && (
            <div style={{ padding: '48px 24px', textAlign: 'center', color: '#64748b', fontSize: 13 }}>
              No alerts match the current filters.
            </div>
          )}

          {alerts.map((alert, idx) => {
            const score    = Math.round(alert.risk_score ?? 0);
            const sev      = alert.severity ?? 'low';
            const factors  = alert.risk_factors ?? [];
            const isSelected = selected === alert.alert_id;

            return (
              <div
                key={alert.alert_id ?? idx}
                className={`alerts-row${isSelected ? ' selected' : ''}`}
                onClick={() => handleRowClick(alert)}
              >
                {/* Rank */}
                <span className="alerts-row__rank">
                  #{offset + idx + 1}
                </span>

                {/* Risk score — colored by severity */}
                <span
                  className="alerts-row__score"
                  style={{ color: SEVERITY_COLOR[sev] ?? '#64748b' }}
                >
                  {score}%
                </span>

                {/* Main content */}
                <div className="alerts-row__main">
                  <div className="alerts-row__wallet">
                    {alert.entity_id ?? '—'}
                  </div>
                  <div className="alerts-row__meta">
                    {alert.primary_state && <span>{alert.primary_state}</span>}
                    {alert.detector      && <span>{alert.detector.replace(/_/g, ' ')}</span>}
                    {alert.cluster_name  && <span>{alert.cluster_name}</span>}
                    {factors.length > 0  && (
                      <span style={{ color: 'var(--gov-red)' }}>
                        ⚠ {factors[0]}{factors.length > 1 ? ` +${factors.length - 1}` : ''}
                      </span>
                    )}
                  </div>
                </div>

                {/* Severity badge */}
                <span style={{
                  flexShrink: 0,
                  fontSize: 9,
                  fontWeight: 800,
                  padding: '2px 7px',
                  borderRadius: 2,
                  border: `1px solid ${SEVERITY_COLOR[sev] ?? '#cbd5e1'}`,
                  background: SEVERITY_BG[sev] ?? '#f8fafc',
                  color: SEVERITY_COLOR[sev] ?? '#64748b',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>
                  {sev}
                </span>

                <span className="alerts-row__arrow">→</span>
              </div>
            );
          })}
        </div>

        {/* ── Pagination ── */}
        {total > 0 && (
          <div className="alerts-pagination">
            <span>
              Page {currentPage} of {totalPages} · {total.toLocaleString()} total
            </span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button
                className="inv-btn inv-btn--sm"
                disabled={offset === 0}
                style={{ opacity: offset === 0 ? 0.4 : 1 }}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                ← Prev
              </button>
              <select
                className="page-select"
                value={limit}
                onChange={e => { setLimit(Number(e.target.value)); setOffset(0); }}
              >
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
                <option value={100}>100 / page</option>
              </select>
              <button
                className="inv-btn inv-btn--sm"
                disabled={offset + limit >= total}
                style={{ opacity: offset + limit >= total ? 0.4 : 1 }}
                onClick={() => setOffset(offset + limit)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
