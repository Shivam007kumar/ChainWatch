import { useEffect, useRef, useCallback, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NODE_COLORS = {
  ip:          { normal: '#3b82f6', flagged: '#ef4444' },
  transaction: { normal: '#a855f7', flagged: '#c084fc' },
  wallet:      { normal: '#00d4aa', flagged: '#ff4d6d' },
};

const NODE_SIZE = {
  ip: 4,
  transaction: 6,
  wallet: 4,
};

export default function GraphView({ data, loading, highlightNode }) {
  const fgRef = useRef();

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge').strength(-60);
    }
  }, [data]);

  // Derive neighbors for highlight dimming
  const neighbors = useMemo(() => {
    if (!highlightNode || !data) return new Set();
    const s = new Set([highlightNode]);
    data.links.forEach(l => {
      const srcId = l.source.id ?? l.source;
      const tgtId = l.target.id ?? l.target;
      if (srcId === highlightNode) s.add(tgtId);
      if (tgtId === highlightNode) s.add(srcId);
    });
    return s;
  }, [highlightNode, data]);

  useEffect(() => {
    if (highlightNode && fgRef.current && data?.nodes) {
      const node = data.nodes.find(n => n.id === highlightNode);
      if (node && node.x !== undefined && node.y !== undefined) {
        // Delay slightly in case simulation is settling
        setTimeout(() => {
          fgRef.current.centerAt(node.x, node.y, 800);
          fgRef.current.zoom(4, 800);
        }, 100);
      }
    }
  }, [highlightNode, data]);

  const nodeColor = useCallback((node) => {
    const type = node.type || 'wallet';
    const baseColor = node.flagged ? NODE_COLORS[type].flagged : NODE_COLORS[type].normal;
    if (highlightNode && !neighbors.has(node.id)) {
      return 'rgba(200, 200, 200, 0.2)'; // Dim non-neighbors
    }
    return baseColor;
  }, [highlightNode, neighbors]);

  const nodeVal = useCallback((node) => {
    const base = NODE_SIZE[node.type || 'wallet'] || 4;
    return node.flagged ? base * 2 : base;
  }, []);

  const linkColor = useCallback((link) => {
    if (highlightNode) {
      const srcId = link.source.id ?? link.source;
      const tgtId = link.target.id ?? link.target;
      if (srcId !== highlightNode && tgtId !== highlightNode) {
        return 'rgba(200, 200, 200, 0.05)';
      }
    }
    
    switch (link.type) {
      case 'BROADCASTED':      return 'rgba(59, 130, 246, 0.3)';
      case 'SENT_TO_NODE':     return 'rgba(59, 130, 246, 0.15)';
      case 'INPUT_TO_TX':      return 'rgba(0, 212, 170, 0.35)';
      case 'OUTPUT_TO_WALLET': return 'rgba(168, 85, 247, 0.35)';
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

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={data}
      nodeColor={nodeColor}
      nodeVal={nodeVal}
      linkColor={linkColor}
      linkWidth={0.8}
      linkDirectionalParticles={2}
      linkDirectionalParticleWidth={1.5}
      linkDirectionalParticleColor={linkColor}
      backgroundColor="transparent"
      cooldownTicks={120}
      nodeLabel={(node) =>
        `[${(node.type || '').toUpperCase()}] ${node.id}${node.flagged ? '\n⚠ FLAGGED' : ''}`
      }
    />
  );
}
