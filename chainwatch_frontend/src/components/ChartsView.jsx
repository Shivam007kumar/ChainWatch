import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';

/**
 * normalise(stats)
 * Reads from either the old flat shape or the new nested shape.
 * See MetricCards.jsx for full explanation.
 */
function normalise(stats) {
  if (!stats) return null;
  return {
    total_wallets:      stats.total_wallets      ?? stats.entities?.wallets         ?? null,
    anomalies_detected: stats.anomalies_detected ?? stats.risk?.flagged_wallets     ?? null,
  };
}

export default function ChartsView({ stats, clusters }) {
  const n = normalise(stats);

  if (!n || !clusters) {
    return (
      <div className="charts-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
        <div className="card chart-card"><div className="metric-loading" style={{ height: '100%' }} /></div>
        <div className="card chart-card"><div className="metric-loading" style={{ height: '100%' }} /></div>
      </div>
    );
  }

  const totalWallets      = n.total_wallets      ?? 0;
  const anomaliesDetected = n.anomalies_detected ?? 0;
  const normalCount       = Math.max(totalWallets - anomaliesDetected, 0);

  // Only render the pie if we actually have data
  const pieData = (totalWallets > 0) ? [
    { name: 'Normal Wallets',  value: normalCount,       color: '#003366' },
    { name: 'Flagged Wallets', value: anomaliesDetected, color: '#FF9933' },
  ] : [];

  const barData = clusters.map(c => ({
    name:     c.cluster_name.split(' ')[0],
    fullName: c.cluster_name,
    count:    c.wallet_count,
  }));

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#fff', border: '1px solid #d1d5db', padding: '10px', borderRadius: '2px', fontSize: '12px' }}>
          <p style={{ fontWeight: 700, marginBottom: '4px', color: '#111827' }}>{payload[0].payload?.fullName || label || payload[0].name}</p>
          <p style={{ color: payload[0].color }}>
            Count: <span style={{ fontWeight: 700 }}>{payload[0].value}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="charts-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>

      {/* Risk Distribution */}
      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">Risk Distribution</div>
        </div>
        <div className="chart-body">
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%" cy="50%"
                    innerRadius={60} outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="chart-legend-custom">
                <div className="cl-item"><div className="cl-dot" style={{ background: '#003366' }} /> Normal</div>
                <div className="cl-item"><div className="cl-dot" style={{ background: '#FF9933' }} /> Flagged</div>
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13 }}>
              Ingest a dataset to see distribution
            </div>
          )}
        </div>
      </div>

      {/* AI Cluster Threat Assessment */}
      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">AI Cluster Threat Assessment</div>
        </div>
        <div className="chart-body">
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#d1d5db" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#374151', fontWeight: 600 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#374151', fontWeight: 600 }} axisLine={false} tickLine={false} />
                <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: '#f2f4f7' }} />
                <Bar dataKey="count" fill="#003366" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13 }}>
              Ingest a dataset to see cluster data
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
