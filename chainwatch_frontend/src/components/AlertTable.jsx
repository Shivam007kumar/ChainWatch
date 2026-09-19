import React from 'react';

// ── SHAP attribution chips ────────────────────────────────────────────────────
function ShapChips({ attributions }) {
  if (!attributions || attributions.length === 0) return null;
  return (
    <div className="shap-chips">
      {attributions.map((attr, i) => (
        <div
          key={i}
          className={`shap-chip ${attr.direction === 'positive' ? 'shap-pos' : 'shap-neg'}`}
          title={`${attr.label}: ${attr.feature_value} (${Math.abs(attr.sigma).toFixed(1)}σ ${attr.sigma >= 0 ? 'above' : 'below'} mean)`}
        >
          <span className="shap-feature">{attr.label}</span>
          <span className="shap-pct">
            {attr.direction === 'positive' ? '+' : '-'}{attr.pct_contribution}%
          </span>
          <span className="shap-sigma">{Math.abs(attr.sigma).toFixed(1)}σ</span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AlertTable({ alerts, loading, selectedWallet, onSelectWallet }) {
  if (loading) {
    return <div style={{ padding: '20px' }}>Querying intelligence database...</div>;
  }
  if (!alerts || alerts.length === 0) {
    return <div style={{ padding: '20px' }}>No active threats found.</div>;
  }

  return (
    <div className="alert-body">
      {alerts.map((alert, idx) => {
        const riskScore        = alert.risk_score || alert.confidence_score || 0;
        const riskFactors      = alert.risk_factors      || [];
        const shapAttributions = alert.shap_attributions || [];
        const isSelected       = selectedWallet === alert.wallet_address;

        return (
          <div
            key={alert.wallet_address}
            className={`alert-row-flat ${isSelected ? 'selected' : ''}`}
            onClick={() => onSelectWallet(alert.wallet_address)}
          >
            {/* Header row: file number + risk badge */}
            <div className="alert-header-flat">
              <span className="alert-rank-flat">FILE #{idx + 1}</span>
              <span
                className="alert-score-flat"
                style={{
                  background: riskScore >= 80 ? '#ef4444' : '#f59e0b',
                  color: '#fff',
                  padding: '2px 8px',
                  borderRadius: '4px',
                }}
              >
                RISK {riskScore}%
              </span>
            </div>

            {/* Wallet address */}
            <div className="alert-wallet-flat">{alert.wallet_address}</div>

            {/* Core metadata */}
            <div className="alert-details-flat">
              <strong>ORIGIN:</strong> {alert.primary_state?.toUpperCase()} <br />
              <strong>ISP/ASN:</strong> {alert.isp} ({alert.asn}) <br />
              <strong>CLASS:</strong> {alert.cluster_name?.toUpperCase()}
              {riskFactors.length > 0 && (
                <div style={{ marginTop: '4px', fontSize: '10px', color: '#f87171' }}>
                  ⚠️ {riskFactors.join(', ')}
                </div>
              )}
            </div>

            {/* SHAP XAI attribution chips */}
            {shapAttributions.length > 0 && (
              <div style={{ marginTop: '6px' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', marginBottom: '4px', letterSpacing: '0.5px' }}>
                  XAI ATTRIBUTION
                </div>
                <ShapChips attributions={shapAttributions} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
