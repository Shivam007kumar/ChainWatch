import { useState, useEffect } from 'react';
import MetricCards from './components/MetricCards';
import AlertTable from './components/AlertTable';
import ChartsView from './components/ChartsView';
import GraphView from './components/GraphView';
import './index.css';

const API = 'http://localhost:8000/api/v1';

// Simple Dictionary for Language Toggle
const dict = {
  en: {
    skip: "Skip to Main Content",
    gov: "Government of India",
    ntro: "National Technical Research Organisation",
    title: "ChainWatch",
    subtitle: "| Threat Intelligence",
    heroTitle: "National Crypto-Threat Intelligence Network",
    heroSub: "Securing India's digital financial infrastructure through AI-driven blockchain forensics and anomaly detection.",
    alerts: "ALERTS",
    secure: "SECURE OFFLINE",
    about: "About the Platform",
    aboutText: "ChainWatch is an advanced AI-powered offline intelligence system designed by NTRO to monitor, detect, and analyze illicit cryptocurrency transaction traffic.",
    quickLinks: "Quick Links",
    nodalAgency: "Nodal Agency",
    copyright: "© 2026 National Technical Research Organisation, Government of India. All rights reserved."
  },
  hi: {
    skip: "मुख्य सामग्री पर जाएं",
    gov: "भारत सरकार",
    ntro: "राष्ट्रीय तकनीकी अनुसंधान संगठन",
    title: "चेनवाच",
    subtitle: "| खतरा खुफिया",
    heroTitle: "राष्ट्रीय क्रिप्टो-खतरा खुफिया नेटवर्क",
    heroSub: "एआई-संचालित ब्लॉकचेन फोरेंसिक और विसंगति पहचान के माध्यम से भारत के डिजिटल वित्तीय बुनियादी ढांचे को सुरक्षित करना।",
    alerts: "अलर्ट",
    secure: "सुरक्षित ऑफ़लाइन",
    about: "मंच के बारे में",
    aboutText: "चेनवाच एक उन्नत एआई-संचालित ऑफ़लाइन खुफिया प्रणाली है जिसे अवैध क्रिप्टोकरेंसी लेनदेन यातायात की निगरानी, पता लगाने और विश्लेषण करने के लिए डिज़ाइन किया गया है।",
    quickLinks: "त्वरित लिंक",
    nodalAgency: "नोडल एजेंसी",
    copyright: "© 2026 राष्ट्रीय तकनीकी अनुसंधान संगठन, भारत सरकार। सर्वाधिकार सुरक्षित।"
  }
};

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

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI('/stats');
  const { data: alerts, loading: alertsLoading } = useAPI('/anomalies?limit=50');
  const { data: clusters, loading: clustersLoading } = useAPI('/clusters');
  const { data: graphData, loading: graphLoading } = useAPI('/graph');

  const [highlightedWallet, setHighlightedWallet] = useState(null);
  const [minConfidence, setMinConfidence] = useState(0);
  const [selectedCluster, setSelectedCluster] = useState(null);

  // Accessibility States
  const [lang, setLang] = useState('en');
  const [zoom, setZoom] = useState(1);
  const t = dict[lang]; // Translation helper

  const filteredAlerts = alerts?.filter(a => {
    if (a.confidence_score < minConfidence) return false;
    if (selectedCluster !== null && a.cluster_id !== selectedCluster) return false;
    return true;
  });

  return (
    <div className="app-shell" style={{ zoom: zoom }}>
      
      {/* ── Accessibility Bar ── */}
      <div className="access-bar">
        <a href="#main-content" className="access-link">{t.skip}</a>
        <div className="access-group">
          <button onClick={() => setZoom(0.9)}>A-</button>
          <button onClick={() => setZoom(1)}>A</button>
          <button onClick={() => setZoom(1.1)}>A+</button>
        </div>
        <div className="access-group">
          <button onClick={() => setLang('en')} className={lang === 'en' ? 'active' : ''}>English</button>
          <span>|</span>
          <button onClick={() => setLang('hi')} className={lang === 'hi' ? 'active' : ''}>हिन्दी</button>
        </div>
      </div>
      
      {/* ── Dark Blue Government Header ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <img 
            src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg" 
            alt="Satyameva Jayate" 
            style={{ height: '56px', filter: 'brightness(0) invert(1)' }} 
          />
          <div className="brand-titles">
            <div className="brand-goi">{t.gov}</div>
            <div className="brand-name">{t.ntro}</div>
          </div>
        </div>

        <div className="topbar-actions">
          <div className="system-title">
            <span style={{ color: '#ffffff', fontWeight: 800 }}>{t.title}</span>
            <span style={{ color: '#94a3b8', fontWeight: 500, marginLeft: 8 }}>{t.subtitle}</span>
          </div>
          {stats?.anomalies_detected && (
            <span className="badge badge-danger">
              🚨 {stats.anomalies_detected} {t.alerts}
            </span>
          )}
          <span className="badge badge-success">
            ✓ {t.secure}
          </span>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="hero-section">
        <div className="hero-overlay">
          <h1>{t.heroTitle}</h1>
          <p>{t.heroSub}</p>
        </div>
      </section>

      {/* ── Main Dashboard Content ── */}
      <main id="main-content" className="main-content">
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

      {/* ── Thick Official Footer ── */}
      <footer className="footer-main">
        <div className="footer-columns">
          <div className="footer-col">
            <h3>{t.about}</h3>
            <p>{t.aboutText}</p>
          </div>
          <div className="footer-col">
            <h3>{t.quickLinks}</h3>
            <ul>
              <li><a href="#">Dashboard Home</a></li>
              <li><a href="#">Generate Intelligence Report</a></li>
              <li><a href="#">Threat Pattern Database</a></li>
              <li><a href="https://github.com/Shivam007kumar/ChainWatch" target="_blank" rel="noopener noreferrer">User Manual & API Docs</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h3>{t.nodalAgency}</h3>
            <p>
              <strong>National Technical Research Organisation</strong><br/>
              Block-III, Old JNU Campus<br/>
              New Delhi - 110067<br/>
              Email: cyber-intel@ntro.gov.in
            </p>
          </div>
        </div>
        <div className="footer-bottom">
          <p>{t.copyright}</p>
          <div className="footer-bottom-links">
            <a href="https://github.com/Shivam007kumar/ChainWatch" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
            <span>|</span>
            <a href="https://github.com/Shivam007kumar/ChainWatch" target="_blank" rel="noopener noreferrer">Terms of Use</a>
            <span>|</span>
            <a href="https://github.com/Shivam007kumar/ChainWatch" target="_blank" rel="noopener noreferrer">Security Policy</a>
          </div>
        </div>
      </footer>
    </div>
  );
}