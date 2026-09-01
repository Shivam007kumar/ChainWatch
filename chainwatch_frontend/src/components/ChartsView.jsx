import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';

export default function ChartsView({ stats, clusters }) {
  if (!stats || !clusters) {
    return (
      <div className="charts-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
        <div className="card chart-card"><div className="metric-loading" style={{height: '100%'}}/></div>
        <div className="card chart-card"><div className="metric-loading" style={{height: '100%'}}/></div>
      </div>
    );
  }

  // 1. Donut Chart Data (Normal vs Anomalous Wallets)
  const pieData = [
    { name: 'Normal Wallets', value: stats.total_wallets - stats.anomalies_detected, color: '#0d9488' },
    { name: 'Flagged Wallets', value: stats.anomalies_detected, color: '#e11d48' }
  ];

  // 2. Bar Chart Data (Clusters)
  const barData = clusters.map(c => ({
    name: c.cluster_name.split(' ')[0], 
    fullName: c.cluster_name,
    count: c.wallet_count,
    color: '#3b82f6'
  }));

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', padding: '10px', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)', fontSize: '12px' }}>
          <p style={{ fontWeight: 600, marginBottom: '4px', color: '#111827' }}>{payload[0].payload?.fullName || label || payload[0].name}</p>
          <p style={{ color: payload[0].color || '#3b82f6' }}>
            Count: <span style={{ fontWeight: 700 }}>{payload[0].value}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="charts-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
      {/* Chart 1: Donut */}
      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">Risk Distribution</div>
          <div className="chart-sub">Flagged vs Normal Entities</div>
        </div>
        <div className="chart-body">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%" cy="50%"
                innerRadius={60} outerRadius={80}
                paddingAngle={5}
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
            <div className="cl-item"><div className="cl-dot" style={{background: '#0d9488'}}/> Normal ({(100 - (stats.anomalies_detected/stats.total_wallets)*100).toFixed(1)}%)</div>
            <div className="cl-item"><div className="cl-dot" style={{background: '#e11d48'}}/> Flagged</div>
          </div>
        </div>
      </div>

      {/* Chart 2: Bar */}
      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">Anomalies by Pattern</div>
          <div className="chart-sub">K-Means Cluster Distribution</div>
        </div>
        <div className="chart-body">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
              <XAxis dataKey="name" tick={{fontSize: 10, fill: '#6b7280'}} axisLine={false} tickLine={false} />
              <YAxis tick={{fontSize: 10, fill: '#6b7280'}} axisLine={false} tickLine={false} />
              <RechartsTooltip content={<CustomTooltip />} cursor={{fill: '#f9fafb'}} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {barData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
