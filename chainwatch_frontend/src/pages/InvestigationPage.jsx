/**
 * InvestigationPage.jsx
 * ─────────────────────
 * Primary investigation workstation.
 * Routes: /investigate  and  /investigate/:address
 *
 * Graph data source: GET /investigations/wallet/{address}/graph (frozen)
 * Inspector panels: filled in P4b–P4f
 */
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { getHealth }          from '../api/health';
import { getWalletGraph }     from '../api/investigations';
import InvestigationGraph     from '../components/InvestigationGraph';
import InspectorPanel         from '../components/InspectorPanel';
import CwNav                  from '../components/CwNav';

// ── Empty state shown when no wallet address is in the URL ─────────────────
function InvestigateEmptyState({ navigate }) {
  const [query, setQuery] = useState('');
  const handleSearch = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    // If it looks like a wallet address (long alphanumeric), investigate directly
    if (q.length >= 20 && /^[a-zA-Z0-9]+$/.test(q)) {
      navigate(`/investigate/${encodeURIComponent(q)}`);
    } else {
      // Otherwise send to global search
      navigate(`/search?q=${encodeURIComponent(q)}`);
    }
  };

  return (
    <div style={{
      position: 'absolute', inset: 0,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '32px 24px', background: 'radial-gradient(circle at center, #ffffff 0%, #f2f4f7 100%)',
    }}>
      <div style={{ fontSize: 32, marginBottom: 16, opacity: 0.25 }}>✦</div>
      <div style={{ fontSize: 15, fontWeight: 800, color: '#0f172a', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        Neural Investigation Map
      </div>
      <div style={{ fontSize: 13, color: '#64748b', marginBottom: 28, textAlign: 'center', maxWidth: 360, lineHeight: 1.65 }}>
        Enter a wallet address to open an investigation, or browse Alerts and Search to find a starting point.
      </div>

      {/* Wallet / TXID lookup */}
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, width: '100%', maxWidth: 420, marginBottom: 20 }}>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Wallet address or search term…"
          style={{
            flex: 1,
            padding: '9px 14px',
            border: '1px solid #94a3b8',
            borderRadius: 2,
            fontSize: 13,
            fontFamily: 'var(--mono)',
            color: '#0f172a',
            background: '#ffffff',
            outline: 'none',
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--gov-blue)'; }}
          onBlur={e  => { e.target.style.borderColor = '#94a3b8'; }}
        />
        <button
          type="submit"
          style={{
            padding: '9px 18px',
            background: 'var(--gov-blue)', color: '#fff',
            border: 'none', borderRadius: 2,
            fontSize: 12, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
            textTransform: 'uppercase', letterSpacing: '0.04em',
            flexShrink: 0,
          }}
        >
          Go
        </button>
      </form>

      {/* Quick-access CTAs */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
        <button
          onClick={() => navigate('/alerts')}
          style={{
            padding: '7px 16px',
            background: '#f8fafc', color: '#475569',
            border: '1px solid #cbd5e1', borderRadius: 2,
            fontSize: 11, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gov-blue)'; e.currentTarget.style.color = 'var(--gov-blue)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = '#cbd5e1'; e.currentTarget.style.color = '#475569'; }}
        >
          🚨 Browse Alerts
        </button>
        <button
          onClick={() => navigate('/search')}
          style={{
            padding: '7px 16px',
            background: '#f8fafc', color: '#475569',
            border: '1px solid #cbd5e1', borderRadius: 2,
            fontSize: 11, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gov-blue)'; e.currentTarget.style.color = 'var(--gov-blue)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = '#cbd5e1'; e.currentTarget.style.color = '#475569'; }}
        >
          🔍 Search Entities
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          style={{
            padding: '7px 16px',
            background: '#f8fafc', color: '#475569',
            border: '1px solid #cbd5e1', borderRadius: 2,
            fontSize: 11, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gov-blue)'; e.currentTarget.style.color = 'var(--gov-blue)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = '#cbd5e1'; e.currentTarget.style.color = '#475569'; }}
        >
          📊 Dashboard
        </button>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function InvestigationPage() {
  const navigate           = useNavigate();
  const { address }        = useParams();
  const [searchParams]     = useSearchParams();

  // ?tx=<txid> or ?ip=<ip> — direct deep-link from Search results.
  // Produces a node shape that InspectorPanel already understands (P4c / P4d).
  // This is a pure derivation — no extra state, no fake graph nodes.
  const queryNode = (() => {
    const tx = searchParams.get('tx');
    if (tx) return { type: 'transaction', id: `tx:${tx}`, label: tx };
    const ip = searchParams.get('ip');
    if (ip) return { type: 'ip', id: `ip:${ip}`, ip };
    return null;
  })();

  // Backend status
  const [status, setStatus] = useState('checking');

  // Graph fetch state
  const [graphData,    setGraphData]    = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError,   setGraphError]   = useState(null);

  // Toolbar state (P3a)
  const [hops,      setHops]      = useState(2);
  const [direction, setDirection] = useState('both');

  // Branch management state (P3b)
  const [isolatedBranch, setIsolatedBranch] = useState(null); // Set | null
  const [hiddenNodes,    setHiddenNodes]    = useState(null); // Set | null

  // Selected entity state (P3c)
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedLink, setSelectedLink] = useState(null);
  const [selectedPath, setSelectedPath] = useState(null); // { source, target }

  // Graph metrics (P3d)
  const [metrics, setMetrics] = useState({ nodeCount: 0, txCount: 0, hops: 2, totalBtc: 0 });

  // ── Health check ─────────────────────────────────────────────────────────
  useEffect(() => {
    getHealth()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('err'));
  }, []);

  // ── Fetch graph when address / hops / direction changes ──────────────────
  useEffect(() => {
    if (!address) { setGraphData(null); return; }

    setGraphLoading(true);
    setGraphError(null);
    setSelectedNode(null);
    setSelectedLink(null);
    setSelectedPath(null);
    setIsolatedBranch(null);
    setHiddenNodes(null);

    getWalletGraph(address, hops, direction)
      .then(data => { setGraphData(data); setGraphLoading(false); })
      .catch(err  => { setGraphError(err.detail ?? err.message ?? 'Graph load failed.'); setGraphLoading(false); });
  }, [address, hops, direction]);

  // ── Metrics callback from graph ───────────────────────────────────────────
  const handleMetrics = useCallback((m) => setMetrics(m), []);

  // ── Node selection ────────────────────────────────────────────────────────
  const handleSelectNode = useCallback((node) => {
    setSelectedNode(node);
    setSelectedLink(null);
    // If we selected a new wallet node, update selectedPath to center + that node
    if (node && node.type === 'wallet' && address) {
      const centerId = `wallet:${address}`;
      if (node.id !== centerId) {
        setSelectedPath({ source: centerId, target: node.id });
      } else {
        setSelectedPath(null);
      }
    } else {
      setSelectedPath(null);
    }
  }, [address]);

  // ── Link/arc selection (P3c) ──────────────────────────────────────────────
  const handleSelectLink = useCallback((link) => {
    setSelectedLink(link);
    setSelectedNode(null);
    if (link) {
      const src = link.source?.id ?? link.source;
      const tgt = link.target?.id ?? link.target;
      setSelectedPath({ source: src, target: tgt });
    } else {
      setSelectedPath(null);
    }
  }, []);

  // ── Branch management (P3b) ───────────────────────────────────────────────
  const handleExpand = () => {
    // Expand: clear isolation to show all nodes
    setIsolatedBranch(null);
    setHiddenNodes(null);
  };

  const handleCollapse = () => {
    // Collapse: show only the center wallet and its direct neighbors (hops=1 logic)
    if (!graphData?.nodes) return;
    const centerId = `wallet:${address}`;
    const directLinks = (graphData.edges ?? graphData.links ?? []).filter(l => {
      const src = l.source?.id ?? l.source;
      const tgt = l.target?.id ?? l.target;
      return src === centerId || tgt === centerId;
    });
    const neighborIds = new Set([centerId]);
    directLinks.forEach(l => {
      neighborIds.add(l.source?.id ?? l.source);
      neighborIds.add(l.target?.id ?? l.target);
    });
    setIsolatedBranch(neighborIds);
  };

  const handleIsolate = () => {
    // Isolate: show only selectedNode + its immediate neighbors
    if (!selectedNode || !graphData) return;
    const links = graphData.edges ?? graphData.links ?? [];
    const keep  = new Set([selectedNode.id]);
    links.forEach(l => {
      const src = l.source?.id ?? l.source;
      const tgt = l.target?.id ?? l.target;
      if (src === selectedNode.id) keep.add(tgt);
      if (tgt === selectedNode.id) keep.add(src);
    });
    setIsolatedBranch(keep);
  };

  const handleHideUnrelated = () => {
    // Hide: nodes not connected to selectedNode
    if (!selectedNode || !graphData) return;
    const links = graphData.edges ?? graphData.links ?? [];
    const related = new Set([selectedNode.id]);
    links.forEach(l => {
      const src = l.source?.id ?? l.source;
      const tgt = l.target?.id ?? l.target;
      if (src === selectedNode.id) related.add(tgt);
      if (tgt === selectedNode.id) related.add(src);
    });
    const allIds  = new Set(graphData.nodes.map(n => n.id));
    const hidden  = new Set([...allIds].filter(id => !related.has(id)));
    setHiddenNodes(hidden);
  };

  const handleReset = () => {
    setIsolatedBranch(null);
    setHiddenNodes(null);
    setSelectedNode(null);
    setSelectedLink(null);
    setSelectedPath(null);
  };

  // ── Hop count — N means max (5) ───────────────────────────────────────────
  const applyHops = (h) => {
    setHops(h === 'N' ? 5 : Number(h));
  };

  // ── Inspector: handled by InspectorPanel component ───────────────────────
  const handleNavigate = useCallback((addr) => {
    navigate(`/investigate/${addr}`);
  }, [navigate]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#f8fafc' }}>

      <CwNav status={status} />

      <div className="inv-layout">

        {/* ── Graph area ── */}
        <div className="inv-graph-area">

          {/* ── Toolbar (P3a + P3b) ── */}
          <div className="inv-toolbar">

            {/* Address context */}
            {address && (
              <>
                <span className="inv-toolbar__label" style={{ color: 'var(--gov-blue)', fontFamily: 'var(--mono)' }}>
                  {address.slice(0, 14)}…
                </span>
                <div className="inv-toolbar__sep" />
              </>
            )}

            {/* Hops */}
            <span className="inv-toolbar__label">Hops</span>
            <div style={{ display: 'flex', gap: 2 }}>
              {[1, 2, 3, 'N'].map(h => (
                <button
                  key={h}
                  className={`inv-btn ${(h === 'N' ? hops === 5 : hops === h) ? 'active' : ''}`}
                  onClick={() => applyHops(h)}
                >
                  {h}
                </button>
              ))}
            </div>

            <div className="inv-toolbar__sep" />

            {/* Direction */}
            <span className="inv-toolbar__label">Direction</span>
            <div style={{ display: 'flex', gap: 2 }}>
              {[
                { key: 'backward', label: '← Back' },
                { key: 'both',     label: 'Both'    },
                { key: 'forward',  label: 'Forward →' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  className={`inv-btn ${direction === key ? 'active' : ''}`}
                  onClick={() => setDirection(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="inv-toolbar__sep" />

            {/* Branch management */}
            <span className="inv-toolbar__label">Branch</span>
            <div style={{ display: 'flex', gap: 2 }}>
              <button className="inv-btn" onClick={handleExpand}    title="Show all nodes">Expand</button>
              <button className="inv-btn" onClick={handleCollapse}  title="Collapse to center + 1 hop">Collapse</button>
              <button
                className={`inv-btn ${selectedNode ? '' : ''}`}
                onClick={handleIsolate}
                title="Isolate selected node and its neighbors"
                disabled={!selectedNode}
                style={{ opacity: selectedNode ? 1 : 0.45 }}
              >
                Isolate
              </button>
              <button
                className="inv-btn"
                onClick={handleHideUnrelated}
                title="Hide nodes not connected to selection"
                disabled={!selectedNode}
                style={{ opacity: selectedNode ? 1 : 0.45 }}
              >
                Hide Unrelated
              </button>
              <button className="inv-btn inv-btn--reset" onClick={handleReset} title="Reset all">Reset</button>
            </div>

            {/* Error indicator */}
            {graphError && (
              <span style={{ marginLeft: 8, color: 'var(--gov-red)', fontSize: 10, fontWeight: 700 }}>
                ⚠ {graphError}
              </span>
            )}
          </div>

          {/* ── Graph canvas ── */}
          <div className="inv-graph-canvas">
            {!address ? (
              <InvestigateEmptyState navigate={navigate} />
            ) : (
              <InvestigationGraph
                graphData={graphData}
                loading={graphLoading}
                centerAddress={address}
                hops={hops}
                direction={direction}
                onSelectNode={handleSelectNode}
                onSelectLink={handleSelectLink}
                onMetrics={handleMetrics}
                isolatedBranch={isolatedBranch}
                hiddenNodes={hiddenNodes}
                selectedPath={selectedPath}
              />
            )}
          </div>

          {/* ── Metrics strip (P3d) ── */}
          <div className="inv-metrics">
            <div className="inv-metrics__item">
              <span className="inv-metrics__label">Nodes</span>
              <span className="inv-metrics__value">{metrics.nodeCount || '—'}</span>
            </div>
            <div className="inv-metrics__item">
              <span className="inv-metrics__label">Transactions</span>
              <span className="inv-metrics__value">{metrics.txCount || '—'}</span>
            </div>
            <div className="inv-metrics__item">
              <span className="inv-metrics__label">Hops</span>
              <span className="inv-metrics__value">{hops === 5 ? 'N' : hops}</span>
            </div>
            {metrics.totalBtc > 0 && (
              <div className="inv-metrics__item">
                <span className="inv-metrics__label">BTC</span>
                <span className="inv-metrics__value">{metrics.totalBtc}</span>
              </div>
            )}
            {address && (
              <span className="inv-metrics__mode">
                Investigation Mode
              </span>
            )}
          </div>
        </div>

        {/* ── Inspector panel ── */}
        <div className="inv-inspector">
          <InspectorPanel
            selectedNode={queryNode ?? selectedNode}
            selectedLink={selectedLink}
            onNavigate={handleNavigate}
            onClear={handleReset}
            datasetId={null}
          />
        </div>

      </div>
    </div>
  );
}
