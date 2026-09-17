import React from 'react';

export default function MetricCards({ stats }) {
  if (!stats) return <div style={{ padding: '20px' }}>Loading metrics...</div>;

  return (
    <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
      <div className="metric-card-flat">
        <div className="metric-label-flat">TRANSACTIONS</div>
        <div className="metric-value-flat">{stats.total_transactions?.toLocaleString()}</div>
        <div className="metric-sub-flat">Raw ledger entries</div>
      </div>
      <div className="metric-card-flat">
        <div className="metric-label-flat">WALLET ENTITIES</div>
        <div className="metric-value-flat">{stats.total_wallets?.toLocaleString()}</div>
        <div className="metric-sub-flat">Distinct addresses</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #ef4444' }}>
        <div className="metric-label-flat">THREATS ISOLATED</div>
        <div className="metric-value-flat" style={{ color: '#ef4444' }}>
          {stats.anomalies_detected?.toLocaleString()}
        </div>
        <div className="metric-sub-flat">Isolation Forest signals</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #f59e0b' }}>
        <div className="metric-label-flat">PEELING CHAINS</div>
        <div className="metric-value-flat" style={{ color: '#f59e0b' }}>
          {stats.peeling_chains_detected ?? 0}
        </div>
        <div className="metric-sub-flat">Multi-hop split chains</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #8b5cf6' }}>
        <div className="metric-label-flat">COINJOIN MIXERS</div>
        <div className="metric-value-flat" style={{ color: '#8b5cf6' }}>
          {stats.coinjoin_mixers_detected ?? 0}
        </div>
        <div className="metric-sub-flat">Uniform mixing txs</div>
      </div>
    </div>
  );
}