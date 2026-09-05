import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps';
import INDIA_GEO_JSON from './india.json';
import { getStateCenter, getWalletDots } from './mapUtils';
import './index.css';

const API = 'http://localhost:8000/api/v1';

export default function Workspace() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState(["[SYSTEM] Workspace initialized. Awaiting ledger ingest..."]);
  const [alerts, setAlerts] = useState([]);
  const [selectedState, setSelectedState] = useState(null);
  const [hoveredState, setHoveredState] = useState("");
  const mapRef = useRef(null);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    const handleOutsideMapClick = (event) => {
      if (mapRef.current && !mapRef.current.contains(event.target)) {
        setSelectedState(null);
      }
    };
    document.addEventListener('click', handleOutsideMapClick);
    return () => document.removeEventListener('click', handleOutsideMapClick);
  }, []);

  const handleFileChange = (event) => {
    if (event.target.files && event.target.files[0]) setFile(event.target.files[0]);
  };

  const handleStateClick = (stateName) => {
    if (selectedState === stateName) {
      setSelectedState(null);
    } else {
      setSelectedState(stateName);
    }
  };

  const fetchAlerts = async () => {
    const response = await fetch(`${API}/anomalies`);
    const data = await response.json();
    setAlerts(data);
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsProcessing(true);
    setLogs(prev => [...prev, `[USER] Initiating ingest for ${file.name}...`]);
    setTimeout(() => setLogs(prev => [...prev, "[ENGINE] Parsing CSV and extracting network graphs..."]), 1000);
    setTimeout(() => setLogs(prev => [...prev, "[ENGINE] Resolving GeoIPs and ASN footprints..."]), 2500);
    setTimeout(() => setLogs(prev => [...prev, "[AI] Running Isolation Forest across 10,000 vectors..."]), 4000);
    setTimeout(() => setLogs(prev => [...prev, "[AI] Executing K-Means behavioral clustering..."]), 5500);

    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API}/ingest`, { method: 'POST', body: formData });
      const result = await response.json();
      setTimeout(() => {
        setLogs(prev => [...prev, `[SUCCESS] Analysis complete. Found ${result.anomalies_found} threats.`]);
        fetchAlerts();
        setIsProcessing(false);
      }, 7000);
    } catch (error) {
      setTimeout(() => {
        setLogs(prev => [...prev, "[ERROR] Connection to Core Engine failed."]);
        setIsProcessing(false);
      }, 7000);
    }
  };

  const stateSuspects = selectedState
    ? alerts.filter(alert => alert.primary_state?.toLowerCase() === selectedState.toLowerCase())
    : alerts;
  const threatDots = getWalletDots(stateSuspects.map(alert => ({ ...alert, is_threat: true })), INDIA_GEO_JSON);
  const topStates = Object.entries(alerts.reduce((counts, alert) => {
    const stateName = alert.primary_state || 'Unknown';
    counts[stateName] = (counts[stateName] || 0) + 1;
    return counts;
  }, {})).sort(([, firstCount], [, secondCount]) => secondCount - firstCount).slice(0, 3);

  return (
    <div className="workspace-layout">
      <header className="topbar">
        <div className="ws-brand">
          <div className="ws-back" onClick={() => navigate('/')}>← BACK TO DASHBOARD</div>
          <div className="brand-titles"><div className="brand-name" style={{ fontSize: '16px' }}>NTRO ANALYST WORKSPACE</div></div>
        </div>
        <div className="topbar-actions"><div className="shield-status"><span className="shield-icon">🛡️</span> SECURED — FULLY OFFLINE</div></div>
      </header>

      <div className="workspace-body">
        <div className="ws-pane ws-left">
          <h3 className="ws-pane-title">1. DATA INGESTION</h3>
          <div className="upload-zone">
            <input type="file" accept=".csv" onChange={handleFileChange} id="file-upload" style={{ display: 'none' }} />
            <label htmlFor="file-upload" className="upload-label">
              {file ? file.name : "Select CSV Ledger"}
            </label>
            <button className={`ws-btn ${!file || isProcessing ? 'disabled' : ''}`} onClick={handleUpload} disabled={!file || isProcessing}>
              {isProcessing ? "ANALYZING..." : "RUN AI PIPELINE"}
            </button>
          </div>
          <div className="ws-instructions">
            <p><strong>INSTRUCTIONS:</strong></p>
            <p>1. Generate ledger via Streamlit.</p>
            <p>2. Upload <code>ledger.csv</code> here.</p>
            <p>3. AI will extract regional anomalies.</p>
          </div>
        </div>

        <div className="ws-pane ws-center">
          <div ref={mapRef} className="ws-map-container" style={{ position: "relative" }}>
            <h3 className="ws-pane-title" style={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}>2. GEOSPATIAL ISOLATION</h3>
            {selectedState && <div className="state-badge">TARGET: {selectedState.toUpperCase()}</div>}
            {hoveredState && <div className="map-tooltip">{hoveredState}</div>}
            {topStates.length > 0 && (
              <div className="top-states-signator">
                <span className="top-states-pulse">●</span> TOP ANOMALY STATES
                <div className="top-states-list">
                  {topStates.map(([stateName, count]) => <span key={stateName}>{stateName.toUpperCase()} ({count})</span>)}
                </div>
              </div>
            )}
            <ComposableMap projection="geoMercator" projectionConfig={{ scale: 1000, center: [80, 22] }} style={{ width: "100%", height: "100%" }}>
              <ZoomableGroup center={selectedState ? getStateCenter(selectedState, INDIA_GEO_JSON) : [80, 22]} zoom={selectedState ? 3 : 1} transitionDuration={800}>
                <Geographies geography={INDIA_GEO_JSON}>
                  {({ geographies }) => geographies.map((geo) => {
                    const stateName = geo.properties.st_nm || geo.properties.name || geo.properties.NAME_1;
                    const isSelected = selectedState === stateName;
                    return (
                      <Geography key={geo.rsmKey} geography={geo} onClick={() => handleStateClick(stateName)} onMouseEnter={() => setHoveredState(stateName)} onMouseLeave={() => setHoveredState("")} fill={isSelected ? "#fee2e2" : "#ffffff"} stroke="#000000" strokeWidth={0.5} style={{ default: { outline: "none" }, hover: { fill: "#f1f5f9", outline: "none", cursor: "pointer" }, pressed: { outline: "none" } }} />
                    );
                  })}
                </Geographies>
                {threatDots.map(dot => (
                  <Marker key={dot.id} coordinates={[dot.lng, dot.lat]}>
                    <circle r={selectedState ? 3 : 2.5} fill={dot.color} stroke="#fff" strokeWidth={0.7}>
                      <title>{`${dot.wallet} | ${dot.state} | ${dot.confidence}% confidence`}</title>
                    </circle>
                  </Marker>
                ))}
              </ZoomableGroup>
            </ComposableMap>
          </div>
          <div className="ws-terminal">
            <h3 className="ws-pane-title" style={{ color: '#94a3b8' }}>ENGINE LOGS</h3>
            <div className="terminal-output">
              {logs.map((log, index) => <div key={index} className={log.includes("ERROR") ? "log-err" : log.includes("SUCCESS") ? "log-succ" : "log-info"}>{log}</div>)}
              <div ref={terminalEndRef} />
            </div>
          </div>
        </div>

        <div className="ws-pane ws-right">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 className="ws-pane-title" style={{ margin: 0 }}>3. REGIONAL SUSPECTS</h3>
            {selectedState && <button className="clear-btn" onClick={() => setSelectedState(null)}>Clear Filter</button>}
          </div>
          <div className="ws-suspect-list">
            {stateSuspects.length === 0 ? (
              <div className="ws-empty">No anomalous activity detected.</div>
            ) : (
              stateSuspects.map((suspect, index) => (
                <div key={index} className="alert-row-flat">
                  <div className="alert-header-flat"><span className="alert-rank-flat">FILE #{index + 1}</span><span className="alert-score-flat">{suspect.confidence_score}%</span></div>
                  <div className="alert-wallet-flat">{suspect.wallet_address}</div>
                  <div className="alert-details-flat"><strong>VOL:</strong> {suspect.total_volume_btc} BTC <br /><strong>ISP:</strong> {suspect.isp} <br /><button className="report-btn" onClick={() => window.open(`${API}/report/${suspect.wallet_address}`, '_blank')}>📄 Generate PDF</button></div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}