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
  return (
    <>
      {/* Black Accessibility Bar */}
      <div className="access-bar">
        <span>Skip to Main Content</span>
        <span>A- A A+</span>
        <span>English | हिन्दी</span>
      </div>
      
      {/* Dark Blue Government Header */}
      <header className="topbar">
        <div className="topbar-brand">
          {/* Emblem filtered to be white on the dark blue background */}
          <img 
            src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg" 
            alt="Satyameva Jayate" 
            style={{ height: '56px', filter: 'brightness(0) invert(1)' }} 
          />
          <div className="brand-titles">
            <div className="brand-goi">Government of India</div>
            <div className="brand-name">National Technical Research Organisation</div>
          </div>
        </div>

        <div className="topbar-actions" style={{ alignItems: 'center' }}>
          <div className="system-title" style={{ fontSize: '16px', borderRight: '1px solid rgba(255,255,255,0.2)', paddingRight: '16px', marginRight: '4px' }}>
            <span style={{ color: '#ffffff', fontWeight: 800 }}>ChainWatch</span>
            <span style={{ color: '#94a3b8', fontWeight: 500, marginLeft: 8 }}>| Threat Intelligence</span>
          </div>
          {anomalyCount !== null && (
            <span className="badge badge-danger" style={{ display: 'flex', alignItems: 'center', height: '32px' }}>
              🚨 {anomalyCount} ALERTS
            </span>
          )}
          <span className="badge badge-success" style={{ display: 'flex', alignItems: 'center', height: '32px' }}>
            ✓ SECURE OFFLINE
          </span>
        </div>
      </header>
    </>
  );
}

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI('/stats');
  const { data: alerts, loading: alertsLoading } = useAPI('/anomalies?limit=50');
  const { data: clusters, loading: clustersLoading } = useAPI('/clusters');
  const { data: graphData, loading: graphLoading } = useAPI('/graph');

  const [highlightedWallet, setHighlightedWallet] = useState(null);
  const [minConfidence, setMinConfidence] = useState(0);
  const [selectedCluster, setSelectedCluster] = useState(null);

  const filteredAlerts = alerts?.filter(a => {
    if (a.confidence_score < minConfidence) return false;
    if (selectedCluster !== null && a.cluster_id !== selectedCluster) return false;
    return true;
  });

  return (
    <div className="app-shell">
      <Topbar anomalyCount={stats?.anomalies_detected ?? null} />

      <main className="main-content">
        <MetricCards stats={statsLoading ? null : stats} />
        
        <ChartsView stats={stats} clusters={clusters} />

        <div className="dashboard-grid two-column">
          <div className="card graph-card">
            <div className="card-header">
              <div className="card-title">
                <span className="card-title-icon">🕸</span>
                Entity Correlation Graph
              </div>
              <div className="graph-legend">
                <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--gov-blue)' }} /> IP Node</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--text-muted)' }} /> Transaction</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--gov-green)' }} /> Wallet</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--gov-red)' }} /> Flagged</div>
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

          <div className="card alert-panel">
            <div className="card-header">
              <div className="card-title">
                <span className="card-title-icon">🚨</span>
                Threat Watchlist & AI Insights
              </div>
              {filteredAlerts && (
                <div className="badge badge-danger">{filteredAlerts.length} FOUND</div>
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
        <span>SIH 2024 (Problem Statement 26146) — ChainWatch Prototype</span>
        <div className="footer-tech">
          <span className="tech-tag">Neo4j</span>
          <span className="tech-tag">Isolation Forest</span>
          <span className="tech-tag">FastAPI</span>
          <span className="tech-tag">React + Vite</span>
        </div>
      </footer>
    </div>
  );
}