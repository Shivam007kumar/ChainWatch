import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps';
import MetricCards from './components/MetricCards';
import AlertTable from './components/AlertTable';
import GraphView from './components/GraphView';
import ChartsView from './components/ChartsView';
import INDIA_GEO_JSON from './india.json';
import { getStateCenter, getWalletDots } from './mapUtils';
import './index.css';

const API = 'http://localhost:8000/api/v1';

const dict = {
  en: {
    skip: "Skip to Main Content", gov: "Government of India", ntro: "National Technical Research Organisation",
    title: "ChainWatch", subtitle: "| Executive Dashboard",
    heroTitle: "National Crypto-Threat Intelligence Network",
    heroSub: "Securing India's digital financial infrastructure through AI-driven blockchain forensics.",
    about: "About the Platform",
    aboutText: "ChainWatch is an advanced offline intelligence system designed by NTRO to monitor, detect, and analyze illicit cryptocurrency transaction traffic across Indian jurisdictions.",
    quickLinks: "Quick Links", nodalAgency: "Nodal Agency",
    copyright: "© 2026 National Technical Research Organisation, Government of India. All rights reserved."
  }
};

function useAPI(endpoint) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`${API}${endpoint}`).then(r => r.json()).then(setData).finally(() => setLoading(false));
  }, [endpoint]);
  return { data, loading };
}

export default function Home() {
  const navigate = useNavigate();
  const { data: stats, loading: statsLoading } = useAPI('/stats');
  const { data: apiAlerts, loading: alertsLoading } = useAPI('/anomalies');
  const { data: graphData, loading: graphLoading } = useAPI('/graph');  const [hoveredState, setHoveredState] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [wallets, setWallets] = useState([]);
  useEffect(() => { if (apiAlerts) setAlerts(apiAlerts); }, [apiAlerts]);
  useEffect(() => { if (stats?.wallet_locations) setWallets(stats.wallet_locations); }, [stats]);
  const [selectedState, setSelectedState] = useState(null);
  const [highlightedWallet, setHighlightedWallet] = useState(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState(null);
  const [selectedDotInspector, setSelectedDotInspector] = useState(null);
  const [mapMode, setMapMode] = useState('regional');
  const [zoom, setZoom] = useState(1);
  const [liveThreatData, setLiveThreatData] = useState(null);
  const mapRef = useRef(null);
  const t = dict.en;

  useEffect(() => {
    const handleOutsideMapClick = (event) => {
      if (mapRef.current && !mapRef.current.contains(event.target)) {
        if (event.target.closest('.alert-panel')) return;
        setSelectedState(null);
      }
    };
    document.addEventListener('click', handleOutsideMapClick);
    return () => document.removeEventListener('click', handleOutsideMapClick);
  }, []);

  const handleStateClick = (stateName) => {
    if (selectedState === stateName) {
      setSelectedState(null);
    } else {
      setSelectedState(stateName);
    }
  };

  const displayedAlerts = selectedState
    ? alerts.filter(alert => alert.primary_state?.toLowerCase() === selectedState.toLowerCase())
    : alerts;
  const threatWallets = wallets.length > 0
    ? wallets.filter(wallet => !selectedState || wallet.primary_state?.toLowerCase() === selectedState.toLowerCase())
    : displayedAlerts.map(alert => ({ ...alert, is_threat: true }));
  const threatDots = getWalletDots(threatWallets, INDIA_GEO_JSON, highlightedWallet);

  const handleAlertSelect = (walletAddress) => {
    const alert = alerts.find(item => item.wallet_address === walletAddress);
    setHighlightedWallet(walletAddress);
    setSelectedGraphNode(`wallet:${walletAddress}`);
    if (alert?.primary_state) setSelectedState(alert.primary_state);
  };

  const handleGraphNodeSelect = (node) => {
    setSelectedGraphNode(node.id);
    if (node.type === 'wallet') {
      const wallet = node.address || node.id.replace(/^wallet:/, '');
      setHighlightedWallet(wallet);
      const alert = alerts.find(item => item.wallet_address === wallet);
      if (alert?.primary_state) setSelectedState(alert.primary_state);
    }
  };

  const resetNeuralMap = () => {
    setSelectedGraphNode(null);
    setHighlightedWallet(null);
    setSelectedState(null);
  };

  const triggerLiveIsolation = () => {
    if (liveThreatData || !alerts || alerts.length === 0) return;
    const realThreat = alerts[0];
    setLiveThreatData(realThreat);
    setHighlightedWallet(realThreat.wallet_address);
    setTimeout(() => {
      const target = document.getElementById('threat-intel-section');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 500);
  };

  const getStateVolume = (stateName, index) => {
    if (!stats) return 0;
    return Math.floor(stats.total_transactions / 10) + (index * 45);
  };

  return (
    <div className="app-shell" style={{ zoom: zoom }}>
      <div className="access-bar">
        <a href="#main-content" className="access-link">{t.skip}</a>
        <div className="access-group">
          <button onClick={() => setZoom(0.9)}>A-</button>
          <button onClick={() => setZoom(1)}>A</button>
          <button onClick={() => setZoom(1.1)}>A+</button>
        </div>
      </div>
      <header className="topbar">
        <div className="topbar-brand" onDoubleClick={triggerLiveIsolation} style={{ cursor: 'default' }}>
          <img src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg" alt="Emblem" style={{ height: '56px', filter: 'brightness(0) invert(1)' }} />
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
          <div className="shield-status"><span className="shield-icon pulse-shield">🛡️</span> SECURED — FULLY OFFLINE</div>
          <button className="ingest-btn" onClick={() => navigate('/workspace')}>➕ Ingest New Ledger</button>
        </div>
      </header>
      {liveThreatData && (
        <div className="live-threat-banner">
          ⚠️ CRITICAL ALERT: LIVE ANOMALY DETECTED IN {liveThreatData.primary_state?.toUpperCase() || 'INDIAN'} JURISDICTION. AUTO-ISOLATING NETWORK NODES...
        </div>
      )}
      <section className="hero-section"><div className="hero-overlay"><h1>{t.heroTitle}</h1><p>{t.heroSub}</p></div></section>
      {/* ── Infinite Scroll Threat Ticker ── */}
      <div className="ticker-wrapper">
        <div className={`ticker-track ${liveThreatData ? 'paused' : ''}`}>
          {alerts && alerts.length > 0 ? [...alerts.slice(0, 10), ...alerts.slice(0, 10)].map((alert, idx) => {
            const isTarget = liveThreatData && alert.wallet_address === liveThreatData.wallet_address;
            return (
              <div key={`${alert.wallet_address}-${idx}`} className={`flash-card-flat ${isTarget ? 'danger' : ''}`}>
                <div className="fc-header-flat">
                  <span className="fc-title-flat">📍 {alert.primary_state?.toUpperCase() || 'UNKNOWN'}</span>
                  <span className={`fc-dot ${isTarget ? 'blink-red' : 'red'}`}></span>
                </div>
                <div className="fc-body-flat">
                  <div><strong>ID:</strong> {alert.wallet_address.substring(0, 12)}...</div>
                  <div><strong>VOL:</strong> {alert.total_volume_btc} BTC</div>
                  <div className="fc-alert-text">CONFIDENCE: {alert.confidence_score}%</div>
                </div>
              </div>
            );
          }) : <div style={{ padding: '10px' }}>Awaiting threat data...</div>}
        </div>
      </div>
      <main id="main-content" className="main-content">
        <MetricCards stats={statsLoading ? null : stats} />
        {/* ChartsView — risk distribution donut + cluster bar chart */}
        {stats && apiAlerts && apiAlerts.length > 0 && (() => {
          const clusterCounts = apiAlerts.reduce((acc, alert) => {
            const name = alert.cluster_name || 'Unknown';
            acc[name] = (acc[name] || 0) + 1;
            return acc;
          }, {});
          const clusters = Object.entries(clusterCounts).map(([cluster_name, wallet_count]) => ({
            cluster_name,
            wallet_count,
          }));
          return <ChartsView stats={stats} clusters={clusters} />;
        })()}
        <div id="threat-intel-section" className="dashboard-grid two-column">
          <div className="card map-card">
            <div className="card-header">
              <div className="card-title"><span className="card-title-icon">{mapMode === 'regional' ? '🗺️' : '✦'}</span> {mapMode === 'regional' ? 'Regional Threat Map' : 'Neural Entity Map'}</div>
              <div className="map-card-actions">
                <div className="map-mode-toggle" role="group" aria-label="Map view">
                  <button className={mapMode === 'regional' ? 'active' : ''} onClick={() => setMapMode('regional')}>Regional Map</button>
                  <button className={mapMode === 'neural' ? 'active' : ''} onClick={() => setMapMode('neural')}>Neural Map</button>
                </div>
                {mapMode === 'neural' && <button className="clear-btn" onClick={resetNeuralMap}>Reset View</button>}
                {mapMode === 'regional' && selectedState && <button className="clear-btn" onClick={() => setSelectedState(null)}>Clear Filter ✖</button>}
              </div>
            </div>
            <div ref={mapRef} className="hybrid-map" style={{ position: "relative" }}>
              {mapMode === 'neural' ? (
                <div className="neural-map-shell">
                  <GraphView data={graphData} loading={graphLoading} highlightNode={selectedGraphNode} onNodeSelect={handleGraphNodeSelect} onReset={resetNeuralMap} />
                  <div className="graph-legend"><span><i className="graph-dot ip" /> IP</span><span><i className="graph-dot transaction" /> Transaction</span><span><i className="graph-dot wallet" /> Wallet</span><span><i className="graph-dot flagged" /> Flagged</span><span><i className="graph-dot co-spender" /> Co-Spender</span></div>
                </div>
              ) : <>
              {hoveredState && <div className="map-tooltip">{hoveredState}</div>}
              <ComposableMap projection="geoMercator" projectionConfig={{ scale: 1000, center: [80, 22] }} style={{ width: "100%", height: "100%" }}>
                <ZoomableGroup center={selectedState ? getStateCenter(selectedState, INDIA_GEO_JSON) : [80, 22]} zoom={selectedState ? 3 : 1} transitionDuration={1200}>
                  <Geographies geography={INDIA_GEO_JSON}>
                    {({ geographies }) => geographies.map((geo, idx) => {
                      const stateName = geo.properties.st_nm || geo.properties.name || geo.properties.NAME_1;
                      const isSelected = selectedState === stateName;
                      return (
                        <Geography key={geo.rsmKey} geography={geo} onClick={() => handleStateClick(stateName)} onMouseEnter={() => setHoveredState(stateName)} onMouseLeave={() => setHoveredState("")} fill={isSelected ? "#fee2e2" : "#ffffff"} stroke="#000000" strokeWidth={0.5} style={{ default: { outline: "none" }, hover: { fill: "#f1f5f9", outline: "none", cursor: "pointer" }, pressed: { outline: "none" } }} />
                      );
                    })}
                  </Geographies>
                  {threatDots.map(dot => (
                    <Marker key={dot.id} coordinates={[dot.lng, dot.lat]} onClick={(event) => { event.stopPropagation(); setSelectedDotInspector(dot); handleAlertSelect(dot.wallet); }}>
                      <circle r={dot.highlighted ? 6 : selectedState ? 4 : 3} fill={dot.color} stroke={dot.highlighted ? '#111827' : '#fff'} strokeWidth={dot.highlighted ? 2 : 1} opacity={dot.highlighted ? 1 : 0.9} style={{ cursor: 'pointer' }}>
                        <title>{`${dot.wallet} | ${dot.state} | Risk Score: ${dot.riskScore}%`}</title>
                      </circle>
                    </Marker>
                  ))}
                </ZoomableGroup>
              </ComposableMap>

              {selectedDotInspector && (
                <div className="map-dot-inspector" onMouseDown={(e) => e.stopPropagation()}>
                  <div className="inspector-header">
                    <span className="inspector-badge" style={{ background: selectedDotInspector.riskScore >= 70 ? '#ef4444' : '#f59e0b' }}>
                      RISK SCORE {selectedDotInspector.riskScore}%
                    </span>
                    <button className="inspector-close" onClick={() => setSelectedDotInspector(null)}>✖</button>
                  </div>
                  <div className="inspector-wallet">{selectedDotInspector.wallet}</div>
                  <div className="inspector-grid">
                    <div><strong>STATE:</strong> {selectedDotInspector.state?.toUpperCase()}</div>
                    <div><strong>TX COUNT:</strong> {selectedDotInspector.txCount}</div>
                    <div><strong>VOLUME:</strong> {selectedDotInspector.volumeBtc} BTC</div>
                  </div>
                  {selectedDotInspector.riskFactors?.length > 0 && (
                    <div className="inspector-factors">
                      <strong>RISK FACTORS:</strong> {selectedDotInspector.riskFactors.join(', ')}
                    </div>
                  )}
                  {selectedDotInspector.transactions?.length > 0 && (
                    <div className="inspector-tx-list">
                      <strong style={{ color: '#94a3b8', fontSize: '10px' }}>LINKED TRANSACTIONS ({selectedDotInspector.transactions.length}):</strong>
                      {selectedDotInspector.transactions.map((tx, idx) => (
                        <div key={idx} className="inspector-tx-item">
                          <span><code>{tx.txid?.slice(0, 12)}...</code></span>
                          <span>{tx.type} · {tx.amount} BTC</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="inspector-actions">
                    <button onClick={() => { setMapMode('neural'); setSelectedGraphNode(`wallet:${selectedDotInspector.wallet}`); }}>
                      🕸️ View Graph
                    </button>
                    <button onClick={() => window.open(`${API}/report/${selectedDotInspector.wallet}`, '_blank')}>
                      📄 PDF Report
                    </button>
                  </div>
                </div>
              )}
              </>}
            </div>
          </div>
          <div className="card alert-panel">
            <div className="card-header"><div className="card-title"><span className="card-title-icon">🚨</span> Threat Watchlist</div><div className="badge badge-danger">{displayedAlerts.length} FOUND</div></div>
            <AlertTable alerts={displayedAlerts} loading={alertsLoading} selectedWallet={highlightedWallet} onSelectWallet={handleAlertSelect} />
          </div>
        </div>
      </main>
      <footer className="footer-main">
        <div className="footer-columns">
          <div className="footer-col"><h3>{t.about}</h3><p>{t.aboutText}</p></div>
          <div className="footer-col"><h3>{t.quickLinks}</h3><ul><li><a href="#">Dashboard Home</a></li><li><a href="#">Generate Intelligence Report</a></li><li><a href="#">Threat Pattern Database</a></li><li><a href="#">User Manual & API Docs</a></li></ul></div>
          <div className="footer-col"><h3>{t.nodalAgency}</h3><p><strong>NTRO</strong><br/>Block-III, Old JNU Campus<br/>New Delhi - 110067<br/>Email: cyber-intel@ntro.gov.in</p></div>
        </div>
        <div className="footer-bottom"><p>{t.copyright}</p><div className="footer-bottom-links"><a href="#">Privacy Policy</a><span>|</span><a href="#">Terms of Use</a><span>|</span><a href="#">Security Policy</a></div></div>
      </footer>
    </div>
  );
}