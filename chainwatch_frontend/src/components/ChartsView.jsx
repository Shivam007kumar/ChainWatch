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

  // Use Government Colors
  const pieData = [
    { name: 'Normal Wallets', value: stats.total_wallets - stats.anomalies_detected, color: '#003366' },
    { name: 'Flagged Wallets', value: stats.anomalies_detected, color: '#FF9933' }
  ];

  const barData = clusters.map(c => ({
    name: c.cluster_name.split(' ')[0], 
    fullName: c.cluster_name,
    count: c.wallet_count,
    color: '#003366' // Deep Blue
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
      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">Risk Distribution</div>
        </div>
        <div className="chart-body">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
              </Pie>
              <RechartsTooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="chart-legend-custom">
            <div className="cl-item"><div className="cl-dot" style={{background: '#003366'}}/> Normal</div>
            <div className="cl-item"><div className="cl-dot" style={{background: '#FF9933'}}/> Flagged</div>
          </div>
        </div>
      </div>

      <div className="card chart-card">
        <div className="chart-header">
          <div className="chart-title">AI Cluster Threat Assessment</div>
        </div>
        <div className="chart-body">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#d1d5db" />
              <XAxis dataKey="name" tick={{fontSize: 10, fill: '#374151', fontWeight: 600}} axisLine={false} tickLine={false} />
              <YAxis tick={{fontSize: 10, fill: '#374151', fontWeight: 600}} axisLine={false} tickLine={false} />
              <RechartsTooltip content={<CustomTooltip />} cursor={{fill: '#f2f4f7'}} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {barData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}