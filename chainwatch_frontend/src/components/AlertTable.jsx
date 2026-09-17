import React from 'react';

export default function AlertTable({ alerts, loading, selectedWallet, onSelectWallet }) {
  if (loading) return <div style={{ padding: '20px' }}>Querying intelligence database...</div>;
  if (!alerts || alerts.length === 0) return <div style={{ padding: '20px' }}>No active threats found.</div>;

  return (
    <div className="alert-body">
      {alerts.map((alert, idx) => {
        const riskScore = alert.risk_score || alert.confidence_score || 0;
        const riskFactors = alert.risk_factors || [];

        return (
          <div
            key={alert.wallet_address}
            className={`alert-row-flat ${selectedWallet === alert.wallet_address ? 'selected' : ''}`}
            onClick={() => onSelectWallet(alert.wallet_address)}
          >
            <div className="alert-header-flat">
              <span className="alert-rank-flat">FILE #{idx + 1}</span>
              <span className="alert-score-flat" style={{ background: riskScore >= 80 ? '#ef4444' : '#f59e0b', color: '#fff', padding: '2px 8px', borderRadius: '4px' }}>
                RISK {riskScore}%
              </span>
            </div>
            <div className="alert-wallet-flat">{alert.wallet_address}</div>
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
          </div>
        );
      })}
    </div>
  );
}