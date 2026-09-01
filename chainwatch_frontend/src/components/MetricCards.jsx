import { useEffect, useState } from 'react';

const METRICS = [
  {
    key: 'total_transactions',
    label: 'Transactions Analyzed',
    icon: '⛓',
    color: 'teal',
    suffix: '',
    sub: 'Synthetic BTC dataset',
  },
  {
    key: 'total_wallets',
    label: 'Unique Wallets',
    icon: '👛',
    color: 'blue',
    suffix: '',
    sub: 'Addresses observed',
  },
  {
    key: 'anomalies_detected',
    label: 'Anomalies Detected',
    icon: '⚠',
    color: 'amber',
    suffix: '',
    sub: 'Isolation Forest (8% rate)',
  },
  {
    key: 'high_risk_wallets',
    label: 'High-Risk Wallets',
    icon: '🚨',
    color: 'red',
    suffix: '',
    sub: 'Confidence ≥ 85%',
  },
  {
    key: 'clusters_identified',
    label: 'Entity Clusters',
    icon: '🔗',
    color: 'purple',
    suffix: '',
    sub: 'K-Means (k=6)',
  },
];

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target === null || target === undefined) return;
    let start = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setValue(target);
        clearInterval(timer);
      } else {
        setValue(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return value;
}

function MetricCard({ metric, rawValue }) {
  const animated = useCountUp(rawValue);
  return (
    <div className={`metric-card ${metric.color}`}>
      <div className="metric-icon">{metric.icon}</div>
      <div className="metric-label">{metric.label}</div>
      {rawValue === null ? (
        <div className="metric-loading" />
      ) : (
        <div className={`metric-value ${metric.color}`}>
          {animated.toLocaleString()}{metric.suffix}
        </div>
      )}
      <div className="metric-sub">{metric.sub}</div>
    </div>
  );
}

export default function MetricCards({ stats }) {
  return (
    <div className="metrics-grid">
      {METRICS.map((m) => (
        <MetricCard
          key={m.key}
          metric={m}
          rawValue={stats ? stats[m.key] : null}
        />
      ))}
    </div>
  );
}
