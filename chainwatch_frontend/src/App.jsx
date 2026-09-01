import { useState, useEffect } from 'react';
import MetricCards from './components/MetricCards';
import AlertTable from './components/AlertTable';
import ChartsView from './components/ChartsView';
import GraphView from './components/GraphView';
import './index.css';

const API = 'http://localhost:8000/api/v1';

function useAPI(endpoint) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API}${endpoint}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [endpoint]);

  return { data, loading, error };
}

function Topbar({ anomalyCount }) {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div className="brand-icon">⛓</div>
        <span className="brand-name">ChainWatch</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 4 }}>Intelligence Platform</span>
      </div>

      <div className="topbar-status">
        <div className="status-dot" />
        <span>Neo4j-backed · Offline pipeline</span>
        <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>
          {time.toLocaleTimeString('en-IN', { hour12: false })}
        </span>
      </div>

      <div className="topbar-actions">
        {anomalyCount !== null && (
          <span className="badge badge-danger">
            🚨 {anomalyCount} ALERTS
          </span>
        )}
        <span className="badge badge-success">
          ✓ OFFLINE MODE
        </span>
      </div>
    </header>
  );
}

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI('/stats');
  const { data: alerts, loading: alertsLoading } = useAPI('/anomalies?limit=50');
  const { data: clusters, loading: clustersLoading } = useAPI('/clusters');
  const { data: graphData, loading: graphLoading } = useAPI('/graph');

  // Cross-component state
  const [highlightedWallet, setHighlightedWallet] = useState(null);

  // Client-side filtering state
  const [minConfidence, setMinConfidence] = useState(0);
  const [selectedCluster, setSelectedCluster] = useState(null);

  // Filter alerts
  const filteredAlerts = alerts?.filter(a => {
    if (a.confidence_score < minConfidence) return false;
    if (selectedCluster !== null && a.cluster_id !== selectedCluster) return false;
    return true;
  });

  return (
    <div className="app-shell">
      <Topbar anomalyCount={stats?.anomalies_detected ?? null} />

      <main className="main-content">
        {/* ── Metric Cards ── */}
        <MetricCards stats={statsLoading ? null : stats} />

        {/* ── Analytical Charts (Donut & Bar only) ── */}
        <ChartsView stats={stats} clusters={clusters} />

        {/* ── Dashboard Grid: Two Column (Graph & Alerts) ── */}
        <div className="dashboard-grid two-column">
          
          {/* Left: Graph Panel */}
          <div className="card graph-card">
            <div className="card-header">
              <div className="card-title">
                <span className="card-title-icon">🕸</span>
                Entity Correlation Graph
              </div>
              <div className="graph-legend">
                <div className="legend-item"><div className="legend-dot" style={{ background: '#3b82f6' }} /> IP Node</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: '#a855f7' }} /> Transaction</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: '#00d4aa' }} /> Wallet</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: '#ff4d6d' }} /> Flagged</div>
              </div>
            </div>
            <div className="graph-body">
              <GraphView 
                data={graphData} 
                loading={graphLoading} 
                highlightNode={highlightedWallet} 
              />
            </div>
          </div>

          {/* Right: Alert Panel */}
          <div className="card alert-panel">
            <div className="card-header">
              <div className="card-title">
                <span className="card-title-icon">🚨</span>
                Flagged Entities Watchlist & AI Insights
              </div>
              {filteredAlerts && (
                <span className="count-chip">{filteredAlerts.length}</span>
              )}
            </div>
            <AlertTable 
              alerts={filteredAlerts} 
              loading={alertsLoading} 
              clusters={clusters}
              selectedWallet={highlightedWallet}
              onSelectWallet={setHighlightedWallet}
              minConfidence={minConfidence}
              onMinConfidenceChange={setMinConfidence}
              selectedCluster={selectedCluster}
              onClusterChange={setSelectedCluster}
            />
          </div>
        </div>
      </main>

      <footer className="footer">
        <span>ChainWatch v1.0 — NTRO Problem Statement Demo — Sept 5, 2026</span>
        <div className="footer-tech">
          <span className="tech-tag">Neo4j 5.12</span>
          <span className="tech-tag">Isolation Forest</span>
          <span className="tech-tag">FastAPI</span>
          <span className="tech-tag">React + Vite</span>
          <span className="tech-tag">100% Offline</span>
        </div>
      </footer>
    </div>
  );
}
