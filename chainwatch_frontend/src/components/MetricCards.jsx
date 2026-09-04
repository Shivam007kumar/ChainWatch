import React from 'react';

export default function MetricCards({ stats }) {
  if (!stats) return <div style={{ padding: '20px' }}>Loading metrics...</div>;

  return (
    <div className="metrics-grid">
      <div className="metric-card-flat">
        <div className="metric-label-flat">TRANSACTIONS ANALYZED</div>
        <div className="metric-value-flat">{stats.total_transactions?.toLocaleString()}</div>
        <div className="metric-sub-flat">Raw ledger entries processed</div>
      </div>
      <div className="metric-card-flat">
        <div className="metric-label-flat">UNIQUE WALLET ENTITIES</div>
        <div className="metric-value-flat">{stats.total_wallets?.toLocaleString()}</div>
        <div className="metric-sub-flat">Distinct addresses observed</div>
      </div>
      <div className="metric-card-flat" style={{ borderTop: '4px solid #cc0000' }}>
        <div className="metric-label-flat">THREATS ISOLATED</div>
        <div className="metric-value-flat" style={{ color: '#cc0000' }}>
          {stats.anomalies_detected?.toLocaleString()}
        </div>
        <div className="metric-sub-flat">High-confidence anomalies</div>
      </div>
    </div>
  );
}