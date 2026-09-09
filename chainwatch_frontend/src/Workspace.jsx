import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps';
import GraphView from './components/GraphView';
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
  const [graphData, setGraphData] = useState(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [selectedState, setSelectedState] = useState(null);
  const [hoveredState, setHoveredState] = useState("");
  const [mapMode, setMapMode] = useState('regional');
  const [selectedGraphNode, setSelectedGraphNode] = useState(null);
  const mapRef = useRef(null);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    fetch(`${API}/graph`).then(response => response.json()).then(setGraphData).finally(() => setGraphLoading(false));
  }, []);

  useEffect(() => {
    const handleOutsideMapClick = (event) => {
      if (mapRef.current && !mapRef.current.contains(event.target)) {
        if (event.target.closest('.ws-right')) return;
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
    const graphResponse = await fetch(`${API}/graph`);
    setGraphData(await graphResponse.json());
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
  const [highlightedWallet, setHighlightedWallet] = useState(null);
  const threatDots = getWalletDots(stateSuspects.map(alert => ({ ...alert, is_threat: true })), INDIA_GEO_JSON, highlightedWallet);

  const handleAlertSelect = (suspect) => {
    setHighlightedWallet(suspect.wallet_address);
    setSelectedGraphNode(`wallet:${suspect.wallet_address}`);
    if (suspect.primary_state) setSelectedState(suspect.primary_state);
  };

  const handleGraphNodeSelect = (node) => {
    setSelectedGraphNode(node.id);
    if (node.type === 'wallet') {
      const wallet = node.address || node.id.replace(/^wallet:/, '');
      setHighlightedWallet(wallet);
      const suspect = alerts.find(item => item.wallet_address === wallet);
      if (suspect?.primary_state) setSelectedState(suspect.primary_state);
    }
  };

  const resetNeuralMap = () => {
    setSelectedGraphNode(null);
    setHighlightedWallet(null);
    setSelectedState(null);
  };
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
            <div className="workspace-map-toolbar">
              <h3 className="ws-pane-title">2. {mapMode === 'regional' ? 'GEOSPATIAL ISOLATION' : 'NEURAL ENTITY MAP'}</h3>
              <div className="map-card-actions">
                <div className="map-mode-toggle" role="group" aria-label="Map view">
                  <button className={mapMode === 'regional' ? 'active' : ''} onClick={() => setMapMode('regional')}>Regional Map</button>
                  <button className={mapMode === 'neural' ? 'active' : ''} onClick={() => setMapMode('neural')}>Neural Map</button>
                </div>
                {mapMode === 'neural' && <button className="clear-btn" onClick={resetNeuralMap}>Reset View</button>}
                {mapMode === 'regional' && selectedState && <button className="clear-btn" onClick={() => setSelectedState(null)}>Clear Filter</button>}
              </div>
            </div>
            {mapMode === 'neural' ? (
              <div className="neural-map-shell">
                <GraphView data={graphData} loading={graphLoading} highlightNode={selectedGraphNode} onNodeSelect={handleGraphNodeSelect} onReset={resetNeuralMap} />
                <div className="graph-legend"><span><i className="graph-dot ip" /> IP</span><span><i className="graph-dot transaction" /> Transaction</span><span><i className="graph-dot wallet" /> Wallet</span><span><i className="graph-dot flagged" /> Flagged</span></div>
              </div>
            ) : <>
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
                    <Marker key={dot.id} coordinates={[dot.lng, dot.lat]} onClick={(event) => { event.stopPropagation(); handleAlertSelect({ wallet_address: dot.wallet, primary_state: dot.state }); }}>
                    <circle r={dot.highlighted ? 5 : selectedState ? 3 : 2.5} fill={dot.color} stroke={dot.highlighted ? '#111827' : '#fff'} strokeWidth={dot.highlighted ? 1.5 : 0.7} opacity={dot.highlighted ? 1 : 0.85}>
                      <title>{`${dot.wallet} | ${dot.state} | ${dot.confidence}% confidence`}</title>
                    </circle>
                  </Marker>
                ))}
              </ZoomableGroup>
            </ComposableMap>
            </>}
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
                <div key={index} className={`alert-row-flat ${highlightedWallet === suspect.wallet_address ? 'selected' : ''}`} onClick={() => handleAlertSelect(suspect)}>
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