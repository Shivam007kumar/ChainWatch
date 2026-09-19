import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NODE_COLORS = {
  ip:          { normal: '#003366', flagged: '#cc0000' }, // Gov Blue / Red
  transaction: { normal: '#6b7280', flagged: '#9ca3af' }, // Gray
  wallet:      { normal: '#138808', flagged: '#FF9933' }, // Gov Green / Saffron
};
const NODE_SIZE = {
  ip: 4,
  transaction: 6,
  wallet: 4,
};

const OVERVIEW_NEIGHBORS_PER_FLAGGED = 6;
const OVERVIEW_CONTEXT_NODES = 12;
const INVESTIGATION_NEIGHBORS = 48;

function endpointId(endpoint) {
  return endpoint?.id ?? endpoint;
}

function nodeImportance(node) {
  return Math.log1p(Math.max(
    Number(node.value || 0),
    Number(node.volume || 0),
    Number(node.connection_count || 0)
  ));
}

export default function GraphView({ data, loading, highlightNode, onNodeSelect, onReset, visible }) {
  const fgRef = useRef();
  const [hoveredNode, setHoveredNode] = useState(null);
  const [copyStatus, setCopyStatus] = useState('');
  const investigationMode = Boolean(highlightNode);

  // When the tab becomes visible again, re-fit the graph after the CSS
  // display:block transition completes (~100ms is enough)
  useEffect(() => {
    if (visible && fgRef.current && focusedData?.nodes?.length) {
      setTimeout(() => fgRef.current?.zoomToFit(500, 72), 120);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const focusedData = useMemo(() => {
    if (!data?.nodes?.length) return data;

    const nodesById = new Map(data.nodes.map(node => [node.id, node]));
    const adjacency = new Map(data.nodes.map(node => [node.id, []]));
    data.links.forEach(link => {
      const source = endpointId(link.source);
      const target = endpointId(link.target);
      adjacency.get(source)?.push({ id: target, value: link.value || 0 });
      adjacency.get(target)?.push({ id: source, value: link.value || 0 });
    });

    const rankNeighbor = ({ id, value }) => {
      const node = nodesById.get(id);
      if (!node) return -1;
      return (node.flagged ? 100000 : 0) + (Math.log1p(Number(value)) * 100) + nodeImportance(node);
    };
    const selectedIds = new Set();

    if (investigationMode && nodesById.has(highlightNode)) {
      selectedIds.add(highlightNode);
      adjacency.get(highlightNode)
        .sort((first, second) => rankNeighbor(second) - rankNeighbor(first))
        .slice(0, INVESTIGATION_NEIGHBORS)
        .forEach(neighbor => selectedIds.add(neighbor.id));
    } else {
      data.nodes.filter(node => node.flagged && node.type === 'wallet').forEach(node => {
        selectedIds.add(node.id);
        adjacency.get(node.id)
          .sort((first, second) => rankNeighbor(second) - rankNeighbor(first))
          .slice(0, OVERVIEW_NEIGHBORS_PER_FLAGGED)
          .forEach(neighbor => selectedIds.add(neighbor.id));
      });

      data.nodes
        .filter(node => !selectedIds.has(node.id))
        .sort((first, second) => nodeImportance(second) - nodeImportance(first))
        .slice(0, OVERVIEW_CONTEXT_NODES)
        .forEach(node => selectedIds.add(node.id));
    }

    const nodes = data.nodes.filter(node => selectedIds.has(node.id));
    const links = data.links.filter(link => selectedIds.has(endpointId(link.source)) && selectedIds.has(endpointId(link.target)));
    return { ...data, nodes, links };
  }, [data, highlightNode, investigationMode]);

  const normalizedNodeSizes = useMemo(() => {
    if (!focusedData?.nodes) return new Map();
    const maxima = focusedData.nodes.reduce((result, node) => {
      const type = node.type || 'wallet';
      result[type] = Math.max(result[type] || 0, nodeImportance(node));
      return result;
    }, {});

    return new Map(focusedData.nodes.map(node => {
      const type = node.type || 'wallet';
      const ratio = maxima[type] ? nodeImportance(node) / maxima[type] : 0;
      if (type === 'wallet') return [node.id, node.flagged ? 10 + ratio * 4 : 5 + ratio * 3];
      if (type === 'ip') return [node.id, 5 + ratio * 2];
      return [node.id, 3 + ratio * 2];
    }));
  }, [focusedData]);

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge').strength(-60);
    }
  }, [data]);

  // Derive neighbors for highlight dimming
  const neighbors = useMemo(() => {
    if (!highlightNode || !focusedData) return new Set();
    const s = new Set([highlightNode]);
    focusedData.links.forEach(l => {
      const srcId = endpointId(l.source);
      const tgtId = endpointId(l.target);
      if (srcId === highlightNode) s.add(tgtId);
      if (tgtId === highlightNode) s.add(srcId);
    });
    return s;
  }, [highlightNode, focusedData]);

  useEffect(() => {
    if (highlightNode && fgRef.current && focusedData?.nodes) {
      const node = focusedData.nodes.find(n => n.id === highlightNode);
      if (node && node.x !== undefined && node.y !== undefined) {
        // Delay slightly in case simulation is settling
        setTimeout(() => {
          fgRef.current.centerAt(node.x, node.y, 800);
          fgRef.current.zoom(4, 800);
        }, 100);
      }
    }
  }, [highlightNode, focusedData]);

  useEffect(() => {
    if (!highlightNode && fgRef.current && focusedData?.nodes?.length) {
      requestAnimationFrame(() => fgRef.current.zoomToFit(500, 72));
    }
  }, [highlightNode, focusedData]);

  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') onReset?.();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onReset]);

  const resetGraph = useCallback(() => {
    onReset?.();
    setHoveredNode(null);
    setCopyStatus('');
    requestAnimationFrame(() => fgRef.current?.zoomToFit(500, 72));
  }, [onReset]);

  const copyIpDetails = useCallback(async () => {
    if (!hoveredNode?.ip) return;
    const details = [
      `IP: ${hoveredNode.ip}`,
      `State: ${hoveredNode.state || 'N/A'}`,
      `ASN: ${hoveredNode.asn || 'N/A'}`,
      `Organization: ${hoveredNode.organization || 'N/A'}`
    ].join('\n');
    try {
      await navigator.clipboard.writeText(details);
      setCopyStatus('Copied');
      window.setTimeout(() => setCopyStatus(''), 1600);
    } catch {
      setCopyStatus('Copy unavailable');
    }
  }, [hoveredNode]);

  const nodeColor = useCallback((node) => {
    const type = node.type || 'wallet';
    const colors = NODE_COLORS[type] || NODE_COLORS.wallet;

    if (highlightNode && !neighbors.has(node.id)) {
      return 'rgba(200, 200, 200, 0.2)'; // Dim non-neighbors
    }

    if (type === 'wallet') {
      if (node.flagged) return '#ef4444'; // Flagged Seed Threat
      if (node.risk_score >= 70) return '#f97316'; // High Propagated Risk
      if (node.risk_score >= 40) return '#eab308'; // Medium Propagated Risk
      return colors.normal;
    }
    return node.flagged ? colors.flagged : colors.normal;
  }, [highlightNode, neighbors]);

  const nodeVal = useCallback((node) => {
    return normalizedNodeSizes.get(node.id) || NODE_SIZE[node.type || 'wallet'] || 4;
  }, [normalizedNodeSizes]);

  const linkColor = useCallback((link) => {
    if (highlightNode) {
      const srcId = endpointId(link.source);
      const tgtId = endpointId(link.target);
      if (srcId !== highlightNode && tgtId !== highlightNode) {
        return 'rgba(200, 200, 200, 0.05)';
      }
    }
    
    switch (link.type) {
      case 'BROADCASTED':      return 'rgba(59, 130, 246, 0.3)';
      case 'SENT_TO_NODE':     return 'rgba(59, 130, 246, 0.15)';
      case 'INPUT_TO_TX':      return 'rgba(0, 212, 170, 0.35)';
      case 'OUTPUT_TO_WALLET': return 'rgba(168, 85, 247, 0.35)';
      case 'SAME_ENTITY_AS':   return 'rgba(234, 179, 8, 0.60)';   // gold — co-spender
      default:                 return 'rgba(0, 0, 0, 0.1)';
    }
  }, [highlightNode]);

  if (loading) {
    return (
      <div className="graph-loading">
        <div className="spinner" />
        <span>Loading intelligence graph…</span>
      </div>
    );
  }

  if (!data) return null;
  if (!focusedData?.nodes?.length) return <div className="graph-empty">No graph data available. Ingest a ledger to build the Neural Map.</div>;

  return (
    <div className="neural-graph-canvas">
      <div className="graph-mode-indicator">
        {investigationMode ? 'Investigation view' : 'Overview view'}
        <span>{focusedData.nodes.length} nodes · {focusedData.links.length} links</span>
      </div>
      <ForceGraph2D
        ref={fgRef}
        graphData={focusedData}
        nodeColor={nodeColor}
        nodeVal={nodeVal}
        linkColor={linkColor}
        linkWidth={0.65}
        linkDirectionalParticles={0}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleColor={linkColor}
        backgroundColor="transparent"
        cooldownTicks={120}
        onNodeClick={onNodeSelect}
        onNodeHover={setHoveredNode}
        onBackgroundClick={resetGraph}
        nodeLabel={(node) => (investigationMode || node.flagged || node.type === 'ip')
          ? `[${(node.type || '').toUpperCase()}] ${node.label || node.id}${node.flagged ? '\nFLAGGED THREAT' : ''}${node.risk_score ? `\nRISK SCORE: ${node.risk_score}%` : ''}`
          : ''}
      />
      {hoveredNode && (
        <div className="graph-hover-inspector" onMouseDown={(event) => event.stopPropagation()}>
          <div className="graph-hover-type">{hoveredNode.type || 'entity'}</div>
          <div className="graph-hover-title">{hoveredNode.type === 'wallet' ? 'Wallet intelligence' : hoveredNode.type === 'ip' ? 'IP intelligence' : 'Transaction intelligence'}</div>
          {hoveredNode.type === 'wallet' && <>
            <div className="graph-hover-row"><span>Wallet</span><strong>{hoveredNode.address || hoveredNode.id.replace(/^wallet:/, '')}</strong></div>
            <div className="graph-hover-row"><span>State</span><strong>{hoveredNode.state || 'N/A'}</strong></div>
            <div className="graph-hover-row"><span>Risk Score</span><strong style={{ color: (hoveredNode.risk_score || 0) > 60 ? '#ef4444' : '#10b981' }}>{hoveredNode.risk_score || 0}%</strong></div>
            {hoveredNode.risk_factors?.length > 0 && (
              <div className="graph-hover-row"><span>Factors</span><strong style={{ fontSize: '10px', color: '#f87171' }}>{hoveredNode.risk_factors.join(', ')}</strong></div>
            )}
            {hoveredNode.shap_attributions?.length > 0 && (
              <div className="graph-hover-shap">
                <div className="graph-hover-shap-title">XAI ATTRIBUTION</div>
                {hoveredNode.shap_attributions.slice(0, 2).map((attr, i) => (
                  <div key={i} className="graph-hover-row">
                    <span style={{ fontSize: '9px', maxWidth: '110px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {attr.label}
                    </span>
                    <strong style={{
                      color: attr.direction === 'positive' ? '#ef4444' : '#10b981',
                      fontSize: '10px',
                      flexShrink: 0,
                    }}>
                      {attr.direction === 'positive' ? '+' : '-'}{attr.pct_contribution}%
                      <span style={{ color: '#94a3b8', fontWeight: 400, marginLeft: '3px' }}>
                        {Math.abs(attr.sigma).toFixed(1)}σ
                      </span>
                    </strong>
                  </div>
                ))}
              </div>
            )}
          </>}
          {hoveredNode.type === 'ip' && <>
            <div className="graph-hover-row"><span>IP</span><strong>{hoveredNode.ip || hoveredNode.id.replace(/^ip:/, '')}</strong></div>
            <div className="graph-hover-row"><span>State</span><strong>{hoveredNode.state || 'N/A'}</strong></div>
            <div className="graph-hover-row"><span>ASN</span><strong>{hoveredNode.asn || 'N/A'}</strong></div>
            <div className="graph-hover-row"><span>Organisation</span><strong>{hoveredNode.organization || 'N/A'}</strong></div>
            <button className="graph-copy-btn" onClick={copyIpDetails}>{copyStatus || 'Copy IP intelligence'}</button>
          </>}
          {hoveredNode.type === 'transaction' && <div className="graph-hover-row"><span>Transaction</span><strong>{hoveredNode.label || hoveredNode.id.replace(/^tx:/, '')}</strong></div>}
        </div>
      )}
    </div>
  );
}
