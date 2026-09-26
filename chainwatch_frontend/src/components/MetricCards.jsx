import React from 'react';

/**
 * normalise(stats)
 * ─────────────────
 * The backend may return either:
 *   (a) The old flat shape from stats.json:
 *         { total_transactions, total_wallets, anomalies_detected,
 *           peeling_chains_detected, coinjoin_mixers_detected }
 *   (b) The new nested shape from api/stats.py:
 *         { entities: { wallets, transactions },
 *           risk: { flagged_wallets },
 *           detections: { anomalies, peeling_chains, coinjoins } }
 *
 * This normaliser reads from whichever shape is present, so the component
 * works regardless of which backend endpoint wins route registration.
 */
function normalise(stats) {
  if (!stats) return null;
  return {
    total_transactions:       stats.total_transactions        ?? stats.entities?.transactions       ?? null,
    total_wallets:            stats.total_wallets             ?? stats.entities?.wallets            ?? null,
    anomalies_detected:       stats.anomalies_detected        ?? stats.risk?.flagged_wallets        ?? null,
    peeling_chains_detected:  stats.peeling_chains_detected   ?? stats.detections?.peeling_chains  ?? null,
    coinjoin_mixers_detected: stats.coinjoin_mixers_detected  ?? stats.detections?.coinjoins       ?? null,
  };
}

export default function MetricCards({ stats }) {
  if (!stats) return <div style={{ padding: '20px' }}>Loading metrics...</div>;

  const n = normalise(stats);

  return (
    <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
      <div className="metric-card-flat">
        <div className="metric-label-flat">TRANSACTIONS</div>
        <div className="metric-value-flat">
          {n.total_transactions !== null ? n.total_transactions.toLocaleString() : '—'}
        </div>
        <div className="metric-sub-flat">Raw ledger entries</div>
      </div>
      <div className="metric-card-flat">
        <div className="metric-label-flat">WALLET ENTITIES</div>
        <div className="metric-value-flat">
          {n.total_wallets !== null ? n.total_wallets.toLocaleString() : '—'}
        </div>
        <div className="metric-sub-flat">Distinct addresses</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #ef4444' }}>
        <div className="metric-label-flat">THREATS ISOLATED</div>
        <div className="metric-value-flat" style={{ color: '#ef4444' }}>
          {n.anomalies_detected !== null ? n.anomalies_detected.toLocaleString() : '—'}
        </div>
        <div className="metric-sub-flat">Isolation Forest signals</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #f59e0b' }}>
        <div className="metric-label-flat">PEELING CHAINS</div>
        <div className="metric-value-flat" style={{ color: '#f59e0b' }}>
          {n.peeling_chains_detected !== null ? n.peeling_chains_detected : '—'}
        </div>
        <div className="metric-sub-flat">Multi-hop split chains</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #8b5cf6' }}>
        <div className="metric-label-flat">COINJOIN MIXERS</div>
        <div className="metric-value-flat" style={{ color: '#8b5cf6' }}>
          {n.coinjoin_mixers_detected !== null ? n.coinjoin_mixers_detected : '—'}
        </div>
        <div className="metric-sub-flat">Uniform mixing txs</div>
      </div>
    </div>
  );
}
