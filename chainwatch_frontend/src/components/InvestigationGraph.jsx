/**
 * InvestigationGraph.jsx
 * ──────────────────────
 * The Neural Map graph renderer for the investigation workstation.
 * Used by InvestigationPage. The existing GraphView.jsx is preserved
 * unchanged for Home.jsx and Workspace.jsx.
 *
 * New capabilities over GraphView:
 *   - Driven by /investigations/wallet/{address}/graph (nodes + edges + meta)
 *   - Hop controls: 1 / 2 / 3 / N hops, forward / backward / both direction
 *   - Branch management: expand, collapse, isolate, hide unrelated, reset
 *   - Selectable arcs/paths: clicking a link selects the path
 *   - Selected path highlighted gold; directional animation ONLY on selected path
 *   - Graph metrics strip (nodes, transactions, hops, BTC value)
 *   - Unified hover inspector (wallet / transaction / IP)
 *   - onSelectNode(node)  — called when a node is clicked
 *   - onSelectLink(link)  — called when a link/edge is clicked
 *
 * Props:
 *   graphData    {object}   { nodes[], edges[], meta{} } from investigation API
 *   loading      {boolean}
 *   centerAddress{string}   the wallet that anchors the graph
 *   hops         {number}   current hop count (1–5)
 *   direction    {string}   'both' | 'forward' | 'backward'
 *   onSelectNode {function} (node) => void
 *   onSelectLink {function} (link) => void
 *   onMetrics    {function} ({ nodeCount, txCount, hops, totalBtc }) => void
 *   isolatedBranch {Set}    node IDs to show exclusively (null = show all)
 *   hiddenNodes  {Set}      node IDs to hide
 *   selectedPath {object}   { source, target } — gold-highlights the path between them
 */

import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

// ── Semantic colors — match existing ChainWatch node colors ──────────────────
// Wallet:      orange (flagged) / green (normal) — same as GraphView
// Transaction: gray — same as GraphView
// IP:          gov-blue — same as GraphView
// Selected path / co-spender: gold — same as GraphView

const NODE_COLOR = {
  wallet: {
    normal:   '#138808',   // gov-green
    medium:   '#eab308',   // amber
    high:     '#f97316',   // orange
    flagged:  '#ef4444',   // red
    selected: '#eab308',   // gold
    dimmed:   'rgba(200,200,200,0.15)',
  },
  transaction: {
    normal:   '#6b7280',
    selected: '#3b82f6',   // blue when on selected path
    dimmed:   'rgba(200,200,200,0.1)',
  },
  ip: {
    normal:   '#003366',   // gov-blue
    flagged:  '#cc0000',
    selected: '#8b5cf6',   // purple when on selected path
    dimmed:   'rgba(200,200,200,0.1)',
  },
};

const LINK_COLOR = {
  BROADCASTED:          'rgba(59,130,246,0.30)',
  INPUT_TO_TX:          'rgba(0,212,170,0.35)',
  OUTPUT_TO_WALLET:     'rgba(168,85,247,0.35)',
  SAME_ENTITY_AS:       'rgba(234,179,8,0.60)',
  OBSERVED_DESTINATION: 'rgba(139,92,246,0.25)',
  SENT:                 'rgba(0,212,170,0.30)',
  RECEIVED_BY:          'rgba(168,85,247,0.30)',
  selected:             'rgba(234,179,8,0.95)',  // gold bright for selected path
  dimmed:               'rgba(200,200,200,0.04)',
};

function endId(ep) { return ep?.id ?? ep; }

function riskLevel(node) {
  // Handles both legacy flat fields and new { risk: { score, level } } shape
  const score = node.risk?.score ?? node.risk_score ?? 0;
  if (node.risk?.flagged || node.flagged) return 'flagged';
  if (score >= 70) return 'high';
  if (score >= 40) return 'medium';
  return 'normal';
}

function nodeImportance(node) {
  const v = node.value ?? node.volume ?? 0;
  return Math.log1p(Math.max(Number(v), Number(node.connection_count || 0)));
}

export default function InvestigationGraph({
  graphData,
  loading,
  centerAddress,
  hops         = 2,
  direction    = 'both',
  onSelectNode,
  onSelectLink,
  onMetrics,
  isolatedBranch = null,   // Set of node IDs to show exclusively
  hiddenNodes    = null,   // Set of node IDs to hide
  selectedPath   = null,   // { source: nodeId, target: nodeId }
}) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dims, setDims] = useState({ width: 0, height: 0 });
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredLink, setHoveredLink] = useState(null);
  const [copyStatus,  setCopyStatus]  = useState('');

  // ── Measure container dimensions via ResizeObserver ────────────────────────
  // ForceGraph2D reads width/height on mount. When the canvas lives inside a
  // flex layout, clientWidth/clientHeight may be 0 on the very first mount
  // (browser hasn't finished layout yet). Passing explicit measured dimensions
  // fixes the blank-canvas-on-first-visit bug.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Measure immediately — may already have valid dimensions on re-mounts
    setDims({ width: el.clientWidth, height: el.clientHeight });
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setDims({ width: Math.floor(width), height: Math.floor(height) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Normalise backend response ─────────────────────────────────────────────
  // /investigations/wallet/{addr}/graph returns { nodes[], edges[], meta{} }
  // ForceGraph2D expects { nodes[], links[] }
  const normalisedData = useMemo(() => {
    if (!graphData) return null;

    const rawNodes = graphData.nodes ?? [];
    const rawEdges = graphData.edges ?? graphData.links ?? [];

    // Normalise node fields — investigation API uses { risk: { score, level, flagged } }
    const nodes = rawNodes.map(n => ({
      ...n,
      // flatten risk for uniform access
      risk_score:  n.risk?.score  ?? n.risk_score  ?? 0,
      flagged:     n.risk?.flagged ?? n.flagged     ?? false,
      risk_level:  n.risk?.level  ?? (n.flagged ? 'high' : 'low'),
    }));

    // edges → links
    const links = rawEdges.map(e => ({
      ...e,
      id:     e.id ?? `${endId(e.source)}__${endId(e.target)}`,
      type:   e.type ?? 'RELATED',
    }));

    return { nodes, links };
  }, [graphData]);

  // ── Derive selected path node set ──────────────────────────────────────────
  const selectedPathNodes = useMemo(() => {
    if (!selectedPath || !normalisedData) return new Set();
    const s = new Set();
    if (selectedPath.source) s.add(selectedPath.source);
    if (selectedPath.target) s.add(selectedPath.target);
    // Also include all nodes that lie on any link between source and target
    normalisedData.links.forEach(l => {
      const src = endId(l.source);
      const tgt = endId(l.target);
      if (s.has(src) || s.has(tgt)) { s.add(src); s.add(tgt); }
    });
    return s;
  }, [selectedPath, normalisedData]);

  // ── Visibility filtering (branch isolation / hidden nodes) ─────────────────
  const visibleData = useMemo(() => {
    if (!normalisedData) return null;
    let { nodes, links } = normalisedData;

    if (isolatedBranch?.size) {
      nodes = nodes.filter(n => isolatedBranch.has(n.id));
      links = links.filter(l => isolatedBranch.has(endId(l.source)) && isolatedBranch.has(endId(l.target)));
    }
    if (hiddenNodes?.size) {
      nodes = nodes.filter(n => !hiddenNodes.has(n.id));
      links = links.filter(l => !hiddenNodes.has(endId(l.source)) && !hiddenNodes.has(endId(l.target)));
    }

    return { nodes, links };
  }, [normalisedData, isolatedBranch, hiddenNodes]);

  // ── Metrics — reported up to InvestigationPage ─────────────────────────────
  useEffect(() => {
    if (!visibleData || !onMetrics) return;
    const txCount    = visibleData.nodes.filter(n => n.type === 'transaction').length;
    const totalBtc   = visibleData.links.reduce((s, l) => s + (Number(l.amount_btc) || 0), 0);
    onMetrics({
      nodeCount: visibleData.nodes.length,
      txCount,
      hops,
      totalBtc: Math.round(totalBtc * 1e4) / 1e4,
    });
  }, [visibleData, hops, onMetrics]);

  // ── D3 force tuning ────────────────────────────────────────────────────────
  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge')?.strength(-80);
      fgRef.current.d3Force('link')?.distance(55);
    }
  }, [normalisedData]);

  // ── Auto-center on centre wallet after data loads ─────────────────────────
  useEffect(() => {
    if (!centerAddress || !visibleData?.nodes?.length) return;
    const centerId = `wallet:${centerAddress}`;
    const node = visibleData.nodes.find(n => n.id === centerId);
    if (node && node.x !== undefined && fgRef.current) {
      setTimeout(() => {
        fgRef.current?.centerAt(node.x, node.y, 600);
        fgRef.current?.zoom(3.5, 600);
      }, 200);
    } else {
      // Node not placed yet — zoom to fit
      setTimeout(() => fgRef.current?.zoomToFit(500, 48), 300);
    }
  }, [centerAddress, visibleData]);

  // ESC clears selection
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onSelectNode?.(null); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [onSelectNode]);

  // ── Node color ─────────────────────────────────────────────────────────────
  const nodeColor = useCallback((node) => {
    const type   = node.type || 'wallet';
    const colors = NODE_COLOR[type] || NODE_COLOR.wallet;

    // On selected path → gold
    if (selectedPathNodes.has(node.id)) return NODE_COLOR.wallet.selected;

    // Dim if there's an active path and this node isn't on it
    if (selectedPathNodes.size > 0 && !selectedPathNodes.has(node.id)) return colors.dimmed;

    if (type === 'wallet') return colors[riskLevel(node)] ?? colors.normal;
    if (type === 'ip')     return node.flagged ? colors.flagged : colors.normal;
    return colors.normal;
  }, [selectedPathNodes]);

  // ── Node size ──────────────────────────────────────────────────────────────
  const nodeVal = useCallback((node) => {
    const base = node.type === 'wallet' ? (node.flagged ? 12 : 6)
               : node.type === 'ip'     ? 5
               :                          4;
    return base + nodeImportance(node) * 1.5;
  }, []);

  // ── Link color ─────────────────────────────────────────────────────────────
  const linkColor = useCallback((link) => {
    const src = endId(link.source);
    const tgt = endId(link.target);

    // Selected path links → bright gold
    if (selectedPathNodes.has(src) && selectedPathNodes.has(tgt)) {
      return LINK_COLOR.selected;
    }
    // Dim if there's an active path selection and this link isn't on it
    if (selectedPathNodes.size > 0) return LINK_COLOR.dimmed;

    return LINK_COLOR[link.type] ?? 'rgba(148,163,184,0.2)';
  }, [selectedPathNodes]);

  // ── Link width ─────────────────────────────────────────────────────────────
  const linkWidth = useCallback((link) => {
    const src = endId(link.source);
    const tgt = endId(link.target);
    if (selectedPathNodes.has(src) && selectedPathNodes.has(tgt)) return 2;
    return 0.8;
  }, [selectedPathNodes]);

  // ── Directional particles — ONLY on selected path links ──────────────────
  const linkParticles = useCallback((link) => {
    const src = endId(link.source);
    const tgt = endId(link.target);
    return (selectedPathNodes.has(src) && selectedPathNodes.has(tgt)) ? 3 : 0;
  }, [selectedPathNodes]);

  const linkParticleColor = useCallback(() => '#eab308', []); // gold

  // ── Node click → select and fire callback ─────────────────────────────────
  const handleNodeClick = useCallback((node) => {
    onSelectNode?.(node);
  }, [onSelectNode]);

  // ── Link click → select and fire callback ─────────────────────────────────
  const handleLinkClick = useCallback((link) => {
    onSelectLink?.(link);
  }, [onSelectLink]);

  // ── Background click → deselect ───────────────────────────────────────────
  const handleBgClick = useCallback(() => {
    setHoveredNode(null);
    setHoveredLink(null);
    onSelectNode?.(null);
    onSelectLink?.(null);
    requestAnimationFrame(() => fgRef.current?.zoomToFit(500, 48));
  }, [onSelectNode, onSelectLink]);

  // ── Hover ──────────────────────────────────────────────────────────────────
  const handleNodeHover = useCallback((node) => {
    setHoveredNode(node ?? null);
  }, []);

  // ── Copy IP to clipboard ───────────────────────────────────────────────────
  const copyIp = useCallback(async () => {
    if (!hoveredNode?.ip) return;
    const text = [
      `IP: ${hoveredNode.ip}`,
      `State: ${hoveredNode.state || 'N/A'}`,
      `ASN: ${hoveredNode.asn || 'N/A'}`,
      `Org: ${hoveredNode.organization || 'N/A'}`,
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('Copied');
      setTimeout(() => setCopyStatus(''), 1600);
    } catch { setCopyStatus('Unavailable'); }
  }, [hoveredNode]);

  // ── Node label (tooltip on hover) ─────────────────────────────────────────
  const nodeLabel = useCallback((node) => {
    const score = node.risk_score ?? 0;
    const flag  = node.flagged ? ' · FLAGGED' : '';
    if (node.type === 'wallet')
      return `[WALLET] ${(node.address || node.id).slice(0, 20)}…\nRisk: ${score}%${flag}`;
    if (node.type === 'ip')
      return `[IP] ${node.ip || node.id}\n${node.state || ''} · ${node.asn || ''}`;
    if (node.type === 'transaction')
      return `[TX] ${node.label || node.id}`;
    return node.id;
  }, []);

  // ── Loading / empty guards ─────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="inv-graph-overlay">
        <div className="inv-spinner" />
        <span>Loading graph…</span>
      </div>
    );
  }

  if (!visibleData?.nodes?.length) {
    return (
      <div className="inv-graph-overlay">
        <span style={{ fontSize: 28, opacity: 0.25 }}>✦</span>
        <span>
          {centerAddress
            ? `No graph data for ${centerAddress.slice(0, 14)}…`
            : 'Select a wallet to begin investigation'}
        </span>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={visibleData}
        nodeId="id"
        nodeColor={nodeColor}
        nodeVal={nodeVal}
        nodeLabel={nodeLabel}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalParticles={linkParticles}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={linkParticleColor}
        linkDirectionalParticleSpeed={0.004}
        backgroundColor="transparent"
        cooldownTicks={140}
        onNodeClick={handleNodeClick}
        onLinkClick={handleLinkClick}
        onNodeHover={handleNodeHover}
        onBackgroundClick={handleBgClick}
        width={dims.width  || undefined}
        height={dims.height || undefined}
      />

      {/* ── Hover inspector — matches existing graph-hover-inspector style ── */}
      {hoveredNode && (
        <div
          className="graph-hover-inspector"
          onMouseDown={e => e.stopPropagation()}
          style={{ zIndex: 20 }}
        >
          <div className="graph-hover-type">{hoveredNode.type || 'entity'}</div>
          <div className="graph-hover-title">
            {hoveredNode.type === 'wallet' ? 'Wallet intelligence'
              : hoveredNode.type === 'ip'  ? 'IP intelligence'
              :                              'Transaction intelligence'}
          </div>

          {hoveredNode.type === 'wallet' && <>
            <div className="graph-hover-row">
              <span>Wallet</span>
              <strong>{(hoveredNode.address || hoveredNode.id?.replace(/^wallet:/, '')).slice(0, 22)}…</strong>
            </div>
            <div className="graph-hover-row">
              <span>State</span>
              <strong>{hoveredNode.state || 'N/A'}</strong>
            </div>
            <div className="graph-hover-row">
              <span>Risk</span>
              <strong style={{ color: hoveredNode.risk_score >= 70 ? '#ef4444' : hoveredNode.risk_score >= 40 ? '#f97316' : '#22c55e' }}>
                {hoveredNode.risk_score ?? 0}%
              </strong>
            </div>
            {hoveredNode.risk_factors?.length > 0 && (
              <div className="graph-hover-row">
                <span>Factors</span>
                <strong style={{ fontSize: 9, color: '#f87171' }}>
                  {hoveredNode.risk_factors.slice(0, 2).join(', ')}
                </strong>
              </div>
            )}
            {hoveredNode.shap_attributions?.slice(0, 2).map((a, i) => (
              <div key={i} className="graph-hover-row">
                <span style={{ fontSize: 9 }}>{a.label}</span>
                <strong style={{ color: a.direction === 'positive' ? '#ef4444' : '#22c55e', fontSize: 10 }}>
                  {a.direction === 'positive' ? '+' : '-'}{a.pct_contribution}%
                  <span style={{ color: '#94a3b8', fontWeight: 400, marginLeft: 3 }}>
                    {Math.abs(a.sigma ?? 0).toFixed(1)}σ
                  </span>
                </strong>
              </div>
            ))}
            <button
              className="graph-copy-btn"
              style={{ marginTop: 8 }}
              onClick={() => onSelectNode?.(hoveredNode)}
            >
              Investigate →
            </button>
          </>}

          {hoveredNode.type === 'ip' && <>
            <div className="graph-hover-row"><span>IP</span><strong>{hoveredNode.ip || hoveredNode.id?.replace(/^ip:/, '')}</strong></div>
            <div className="graph-hover-row"><span>State</span><strong>{hoveredNode.state || 'N/A'}</strong></div>
            <div className="graph-hover-row"><span>ASN</span><strong>{hoveredNode.asn || 'N/A'}</strong></div>
            <div className="graph-hover-row"><span>Org</span><strong>{hoveredNode.organization || 'N/A'}</strong></div>
            <button className="graph-copy-btn" onClick={copyIp}>{copyStatus || 'Copy IP details'}</button>
          </>}

          {hoveredNode.type === 'transaction' && <>
            <div className="graph-hover-row">
              <span>TXID</span>
              <strong>{(hoveredNode.label || hoveredNode.id?.replace(/^tx:/, '')).slice(0, 16)}…</strong>
            </div>
            {hoveredNode.fee != null && (
              <div className="graph-hover-row"><span>Fee</span><strong>{hoveredNode.fee} BTC</strong></div>
            )}
            <button
              className="graph-copy-btn"
              style={{ marginTop: 8 }}
              onClick={() => onSelectNode?.(hoveredNode)}
            >
              Investigate →
            </button>
          </>}
        </div>
      )}

      {/* ── Graph legend — matches existing .graph-legend style ── */}
      <div className="inv-graph-legend" style={{ bottom: 40 }}>
        <div className="inv-graph-legend__item">
          <div className="inv-graph-legend__dot" style={{ background: '#ef4444' }} /> Flagged
        </div>
        <div className="inv-graph-legend__item">
          <div className="inv-graph-legend__dot" style={{ background: '#138808' }} /> Wallet
        </div>
        <div className="inv-graph-legend__item">
          <div className="inv-graph-legend__dot" style={{ background: '#6b7280' }} /> TX
        </div>
        <div className="inv-graph-legend__item">
          <div className="inv-graph-legend__dot" style={{ background: '#003366' }} /> IP
        </div>
        <div className="inv-graph-legend__item">
          <div className="inv-graph-legend__dot" style={{ background: '#eab308' }} /> Selected
        </div>
      </div>
    </div>
  );
}
