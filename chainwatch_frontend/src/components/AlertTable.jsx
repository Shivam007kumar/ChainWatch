import { useState, useEffect } from 'react';

function confidenceClass(score) {
  if (score >= 85) return 'high';
  if (score >= 72) return 'mid';
  return 'low';
}

function ClusterBadge({ clusterId, clusterName }) {
  return (
    <span className={`cluster-badge cluster-${clusterId}`}>
      {clusterName?.split(' ')[0]}
    </span>
  );
}

function DetailDrawer({ alert }) {
  return (
    <div className="detail-drawer">
      <div className="detail-title">⚙ Intelligence Report</div>
      <div className="detail-reason">{alert.reason}</div>
      <div className="detail-stats">
        <div className="detail-stat">
          <div className="detail-stat-label">TX Count</div>
          <div className="detail-stat-value">{alert.tx_count}</div>
        </div>
        <div className="detail-stat">
          <div className="detail-stat-label">Total Volume</div>
          <div className="detail-stat-value">{alert.total_volume_btc} BTC</div>
        </div>
        <div className="detail-stat">
          <div className="detail-stat-label">Unique IPs</div>
          <div className="detail-stat-value">{alert.unique_ip_count}</div>
        </div>
        <div className="detail-stat">
          <div className="detail-stat-label">High-Risk Hits</div>
          <div className="detail-stat-value" style={{ color: alert.high_risk_hits > 0 ? 'var(--red)' : 'inherit' }}>
            {alert.high_risk_hits}
          </div>
        </div>
        <div className="detail-stat" style={{ gridColumn: '1 / -1' }}>
          <div className="detail-stat-label">Sample TXID</div>
          <div className="detail-stat-value" style={{ fontSize: 11, wordBreak: 'break-all' }}>
            {alert.sample_txid}
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertRow({ alert, rank, isSelected, onSelect }) {
  const cls = confidenceClass(alert.confidence_score);
  const [copied, setCopied] = useState(false);

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(alert.wallet_address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  return (
    <>
      <div
        className={`alert-row ${isSelected ? 'selected' : ''}`}
        onClick={() => onSelect(isSelected ? null : alert.wallet_address)}
        id={`alert-${rank}`}
      >
        <div className="alert-rank">#{rank} — {alert.cluster_name}</div>
        <div className="alert-wallet" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="flag-icon">🔴</span>
            <span>{alert.wallet_address.slice(0, 18)}…</span>
            <button 
              onClick={handleCopy} 
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px' }}
              title="Copy Address"
            >
              {copied ? '✅' : '📋'}
            </button>
          </div>
          <ClusterBadge clusterId={alert.cluster_id} clusterName={alert.cluster_name} />
        </div>
        <div className="alert-meta">
          <div className="confidence-bar-wrap">
            <div
              className={`confidence-bar ${cls}`}
              style={{ width: `${alert.confidence_score}%` }}
            />
          </div>
          <span className={`confidence-pct ${cls}`}>
            {alert.confidence_score.toFixed(1)}%
          </span>
        </div>
      </div>
      {isSelected && <DetailDrawer alert={alert} />}
    </>
  );
}

export default function AlertTable({ 
  alerts, 
  loading, 
  clusters,
  selectedWallet, 
  onSelectWallet,
  minConfidence,
  onMinConfidenceChange,
  selectedCluster,
  onClusterChange
}) {

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ── Filters Header ── */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Confidence Threshold ({minConfidence}%)
            </label>
            <input 
              type="range" 
              min="0" max="100" 
              value={minConfidence} 
              onChange={(e) => onMinConfidenceChange(Number(e.target.value))}
              style={{ width: '60%' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => onClusterChange(null)}
              className={`cluster-badge ${selectedCluster === null ? 'cluster-5' : ''}`}
              style={{ cursor: 'pointer', opacity: selectedCluster === null ? 1 : 0.6 }}
            >
              All Patterns
            </button>
            {clusters?.map(c => (
              <button
                key={c.cluster_id}
                onClick={() => onClusterChange(c.cluster_id)}
                className={`cluster-badge cluster-${c.cluster_id}`}
                style={{ cursor: 'pointer', opacity: selectedCluster === c.cluster_id ? 1 : 0.6 }}
              >
                {c.cluster_name.split(' ')[0]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Alert Body ── */}
      {loading ? (
        <div className="alert-body" style={{ padding: 20 }}>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{ marginBottom: 16 }}>
              <div className="metric-loading" style={{ height: 14, marginBottom: 8, width: '60%' }} />
              <div className="metric-loading" style={{ height: 10, width: '90%' }} />
            </div>
          ))}
        </div>
      ) : !alerts?.length ? (
        <div className="alert-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
          No alerts match the current filters.
        </div>
      ) : (
        <div className="alert-body">
          {alerts.map((alert, i) => (
            <AlertRow
              key={alert.wallet_address}
              alert={alert}
              rank={i + 1}
              isSelected={selectedWallet === alert.wallet_address}
              onSelect={onSelectWallet}
            />
          ))}
        </div>
      )}
    </div>
  );
}
